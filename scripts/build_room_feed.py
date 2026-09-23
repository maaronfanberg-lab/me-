#!/usr/bin/env python3
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
live = json.loads((ROOM / "live.json").read_text())
entities = {}
for entity_id, mind in (live.get("minds", {}).get("entities", {}) or {}).items():
    entities[entity_id] = {
        "name": mind.get("name", entity_id),
        "status": mind.get("status", "awake"),
        "genome": mind.get("genome", {}),
        "development": mind.get("development", {}),
        "memory": mind.get("memory", [])[-12:],
    }
conversation = [{
    "id": m.get("id"), "speaker": m.get("speaker"), "text": m.get("text"),
    "at": m.get("at"), "beat_id": m.get("beat_id")
} for m in (live.get("conversation", []) or [])[-160:]]
brain = {
    "active": os.environ.get("ROOM_BRAIN_ACTIVE", "unknown").strip() or "unknown",
    "run_id": os.environ.get("GITHUB_RUN_ID", "").strip() or None,
    "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "").strip() or None,
}
feed = {
    "generated_at": live.get("generated_at"), "state": live.get("state", {}),
    "brain": brain,
    "minds": {"entities": entities}, "conversation": conversation,
}
(ROOM / "brain-status.json").write_text(json.dumps(brain, ensure_ascii=False, indent=2) + "\n")
(ROOM / "feed.json").write_text(json.dumps(feed, ensure_ascii=False, separators=(",", ":")) + "\n")
