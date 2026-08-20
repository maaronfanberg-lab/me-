#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = (ROOT / "room" / "index.html").read_text()
WORKER = (ROOT / "cloudflare" / "room-worker" / "src" / "index.js").read_text()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require("semantic-epoch-v1/conversation.json" in VIEWER,
            "viewer does not load the pre-reset semantic archive")
    require("archiveHistoryData" in VIEWER,
            "viewer has no separate archive history buffer")
    require("[archiveHistoryData,historyData,liveData?.conversation||[]]" in VIEWER.replace(" ", ""),
            "viewer does not merge archive before active/live history")
    require("seen.has(m.id)" in VIEWER,
            "viewer history merge does not deduplicate message IDs")

    require("semantic-epoch-v1/conversation.json" in WORKER,
            "Allen viewer does not load the pre-reset semantic archive")
    require("allenArchiveHistory" in WORKER and "allenActiveHistory" in WORKER,
            "Allen viewer lacks separate archive and active history buffers")
    require("mergeAllenHistory" in WORKER,
            "Allen viewer does not merge archive, active history, and relay feed")
    require("seen.has(String(x.id))" in WORKER,
            "Allen viewer history merge does not deduplicate message IDs")
    require("Math.max(0,c.length-90)" not in WORKER,
            "Allen viewer still hard-caps itself to only 90 relay messages")
    print("ROOM VIEWER HISTORY SIM: GREEN")


if __name__ == "__main__":
    main()
