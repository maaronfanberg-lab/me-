#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import room_private_commit as publish
import room_skill_exec as skill_exec


def main() -> None:
    assert getattr(publish, "QUALITY_REJECTION_EXIT", None) == 42, (
        "publish boundary has no distinct semantic-rejection exit code"
    )
    classify = getattr(publish, "quality_rejection_exit_code", None)
    assert callable(classify), "publish boundary cannot classify intentional quality rejection"
    assert classify(RuntimeError("private Room same-beat echo blocked for sarah: semantic_phrase_mosaic")) == 42
    assert classify(RuntimeError("private Room privacy leak blocked for sarah")) is None
    assert classify(RuntimeError("model process crashed")) is None

    # Live pre-PR130 runners proved a second liveness seam before final publish:
    # all expression retries could be rejected for dialogue quality, after which
    # the shell incorrectly counted the beat as an infrastructure failure.
    exhaustion_reason = getattr(skill_exec, "expression_quality_exhaustion_reason", None)
    assert callable(exhaustion_reason), "expression wrapper cannot classify quality exhaustion"
    assert exhaustion_reason(
        "RuntimeError: private model output rejected for expression: same_beat_semantic_coverage\n"
    ) == "same_beat_semantic_coverage"
    assert exhaustion_reason(
        "RuntimeError: private model output rejected for expression: duplicate_context\n"
    ) == "duplicate_context"
    assert exhaustion_reason(
        "RuntimeError: private model output rejected for expression: same_beat_phrase_echo\n"
    ) == "same_beat_phrase_echo"

    # Model/transport/schema failures must not be laundered into quality retries.
    assert exhaustion_reason(
        "RuntimeError: private model output rejected for expression: empty_output\n"
    ) is None
    assert exhaustion_reason(
        "RuntimeError: private model request failed for expression: HTTP 500\n"
    ) is None
    assert exhaustion_reason(
        "RuntimeError: private model output rejected for expression: schema missing utterance\n"
    ) is None

    marker_reader = getattr(publish, "beat_quality_marker_reason", None)
    marker_writer = getattr(skill_exec, "write_quality_rejection_marker", None)
    assert callable(marker_reader), "publish boundary cannot see expression-quality beat marker"
    assert callable(marker_writer), "expression wrapper cannot mark a doomed beat for regeneration"
    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "room_work" / "quality-rejection.json"
        marker_writer("duplicate_context", marker)
        assert marker_reader(marker) == "duplicate_context"
        payload = json.loads(marker.read_text())
        assert payload.get("kind") == "expression_quality_exhaustion"
        assert payload.get("reason") == "duplicate_context"

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
