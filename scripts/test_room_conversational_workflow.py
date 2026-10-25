#!/usr/bin/env python3
"""Static syntax and rollback checks on the actual GitHub Actions runner."""
from __future__ import annotations
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
workflow = (root / ".github/workflows/sarah-society.yml").read_text()
start = workflow.index("        run: |\n") + len("        run: |\n")
shell_lines = []
for line in workflow[start:].splitlines():
    if line.startswith("          "):
        shell_lines.append(line[10:])
    elif not line.strip():
        shell_lines.append("")
    else:
        break
script = "\n".join(shell_lines) + "\n"
if not script.strip():
    raise AssertionError("Room shell runner empty")
proc = subprocess.run(("bash", "-n"), input=script, text=True, capture_output=True)
if proc.returncode:
    raise AssertionError("Room bash syntax: " + proc.stderr[:1000])
checks = (
    'if [ "${ROOM_CONVERSATIONAL_FLOOR:-0}" = "1" ]; then',
    'ROOM_EXPRESSION_RANK="0"',
    'scripts/room_conversational_candidate.py',
    'expr_nodes=(2 5 8 11)',
    'export ROOM_CONVERSATIONAL_FLOOR=0',
    'ROOM_FLOOR_DESIRED=',
    'floor_recovery_after_seq=',
    'Room selected-floor re-probe after temporary technical fallback',
    'ROOM_FLOOR_LAST_FAILURE="model_generation"',
    'ROOM_FLOOR_LAST_FAILURE="candidate_preflight"',
    'ROOM_FLOOR_FALLBACK_REASON=',
    'git diff --quiet HEAD^ origin/main',
)
for snippet in checks:
    if snippet not in script:
        raise AssertionError("missing Room selection or rollback path: " + snippet)
# An older repository variable can explicitly hold the Room on the
# legacy engine even when the tested code is deployed. The pilot uses a
# separate emergency disable switch so its initial state is unambiguous.
if "vars.ROOM_CONVERSATIONAL_FLOOR_DISABLE == '1' && '0' || '1'" not in workflow:
    raise AssertionError("live pilot must be enabled by default with reversible disable switch")
if 'ROOM_FLOOR_DESIRED="${ROOM_CONVERSATIONAL_FLOOR:-0}"' not in script:
    raise AssertionError("selected-turn recovery must observe the activated flag")
print("PASS: Room workflow shell syntax and both selected/legacy routes")
