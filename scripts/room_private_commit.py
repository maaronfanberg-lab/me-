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
QUALITY_REJECTION_COUNTER = Path(".room-quality-rejections")
PUBLISH_RETRY_MARKER = Path(".room-publish-retry.json")
MAX_CONSECUTIVE_QUALITY_REJECTIONS = 3


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


def _quality_rejection_count() -> int:
    try:
        return max(0, int(QUALITY_REJECTION_COUNTER.read_text().strip()))
    except Exception:
        return 0


def _record_quality_rejection(reason: str) -> None:
    count = _quality_rejection_count() + 1
    QUALITY_REJECTION_COUNTER.write_text(f"{count}\n")
    if count > MAX_CONSECUTIVE_QUALITY_REJECTIONS:
        print(
            f"ROOM QUALITY REJECTION LIMIT: {count} consecutive rejections; "
            "escalating to runner failure/handoff",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(
        f"ROOM QUALITY REJECTION {count}/{MAX_CONSECUTIVE_QUALITY_REJECTIONS}: "
        f"{reason}; regenerating whole beat",
        file=sys.stderr,
    )
    raise SystemExit(QUALITY_REJECTION_EXIT)


def _clear_quality_rejections() -> None:
    try:
        QUALITY_REJECTION_COUNTER.unlink()
    except FileNotFoundError:
        pass


def clear_publish_retry_marker(path: Path | None = None) -> None:
    marker = Path(path) if path is not None else PUBLISH_RETRY_MARKER
    try:
        marker.unlink()
    except FileNotFoundError:
        pass


def _run_cli() -> None:
    reason = beat_quality_marker_reason()
    if reason:
        _record_quality_rejection(reason)

    try:
        _core._run_cli()
    except SystemExit as exc:
        if exc.code == QUALITY_REJECTION_EXIT:
            _record_quality_rejection("publish-quality rejection")
        raise
    else:
        _clear_quality_rejections()
        clear_publish_retry_marker()


def __getattr__(name: str):
    return getattr(_core, name)


if __name__ == "__main__":
    _run_cli()
