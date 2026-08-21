#!/usr/bin/env python3
from __future__ import annotations

"""Room publish facade that also honors expression-stage beat regeneration."""

import json
import sys
from pathlib import Path

import room_private_commit_liveness_core as _core

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

QUALITY_REJECTION_EXIT = _core.QUALITY_REJECTION_EXIT
QUALITY_MARKER = Path("room_work/quality-rejection.json")


def beat_quality_marker_reason(path: Path | None = None) -> str | None:
    marker = Path(path) if path is not None else QUALITY_MARKER
    try:
        payload = json.loads(marker.read_text())
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("kind") != "expression_quality_exhaustion":
        return None
    reason = str(payload.get("reason") or "").strip()
    return reason or None


def _run_cli() -> None:
    reason = beat_quality_marker_reason()
    if reason:
        print(
            f"ROOM EXPRESSION QUALITY REJECTION: {reason}; regenerating whole beat",
            file=sys.stderr,
        )
        raise SystemExit(QUALITY_REJECTION_EXIT)
    _core._run_cli()


def __getattr__(name: str):
    return getattr(_core, name)


if __name__ == "__main__":
    _run_cli()
