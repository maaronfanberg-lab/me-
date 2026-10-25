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
    'git diff --quiet HEAD^ origin/main',
)
for snippet in checks:
    if snippet not in script:
        raise AssertionError("missing Room selection or rollback path: " + snippet)
if "vars.ROOM_CONVERSATIONAL_FLOOR" not in workflow:
    raise AssertionError("Room feature flag not adjustable")
print("PASS: Room workflow shell syntax and both selected/legacy routes")
