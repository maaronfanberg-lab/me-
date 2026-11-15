from __future__ import annotations

import base64
from pathlib import Path

ROOM = Path("apps/sarah-room.html")
FEED = Path("room/feed.json")
LIVE = Path("society/live.json")  # fallback only
TOKEN = "__ROOM_SNAPSHOT_B64__"

html = ROOM.read_text(encoding="utf-8")
if TOKEN not in html:
    raise SystemExit(f"missing bake token {TOKEN} in {ROOM}")

source = FEED if FEED.exists() else LIVE
snapshot = source.read_bytes()
encoded = base64.b64encode(snapshot).decode("ascii")
ROOM.write_text(html.replace(TOKEN, encoded), encoding="utf-8")
print(f"Baked {len(snapshot)} bytes from {source} into {ROOM}")
