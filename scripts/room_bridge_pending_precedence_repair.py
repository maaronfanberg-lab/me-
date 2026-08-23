#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/room_topic_bounded.py')
text = path.read_text()
old = '''def update_topic(topic: dict | None, messages, cycle: int) -> dict:\n    current = _normalize(topic, cycle)\n    shifted = _outside_subject_shift(current, list(messages or []), cycle)\n    if shifted is not None:\n        return shifted\n'''
new = '''def update_topic(topic: dict | None, messages, cycle: int) -> dict:\n    current = _normalize(topic, cycle)\n    # A bridge already marked pending is authoritative. Participant ingress may\n    # redirect an active episode, but it must not clear an exhausted episode's\n    # bridge before the vetted breakout selector gets to run.\n    shifted = None if current.get("bridge_pending") else _outside_subject_shift(current, list(messages or []), cycle)\n    if shifted is not None:\n        return shifted\n'''
if old not in text:
    if new in text:
        print('PASS: bridge-pending precedence repair already applied')
        raise SystemExit(0)
    raise SystemExit('GUARD FAIL: update_topic ingress boundary not found')
path.write_text(text.replace(old, new, 1))
print('PASS: bridge-pending precedence repair applied')
