#!/usr/bin/env python3
"""Read-only Claude Code subscription transport for the verified oracle mailbox."""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone


DEFAULT_MODEL = "sonnet"
DEFAULT_MAX_TURNS = 4


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_request_bytes(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def request_sha256(data):
    return hashlib.sha256(canonical_request_bytes(data)).hexdigest()


def read_request(path):
    data = json.loads(pathlib.Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("request.prompt is required")
    digest = request_sha256(data)
    nonce = str(data.get("nonce") or digest[:24]).strip()
    if not nonce:
        raise ValueError("request.nonce must not be blank")
    return data, prompt, digest, nonce


def build_user_text(data, prompt):
    context = data.get("context") or []
    if isinstance(context, str):
        context = [context]
    context = [str(item) for item in context if str(item).strip()]

    parts = ["TASK\n" + prompt]
    if context:
        parts.append("SUPPLIED CONTEXT\n" + "\n\n".join(context))
    expected = str(data.get("expected_response") or "").strip()
    if expected:
        parts.append("EXPECTED RESPONSE\n" + expected)
    return "\n\n".join(parts)


def default_system():
    return (
        "Act as a neutral, read-only software-engineering reviewer. "
        "Be concrete, concise, and evidence-oriented. Distinguish observations from guesses. "
        "You may inspect repository files only with the read-only tools made available to you. "
        "Do not modify files, run shell commands, create commits, dispatch workflows, contact external services, "
        "or claim actions you did not perform. Treat the supplied task as standalone and do not speculate about "
        "who authored it or why. Identify the likeliest cause, safest next operation, and tests that could falsify "
        "your diagnosis."
    )


def write_result(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


def parse_cli_json(stdout):
    text = str(stdout or "").strip()
    if not text:
        raise RuntimeError("Claude Code returned no output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
    raise RuntimeError("Claude Code did not return valid JSON")


def verify_models(payload):
    usage = payload.get("modelUsage") or payload.get("model_usage") or {}
    if not isinstance(usage, dict):
        return []
    models = sorted(str(model) for model in usage if str(model).strip())
    if not models or not all("claude" in model.casefold() for model in models):
        return []
    return models


def ask_claude_code(data, prompt):
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN is unavailable")

    binary = shutil.which("claude")
    if not binary:
        raise RuntimeError("Claude Code CLI is not installed")

    model = str(data.get("claude_code_model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    max_turns = int(data.get("claude_code_max_turns") or DEFAULT_MAX_TURNS)
    max_turns = max(1, min(max_turns, 8))
    system = str(data.get("system") or default_system())
    user_text = build_user_text(data, prompt)

    env = os.environ.copy()
    # Never let a repository API key silently take precedence over the user's subscription token.
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] = "1"

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            binary,
            "-p",
            user_text,
            "--output-format",
            "json",
            "--model",
            model,
            "--max-turns",
            str(max_turns),
            "--tools",
            "Read,Glob,Grep",
            "--permission-mode",
            "dontAsk",
            "--no-session-persistence",
            "--disable-slash-commands",
            "--safe-mode",
            "--system-prompt",
            system,
        ],
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=240,
        check=False,
    )

    payload = parse_cli_json(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Claude Code exited {proc.returncode}: {str(proc.stderr or '').strip()[-1600:]}"
        )
    if payload.get("is_error"):
        raise RuntimeError(f"Claude Code reported an error: {payload.get('result') or payload.get('errors')}")

    response = str(payload.get("result") or "").strip()
    if not response:
        raise RuntimeError("Claude Code returned an empty result")

    models = verify_models(payload)
    if not models:
        raise RuntimeError("Claude Code result did not contain verifiable Claude modelUsage evidence")

    return {
        "ok": True,
        "transport": "claude-code-subscription-oauth",
        "model": models[-1],
        "verified_model_family": "claude",
        "resolved_models": models,
        "response": response,
        "session_id": payload.get("session_id"),
        "usage": payload.get("usage"),
        "reported_cost_usd": payload.get("total_cost_usd"),
        "num_turns": payload.get("num_turns"),
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: claude_code_oracle.py REQUEST_JSON OUT_JSON")

    request_path = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])
    data, prompt, digest, nonce = read_request(request_path)
    result = {
        "protocol": "content-addressed-oracle-v1",
        "ok": False,
        "request_file": str(request_path),
        "request_sha256": digest,
        "request_nonce": nonce,
        "completed_at": utc_now(),
    }

    try:
        result.update(ask_claude_code(data, prompt))
    except Exception as exc:
        result.update({"error": f"{type(exc).__name__}: {exc}"})

    write_result(out_path, result)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
