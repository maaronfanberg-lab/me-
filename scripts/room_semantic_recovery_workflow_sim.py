#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
workflow = ROOT / ".github" / "workflows" / "room-semantic-recovery.yml"
assert workflow.exists(), "RED: independent semantic-recovery workflow does not exist"
text = workflow.read_text()
assert "society/pulse-kick.txt" in text, "RED: recovery preflight is not tied to Room restart"
assert "python3 scripts/room_semantic_epoch.py migrate" in text, "RED: recovery workflow does not run the tested migration"
assert "git add room" in text, "RED: recovered state is not staged"
assert "git push origin HEAD:main" in text, "RED: recovered state is not published to main"
assert "ROOM_PROMPT_" not in text and "ROOM_NODE_PROMPT" not in text, "RED: recovery preflight must not receive cognition secrets"
print("PASS: independent semantic recovery publishes before model cognition is needed")
