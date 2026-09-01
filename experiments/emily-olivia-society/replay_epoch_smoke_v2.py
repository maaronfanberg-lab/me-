#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from community_session import recent_dialogue_history

with tempfile.TemporaryDirectory() as tmp:
    stream = Path(tmp) / "community_session.jsonl"
    rows = [
        {"type": "session_start", "session_id": "old", "seed": {"message": {"id": 1, "from_name": "Emily", "content": "Old line"}}},
        {"type": "turn", "session_id": "old", "turn": {"action_result": {"message": {"id": 2, "from_name": "Olivia", "content": "Old reply"}}}},
    ]
    stream.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    assert len(recent_dialogue_history(stream)) == 2
    stream.unlink()
    assert recent_dialogue_history(stream) == []
print("Replay reset regression check passed.")
