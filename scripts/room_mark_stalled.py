#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def mark_stalled(state_path: Path) -> dict:
    state = json.loads(state_path.read_text())
    heartbeat = state.get("heartbeat")
    if heartbeat is None:
        heartbeat = {}
    if not isinstance(heartbeat, dict):
        raise RuntimeError(f"invalid Room heartbeat: {heartbeat!r}")
    last = str(heartbeat.get("last_successful_beat_at") or state.get("last_run") or "").strip()
    if not last:
        raise RuntimeError("cannot mark Room stalled without a last successful beat timestamp")
    heartbeat = dict(heartbeat)
    heartbeat["last_successful_beat_at"] = last
    heartbeat["stalled"] = True
    heartbeat["stalled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state["heartbeat"] = heartbeat
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return state


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("room/state.json")
    mark_stalled(path)
    print(f"ROOM HEARTBEAT: stalled=true path={path}")


if __name__ == "__main__":
    main()
