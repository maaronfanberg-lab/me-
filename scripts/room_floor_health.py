#!/usr/bin/env python3
"""Minimal, privacy-safe evidence about Room's selected-floor liveness fallback.

The runner calls this only AFTER resetting to the current main branch, and
the next successful ordinary Room commit stages it. A failure to write this
optional diagnostic must never interrupt conversation recovery. The source
of truth remains the Git-published state, not this diagnostic.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

KNOWN_STAGES = frozenset({
    "before_floor",
    "floor_selection",
    "expression_generation",
    "candidate_preflight",
    "validated_publication",
    "unknown",
})


def fallback_record(run_id: str, stages: str, *, now: str | None = None) -> dict:
    """Accept stage codes only; never serialize secrets, prompts, or text."""
    raw = (stages or "").split(",")
    clean = [
        stage if stage in KNOWN_STAGES else "unknown"
        for stage in raw[:2] if stage
    ]
    if not clean:
        clean = ["unknown"]
    rid = str(run_id or "")
    if len(rid) > 40 or not rid.isdigit():
        rid = "unknown"
    return {
        "schema": 1,
        "outcome": "runner_fell_back_to_legacy",
        "failure_stages": clean,
        "run_id": rid,
        "recorded_at": now or datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stages", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Path(args.out)
    result = fallback_record(args.run_id, args.stages)
    output.parent.mkdir(parents=True, exist_ok=True)
    # This file is diagnostic only. Avoid half-written JSON if interrupted.
    temp = output.with_name(output.name + ".writing")
    temp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temp.replace(output)


if __name__ == "__main__":
    main()
