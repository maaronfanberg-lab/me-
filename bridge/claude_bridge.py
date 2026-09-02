#!/usr/bin/env python3
import hashlib
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
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_COPILOT_CLAUDE_MODELS = (
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-haiku-4.5",
)


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
    context = [str(x) for x in context if str(x).strip()]
    parts = ["TASK\n" + prompt]
    if context:
        parts.append("REPOSITORY CONTEXT\n" + "\n\n".join(context))
    expected = str(data.get("expected_response") or "").strip()
    if expected:
        parts.append("EXPECTED RESPONSE\n" + expected)
    return "\n\n".join(parts)


def default_system():
    return (
        "Review the supplied standalone software-engineering task. "
        "Be concrete, concise, and evidence-oriented. Distinguish observations from guesses. "
        "Identify the likeliest cause, the safest next operation, and tests that would falsify the diagnosis. "
        "Do not use tools, modify files, ask questions, or claim actions you did not perform. "
        "Treat the supplied text as the complete task; do not speculate about who authored it or why."
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
    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": API_VERSION,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = json.loads(response.read().decode("utf-8"))
    text_parts = [b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text"]
    response_text = "\n".join(x for x in text_parts if x).strip()
    if not response_text:
        raise RuntimeError("Anthropic returned an empty response")
    return {
        "ok": True,
        "transport": "anthropic-api",
        "model": model,
        "verified_model_family": "claude",
        "response": response_text,
        "stop_reason": raw.get("stop_reason"),
        "usage": raw.get("usage"),
        "message_id": raw.get("id"),
    }


def _assistant_text_from_jsonl(stdout):
    chunks = []
    for line in str(stdout or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "assistant.message":
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        content = data.get("content")
        if isinstance(content, str) and content.strip():
            chunks.append(content.strip())
    return "\n".join(chunks).strip()


def _string_value(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for key in ("stringValue", "string_value", "value"):
        item = value.get(key)
        if isinstance(item, str):
            return item
    return ""


def _collect_response_models(obj, found):
    if isinstance(obj, dict):
        direct = obj.get("gen_ai.response.model")
        direct_text = _string_value(direct)
        if direct_text:
            found.add(direct_text)
        if obj.get("key") == "gen_ai.response.model":
            text = _string_value(obj.get("value"))
            if text:
                found.add(text)
        for value in obj.values():
            _collect_response_models(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _collect_response_models(value, found)


def _response_models_from_otel(path):
    found = set()
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        _collect_response_models(payload, found)
    return sorted(found)


def _all_models_are_claude(models):
    return bool(models) and all("claude" in str(model).casefold() for model in models)


def _copilot_candidates(data):
    requested = data.get("copilot_models")
    if isinstance(requested, str):
        requested = [x.strip() for x in requested.split(",") if x.strip()]
    if isinstance(requested, list):
        cleaned = [str(x).strip() for x in requested if str(x).strip()]
        if cleaned:
            return cleaned
    env_models = [x.strip() for x in os.environ.get("COPILOT_CLAUDE_MODELS", "").split(",") if x.strip()]
    return env_models or list(DEFAULT_COPILOT_CLAUDE_MODELS)


def ask_copilot_verified_claude(data, prompt):
    binary = shutil.which("copilot")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not binary:
        raise RuntimeError("GitHub Copilot CLI is not installed")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is unavailable for Copilot fallback")

    system = str(data.get("system") or default_system())
    user_text = build_user_text(data, prompt)
    envelope = f"{system}\n\n{user_text}\n"

    base_env = os.environ.copy()
    base_env.setdefault("COPILOT_GITHUB_TOKEN", token)
    attempts = []

    with tempfile.TemporaryDirectory(prefix="oracle-bridge-audit-") as temp_dir_raw:
        temp_dir = pathlib.Path(temp_dir_raw)
        for attempt, candidate in enumerate(_copilot_candidates(data), start=1):
            otel_path = temp_dir / f"otel-{attempt}.jsonl"
            env = base_env.copy()
            env["COPILOT_OTEL_ENABLED"] = "true"
            env["COPILOT_OTEL_EXPORTER_TYPE"] = "file"
            env["COPILOT_OTEL_FILE_EXPORTER_PATH"] = str(otel_path)
            env["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "false"

            proc = subprocess.run(
                [
                    binary,
                    "-p",
                    envelope,
                    "--model",
                    candidate,
                    "--output-format",
                    "json",
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
            response = _assistant_text_from_jsonl(proc.stdout)
            models = _response_models_from_otel(otel_path)
            stderr_tail = str(proc.stderr or "").strip()[-1200:]
            attempts.append({
                "attempt": attempt,
                "returncode": proc.returncode,
                "requested_model": candidate,
                "resolved_models": models,
                "had_response": bool(response),
                "stderr_tail": stderr_tail,
            })

            if proc.returncode == 0 and response and _all_models_are_claude(models):
                return {
                    "ok": True,
                    "transport": "github-copilot-claude-verified-by-otel",
                    "model": models[-1],
                    "verified_model_family": "claude",
                    "resolved_models": models,
                    "response": response,
                    "routing_attempts": attempts,
                }

    summary = "; ".join(
        f"attempt {item['attempt']}: requested={item['requested_model']} "
        f"models={item['resolved_models'] or ['unverified']} rc={item['returncode']} "
        f"stderr={item['stderr_tail']!r}"
        for item in attempts
    )
    raise RuntimeError(
        "No telemetry-verified Claude answer was produced; every unverified or non-Claude response was discarded. "
        + summary
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: claude_bridge.py REQUEST_JSON OUT_JSON")

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
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if key:
            answer = ask_anthropic(data, prompt, key)
        else:
            answer = ask_copilot_verified_claude(data, prompt)
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
