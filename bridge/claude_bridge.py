#!/usr/bin/env python3
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-6"
COPILOT_CLAUDE_MODEL = "claude-sonnet-4.6"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_request(path):
    data = json.loads(pathlib.Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("request must be a JSON object")
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("request.prompt is required")
    return data, prompt


def build_user_text(data, prompt):
    context = data.get("context") or []
    if isinstance(context, str):
        context = [context]
    context = [str(x) for x in context if str(x).strip()]
    parts = [prompt]
    if context:
        parts.append("\nShared context from the collaborating agent/repository:\n" + "\n\n".join(context))
    return "\n".join(parts)


def default_system():
    return (
        "You are Claude collaborating with another AI agent through a GitHub mailbox. "
        "Be concrete, concise, and evidence-oriented. Distinguish observations from guesses. "
        "When reviewing a software problem, identify the likeliest cause, the safest next operation, "
        "and any tests that would falsify your diagnosis. Do not claim you changed files unless the request says you did."
    )


def write_result(out_path, result):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


def ask_anthropic(data, prompt, key):
    model = str(data.get("model") or DEFAULT_MODEL)
    max_tokens = int(data.get("max_tokens") or 1800)
    max_tokens = max(64, min(max_tokens, 8192))
    system = str(data.get("system") or default_system())
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": build_user_text(data, prompt)}],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": API_VERSION,
    })
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = json.loads(response.read().decode("utf-8"))
    text_parts = [b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text"]
    return {
        "ok": True,
        "transport": "anthropic-api",
        "model": model,
        "response": "\n".join(x for x in text_parts if x).strip(),
        "stop_reason": raw.get("stop_reason"),
        "usage": raw.get("usage"),
        "message_id": raw.get("id"),
    }


def ask_copilot_claude(data, prompt):
    binary = shutil.which("copilot")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not binary:
        raise RuntimeError("GitHub Copilot CLI is not installed")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is unavailable for Copilot fallback")

    system = str(data.get("system") or default_system())
    user_text = build_user_text(data, prompt)
    envelope = (
        "You are being invoked specifically as Claude through GitHub Copilot CLI, acting as a read-only peer reviewer.\n"
        "Do not use tools, do not modify files, and do not ask questions. Everything needed is embedded below.\n\n"
        f"SYSTEM INSTRUCTIONS FROM BRIDGE:\n{system}\n\n"
        f"REQUEST ENVELOPE:\n{user_text}\n"
    )

    env = os.environ.copy()
    env.setdefault("COPILOT_GITHUB_TOKEN", token)
    with tempfile.TemporaryDirectory(prefix="claude-bridge-review-") as temp_dir:
        proc = subprocess.run(
            [
                binary,
                "-p",
                envelope,
                "-s",
                "--model",
                COPILOT_CLAUDE_MODEL,
                "--no-ask-user",
                "--no-custom-instructions",
                "--no-color",
            ],
            cwd=temp_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
    response = proc.stdout.strip()
    if proc.returncode != 0 or not response:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"Copilot Claude fallback failed: {detail[:4000]}")
    return {
        "ok": True,
        "transport": "github-copilot-cli",
        "model": COPILOT_CLAUDE_MODEL,
        "response": response,
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: claude_bridge.py REQUEST_JSON OUT_JSON")

    request_path = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])
    data, prompt = read_request(request_path)
    result = {
        "ok": False,
        "request_file": str(request_path),
        "completed_at": utc_now(),
    }

    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if key:
            answer = ask_anthropic(data, prompt, key)
        else:
            answer = ask_copilot_claude(data, prompt)
        result.update(answer)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        result.update({"error": f"Claude API HTTP {exc.code}", "detail": detail[:4000]})
    except Exception as exc:
        result.update({"error": f"{type(exc).__name__}: {exc}"})

    write_result(out_path, result)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
