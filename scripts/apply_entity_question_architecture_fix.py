#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parent / "room_private_model.py"
text = path.read_text()
old = '            and event_speaker in PEOPLE\n            and event_speaker != self_entity\n'
new = '            and event_speaker in PEOPLE\n            and event_speaker != "allen"\n            and event_speaker != self_entity\n'
if new in text:
    print("already applied: entity-only direct question model guard")
elif old in text:
    path.write_text(text.replace(old, new, 1))
    print("applied: entity-only direct question model guard")
else:
    raise SystemExit("repair anchor missing: entity-only direct question model guard")
