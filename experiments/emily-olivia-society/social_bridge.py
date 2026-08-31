#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from controlled_social_space import ControlledSocialSpace

HERE = Path(__file__).resolve().parent
SOCIAL_STATE = HERE / "replay" / "social_state.json"
MAX_REQUEST_CHARS = 32_768


async def main() -> None:
    pairs = [(1, "Emily"), (2, "Olivia")]
    social = ControlledSocialSpace(pairs, state_path=SOCIAL_STATE)

    for raw in sys.stdin:
        if len(raw) > MAX_REQUEST_CHARS:
            print(json.dumps({"ok": False, "error": "RequestTooLarge: social bridge request exceeded limit"}), flush=True)
            continue
        raw = raw.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object.")
            op = request.get("op")
            if not isinstance(op, str) or not op:
                raise ValueError("Request requires a non-empty op.")
            if op == "observe":
                result = await social.observe_social_space(int(request["agent_id"]))
            elif op == "send":
                result = await social.send_message(
                    int(request["agent_id"]),
                    int(request["recipient_id"]),
                    str(request["content"]),
                )
            elif op == "consume":
                result = await social.consume_message(
                    int(request["agent_id"]),
                    int(request["message_id"]),
                )
            elif op == "close":
                print(json.dumps({"ok": True, "result": {"closed": True}}), flush=True)
                return
            else:
                raise ValueError(f"Unknown operation: {op}")
            print(json.dumps({"ok": True, "result": result}), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
