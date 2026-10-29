#!/usr/bin/env python3
"""Guard against the observed 2026-10-29 CPU model timeout/restart loop."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runner = (root / ".github/workflows/sarah-society.yml").read_text()
model = (root / "scripts/room_private_model/__init__.py").read_text()
assert ' -c "$context_size" -np 1 >' in runner, "Only one CPU inference slot is budgeted"
assert ' -np 2 >' not in runner, "Parallel decoding previously caused request starvation"
assert 'for n in 0 3 6 9; do timeout' in runner
assert 'for n in 1 4 7 10; do timeout' in runner
assert 'for pair in "0 3" "6 9"' not in runner
assert 'for pair in "1 4" "7 10"' not in runner
assert '"n_predict": 192 if role == "comprehension" else (256 if role == "thought" else 320),' in model
assert 'ROOM_CONVERSATIONAL_FLOOR' in runner
assert 'ROOM_FLOOR_DESIRED=' in runner
assert 'ROOM_NODE_TIMEOUT_SECONDS=60' in runner
print("PASS: bounded model inference, single CPU slot, serial prompted stages and rollback")
