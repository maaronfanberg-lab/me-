#!/usr/bin/env python3
"""Small regression checks for Community replay epoch boundaries."""
from __future__ import annotations

import tempfile
from pathlib import Path

from community_session import recent_dialogue_history


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        stream = Path(tmp) / "community_session.jsonl"
        stream.write_text("", encoding="utf-8")
        if recent_dialogue_history(stream) != []:
            raise SystemExit("empty replay epoch unexpectedly supplied dialogue history")
    print("Replay epoch smoke passed.")


if __name__ == "__main__":
    main()
