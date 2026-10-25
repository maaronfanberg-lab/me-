#!/usr/bin/env python3
"""Isolated Room full pipeline and lexical-repair tests; never mutate live state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if "--fixture" not in sys.argv:
    original = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="room-floor-integration-") as tmp:
        work = Path(tmp)
        shutil.copytree(original / "scripts", work / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (work / "room").mkdir()
        shutil.copy2(original / "room" / "config.json", work / "room" / "config.json")
        environment = dict(os.environ)
        environment["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        environment.pop("GITHUB_TOKEN", None)
        environment.pop("GH_TOKEN", None)
        subprocess.run([sys.executable, str(work / "scripts" / Path(__file__).name), "--fixture"],
                       env=environment, check=True, timeout=60)
    print("PASS: isolated Room one-turn full commit, legacy rejection and lexical repair")
    raise SystemExit(0)

import room_engine_v5_core as core
import room_expression_quality as quality
import room_private_commit as commit

# The new path must preserve a deliberate echo, even if it might also be
# used for a repair: prohibiting repeated words is not a conversation model.
repeated = "Trees? Trees?"
assert quality.repair_expression(repeated, "sarah") == repeated
assert quality.quality_issue("Right.", {"context": []}, "sarah", core._sim) is None
assert quality.quality_issue("Can you clarify?", {"context": []}, "sarah", core._sim) is None
assert quality.quality_issue("Right.", {"context": []}, "sarah", core._sim) is None

# We also require the original validation path to remain available.
os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
assert quality.quality_issue("Right.", {"context": []}, "sarah", core._sim) == "empty_fragment"
os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"

parts_root = core.PARTS
parts_root.mkdir(exist_ok=True)
core.WORK.mkdir(exist_ok=True)
node_ids = [i for i in range(12) if i % 3 != 2] + [2]
for node in node_ids:
    entity, _local, role, _tasks = core.ni(node)
    part = {"node": node, "entity": entity, "role": role,
            "private": {"source": {"event": None}, "deliberation": None},
            "public": {"node": node, "entity": entity, "role": role}}
    if node == 2:
        part["private"] = {
            "intent": {"readiness": 0.7, "latency": 0.3, "generation_rank": 0,
                       "mandatory_speech": False},
            "expression": {"decision": "SPEAK", "target": "mara",
                           "move": "deepen", "utterance":
                               "That oak tree near the garden has a hollow branch where moths settle at dusk.",
                           "semantic_terms": ["oak", "moths"]},
        }
    core.save(parts_root / f"recurrent-{node:02d}.json", part)
core.save(core.WORK / "floor.json", {
    "speaker": "sarah", "node": 2, "reason": "voluntary_relevance",
    "source_id": None, "source_speaker": "",
})

# The core's public commit CLI requires the nine-node contract.
assert len(node_ids) == 9
sys.argv = ["room_private_commit.py", "commit"]
core.commit = commit.private_commit
core.main()
conversation = json.loads((core.ROOM / "conversation.json").read_text())
state = json.loads((core.ROOM / "state.json").read_text())
assert len(conversation) == 1, conversation
assert conversation[0]["speaker"] == "sarah"
assert conversation[0]["text"].startswith("That oak tree")
assert state["cycle"] == 1
assert state["beat_message_count"] == 1
assert state["conversational_floor"] == "opportunity_v1"

# The old four-voice path must STILL reject the nine-node input.
os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
try:
    core.main()
except RuntimeError as exc:
    assert "all 12 recurrent nodes" in str(exc)
else:
    raise AssertionError("legacy path accepted a partial beat")
os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"

# Allen is an actual interlocutor, not an entity to redirect to another AI.
# The first version of the selected-only commit mistakenly discarded Allen
# as the expression target; this is a publication regression fixture.
reply_part = core.load(parts_root / "recurrent-02.json", {})
reply_part["private"]["expression"] = {
    "decision": "SPEAK", "target": "allen", "move": "answer",
    "utterance": "Allen, I think those moths really do gather under the oak tree.",
    "semantic_terms": ["moths", "oak"],
}
core.save(parts_root / "recurrent-02.json", reply_part)
core.main()
conversation = json.loads((core.ROOM / "conversation.json").read_text())
assert len(conversation) == 2
assert conversation[-1]["cognition"]["target"] == "allen"
assert json.loads((core.ROOM / "state.json").read_text())["cycle"] == 2

# Structural safety must fail if a second expression is incorrectly inserted.
extra = {"node": 5, "entity": "mara", "role": "expression", "private": {
    "intent": {"generation_rank": 1},
    "expression": {"decision": "SPEAK", "utterance": "I heard you."}
}}
core.save(parts_root / "recurrent-05.json", extra)
try:
    core.main()
except RuntimeError as exc:
    assert "eight cognitive nodes plus one expression" in str(exc)
else:
    raise AssertionError("second expression bypassed the selected turn gate")

print("PASS: one selected voice, stored social/cognitive state, and anti-novelty avoidance")
