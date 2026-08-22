#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import room_private_commit_liveness_core as bridge

ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads((ROOT / "room" / "state.json").read_text())
MINDS = json.loads((ROOT / "room" / "cognitive_state.json").read_text())
TOPIC = dict(STATE.get("topic_episode") or {})
VOCAB = bridge.episode_previous_vocabulary(TOPIC, MINDS)

report = {
    "topic_episode": {
        key: TOPIC.get(key)
        for key in (
            "id", "root", "current_facet", "focus_turns", "status",
            "bridge_pending", "recent_terms",
        )
    },
    "previous_vocabulary_count": len(VOCAB),
    "previous_vocabulary": VOCAB if len(VOCAB) < 200 else None,
    "previous_vocabulary_recent_50": VOCAB[-50:] if len(VOCAB) >= 200 else None,
    "bridge_pending": TOPIC.get("bridge_pending"),
}
print("LIVE_STATE=" + json.dumps(report, ensure_ascii=False, separators=(",", ":")))

assert VOCAB, "live cognitive_state.json yielded empty previous_vocabulary"
probe = dict(TOPIC)
probe["bridge_pending"] = True
probe["status"] = "ready_to_bridge"
probe["bridge_reason"] = probe.get("bridge_reason") or "regression_probe"
cycle = int(STATE.get("cycle", 0)) + 1

selected = bridge._bridge_safe_new_topic_from_terms(VOCAB[-50:], cycle, probe)
root = selected.get("root")
near_hits = [term for term in VOCAB if bridge._base._bounded_topic._near(root, term)]
print(
    "ASSERT selected_root_not_near_live_vocabulary "
    f"root={root!r} near_hits={near_hits!r} vocabulary_count={len(VOCAB)}"
)
assert root, "bridge selected no root"
assert not near_hits, (
    "bridge selected a seed near live previous_vocabulary: "
    f"root={root!r} near_hits={near_hits!r}"
)

original_breakout = bridge.c.breakout_subject
try:
    contaminated = VOCAB[-1]
    bridge.c.breakout_subject = lambda _key: contaminated
    selected_again = bridge._bridge_safe_new_topic_from_terms(VOCAB[-50:], cycle + 1, probe)
finally:
    bridge.c.breakout_subject = original_breakout

root_again = selected_again.get("root")
near_hits_again = [
    term for term in VOCAB
    if bridge._base._bounded_topic._near(root_again, term)
]
print(
    "ASSERT contaminated_breakout_and_generated_terms_rejected "
    f"contaminated={contaminated!r} root={root_again!r} "
    f"near_hits={near_hits_again!r}"
)
assert root_again, "bridge selected no root after contaminated breakout probe"
assert not near_hits_again, (
    "bridge admitted a seed near live previous_vocabulary after contaminated breakout: "
    f"root={root_again!r} near_hits={near_hits_again!r}"
)

print("PASS live bridge vocabulary regression")
