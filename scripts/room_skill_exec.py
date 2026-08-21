#!/usr/bin/env python3
from __future__ import annotations

"""Room attention-router facade with beat-level expression-quality recovery.

The proven attention router lives in room_skill_exec_core. This facade preserves
its import API, but when the expression engine exhausts all five attempts for a
known dialogue-quality reason it marks the current beat for regeneration instead
of letting the warm runner misclassify that event as infrastructure failure.
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import room_skill_exec_core as _core

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

QUALITY_MARKER = Path("room_work/quality-rejection.json")
_QUALITY_OUTPUT_REASONS = {
    "empty_expression",
    "rambling_expression",
    "malformed_pronoun",
    "self_address",
    "trailing_fragment",
    "self_repetition",
    "duplicate_context",
}
_QUALITY_EXHAUSTION = re.compile(
    r"RuntimeError:\s*private model output rejected for expression:\s*([^\r\n]+)"
)


def expression_quality_exhaustion_reason(stderr: object) -> str | None:
    """Classify only exhausted expression-quality retries, never model failures."""
    matches = _QUALITY_EXHAUSTION.findall(str(stderr or ""))
    if not matches:
        return None
    reason = str(matches[-1]).strip()
    if reason.startswith("same_beat_") or reason in _QUALITY_OUTPUT_REASONS:
        return reason
    return None


def write_quality_rejection_marker(reason: str, path: Path | None = None) -> Path:
    """Persist only the rejection class; no private model text crosses this seam."""
    marker = Path(path) if path is not None else QUALITY_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "kind": "expression_quality_exhaustion",
        "reason": str(reason or "unknown")[:80],
    }, separators=(",", ":")) + "\n")
    return marker


def _is_expression_node(argv: list[str], env: dict[str, str]) -> bool:
    if not argv or "ROOM_EXPRESSION_RANK" not in env:
        return False
    target = Path(str(argv[0])).name
    return target == "room_engine_v5.py" and "node" in argv


def _run_child(argv: list[str], env: dict[str, str]) -> tuple[int, str]:
    """Run the routed child while forwarding termination to avoid orphan models."""
    with tempfile.TemporaryFile(mode="w+t") as err:
        proc = subprocess.Popen(
            [sys.executable, *argv],
            env=env,
            stderr=err,
        )
        previous: dict[int, object] = {}

        def forward(signum, _frame):
            if proc.poll() is None:
                try:
                    proc.send_signal(signum)
                except ProcessLookupError:
                    pass

        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, forward)
        try:
            rc = proc.wait()
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        err.seek(0)
        text = err.read()
    return rc, text


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: room_skill_exec.py <python-script> [args...]", file=sys.stderr)
        return 2

    env = _core.prepare_environment()
    expression_node = _is_expression_node(argv, env)
    if expression_node and QUALITY_MARKER.exists():
        print("ROOM EXPRESSION QUALITY: beat already marked for regeneration", file=sys.stderr)
        return 0

    rc, stderr = _run_child(argv, env)
    if stderr:
        sys.stderr.write(stderr)
        sys.stderr.flush()

    if expression_node and rc != 0:
        reason = expression_quality_exhaustion_reason(stderr)
        if reason:
            write_quality_rejection_marker(reason)
            print(
                f"ROOM EXPRESSION QUALITY REJECTION: {reason}; deferring beat to exit-42 regeneration",
                file=sys.stderr,
            )
            return 0
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
