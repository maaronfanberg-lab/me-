#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import room_private_commit as publish


def main() -> None:
    assert getattr(publish, "QUALITY_REJECTION_EXIT", None) == 42, (
        "publish boundary has no distinct semantic-rejection exit code"
    )
    classify = getattr(publish, "quality_rejection_exit_code", None)
    assert callable(classify), "publish boundary cannot classify intentional quality rejection"
    assert classify(RuntimeError("private Room same-beat echo blocked for sarah: semantic_phrase_mosaic")) == 42
    assert classify(RuntimeError("private Room privacy leak blocked for sarah")) is None
    assert classify(RuntimeError("model process crashed")) is None

    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sarah-society.yml"
    ).read_text()
    assert "ROOM_QUALITY_REJECTION_EXIT=42" in workflow, "runner does not share the boundary exit code"
    assert "commit_rc=$?" in workflow, "run_beat discards the commit process exit code"
    assert 'return "$ROOM_QUALITY_REJECTION_EXIT"' in workflow, (
        "run_beat does not preserve intentional quality rejection"
    )
    assert "beat_rc=$?" in workflow, "warm loop does not inspect the beat result"

    quality = workflow.find('if [ "$beat_rc" -eq "$ROOM_QUALITY_REJECTION_EXIT" ]')
    failure = workflow.find("consecutive_failures=$((consecutive_failures + 1))")
    assert quality >= 0, "warm loop has no quality-rejection regeneration branch"
    assert failure >= 0, "warm loop lost infrastructure failure accounting"
    assert quality < failure, "quality rejection is still counted as infrastructure failure"
    assert "Publish boundary rejected semantic echo; regenerating the beat" in workflow

    print("ROOM QUALITY-REJECTION RUNNER SIM: GREEN")


if __name__ == "__main__":
    main()
