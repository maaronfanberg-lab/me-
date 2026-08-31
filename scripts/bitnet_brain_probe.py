from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BITNET_URL", "http://127.0.0.1:8081").rstrip("/")


def get_json(path: str, timeout: int = 5) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def post_json(path: str, payload: dict, timeout: int = 60) -> dict:
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def main() -> int:
    try:
        health = get_json("/health")
        if health.get("status") not in {"ok", "no slot available"}:
            raise RuntimeError(f"unexpected health response: {health}")

        result = post_json(
            "/completion",
            {
                "prompt": "Reply with exactly: BITNET_ALIVE",
                "n_predict": 16,
                "temperature": 0.0,
                "cache_prompt": True,
            },
        )
        text = str(result.get("content", "")).strip()
        if not text:
            raise RuntimeError(f"completion returned no content: {result}")

        print(json.dumps({"ok": True, "url": BASE, "content": text}, ensure_ascii=False))
        return 0
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "url": BASE, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
