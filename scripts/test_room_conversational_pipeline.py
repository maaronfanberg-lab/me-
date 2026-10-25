#!/usr/bin/env python3
"""Isolated Room full pipeline and lexical-repair tests; never mutate live state."""
from __future__ import annotations

import hashlib
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
        environment["ROOM_FLOOR_DESIRED"] = "1"
        environment["ROOM_FLOOR_FALLBACK_REASON"] = ""
        environment.pop("GITHUB_TOKEN", None)
        environment.pop("GH_TOKEN", None)
        subprocess.run([sys.executable, str(work / "scripts" / Path(__file__).name), "--fixture"],
                       env=environment, check=True, timeout=60)
    print("PASS: isolated Room one-turn full commit, legacy rejection and lexical repair")
    raise SystemExit(0)

import room_engine_v5_core as core
import room_expression_quality as quality
import room_private_commit as commit
from room_conversational_candidate import validate_candidate

# The new path must preserve a deliberate echo, even if it might also be
# used for a repair: prohibiting repeated words is not a conversation model.
repeated = "Trees? Trees?"
assert quality.repair_expression(repeated, "sarah") == repeated
assert quality.quality_issue("No, no, no!", {"context": []}, "sarah", core._sim) is None
assert quality.quality_issue("Can you clarify?", {"context": []}, "sarah", core._sim) is None
assert quality.quality_issue("Right.", {"context": []}, "sarah", core._sim) is None
assert quality.quality_issue("Yes.", {"context": []}, "sarah", core._sim) is None
for fragment in ("This", "That.", "Because", "The", "However."):
    assert quality.quality_issue(fragment, {"context": []}, "sarah", core._sim) == "unfinished_deictic_or_connective", fragment

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
def write_floor(key, source=None):
    os.environ["ROOM_CYCLE_KEY"] = key
    core.save(core.WORK / "bus-recurrent.json", {"key": key})
    digest = hashlib.sha256((core.WORK / "bus-recurrent.json").read_bytes()).hexdigest()
    core.save(core.WORK / "floor.json", {
        "speaker": "sarah", "node": 2, "reason": "open_floor_relevance",
        "source_id": source, "source_speaker": "",
        "cycle_key": key, "bus_sha256": digest,
    })


write_floor("fixture-beat-1")

# The model's broken output is rejected, not published, while a legitimate
# short repair or quote can pass the same structural/epistemic gates.
valid_part = core.load(parts_root / "recurrent-02.json", {})
assert validate_candidate(valid_part, "sarah", [], {}) == valid_part["private"]["expression"]["utterance"]
dangling = json.loads(json.dumps(valid_part))
dangling["private"]["expression"]["utterance"] = "This"
dangling["private"]["expression"]["semantic_terms"] = ["this"]
try:
    validate_candidate(dangling, "sarah", [], {})
except RuntimeError as exc:
    assert "unfinished_deictic_or_connective" in str(exc)
else:
    raise AssertionError("live publisher would allow a dangling one-word utterance")
bad_part = json.loads(json.dumps(valid_part))
bad_part["private"]["expression"]["utterance"] = "I think " * 20
bad_part["private"]["expression"]["semantic_terms"] = ["think"]
try:
    validate_candidate(bad_part, "sarah", [], {})
except RuntimeError as exc:
    assert "sampler_collapse" in str(exc)
else:
    raise AssertionError("extreme generator collapse was accepted")

# The model must not receive the old system-indexed topic three times.
# A local topic record may still be used for storage, but cognition receives
# only actual public contributions and each character's own dispositions.
import room_private_model as base_model
original_msgs, original_conv, original_state, original_model_run = core.msgs, core.conv, core.state, core.model_run
repeat_feed = [
    {"id": "r1", "speaker": "mara", "text": "Category classification trees."},
    {"id": "r2", "speaker": "owen", "text": "Category classification trees again."},
    {"id": "r3", "speaker": "jules", "text": "The classification experiment."},
    {"id": "r4", "speaker": "sarah", "text": "I wonder why this is interesting."},
    {"id": "a5", "speaker": "allen", "text": "Sarah, can you explain what's happening?"},
]
core.msgs = lambda: repeat_feed[:-1]
core.conv = lambda: repeat_feed
core.state = lambda: {"cycle": 13, "topic_episode": {
    "root": "category classification experiment", "current_facet": "classification trees",
    "shared_references": ["trees"], "status": "active"
}}
core.model_run = lambda role, payload: None
try:
    sensed = core.sense(0, "evidence-v1")
    private = sensed["private"]
    assert private["event"]["id"] == "a5"
    assert private["event"]["speaker"] == "allen"
    assert len(private["context"]) == 3
    assert private["keywords"] == []
    assert private["topic"] == {}
    compact = base_model._compact_payload({
        "event": private["event"], "context": private["context"],
        "topic": private["topic"], "keywords": private["keywords"],
    }, "thought", "sarah")
    assert compact["discussion"]["subject"] is None, compact
    assert compact["event"]["text"] == repeat_feed[-1]["text"]
    assert "classification experiment" not in json.dumps(compact.get("discussion"))
finally:
    core.msgs, core.conv, core.state, core.model_run = original_msgs, original_conv, original_state, original_model_run

# All four minds must witness the same durably accepted Allen message, but
# NOT an orchestration/status message or an older topic index.
turns = [
    {"id": "s100", "speaker": "sarah", "text": "The tree looks familiar."},
    {"id": "heartbeat", "speaker": "system", "text": "Runner active."},
    {"id": "allen-101", "speaker": "allen",
     "text": "Mara, can you tell me why you think that?", "runtime": "allen-public"},
]
original_conv, original_state, original_model_run = core.conv, core.state, core.model_run
core.conv = lambda: turns
core.state = lambda: {"cycle": 24, "topic_episode": {
    "root": "category classification experiment", "current_facet": "classification trees",
}}
core.model_run = lambda role, payload: {"participation": "PARTICIPANT", "bids": []}
try:
    for node in (0, 1, 3, 4, 6, 7, 9, 10):
        sensed = core.sense(node, "allen-public-source")
        data = sensed["private"]
        assert data["event"]["id"] == "allen-101", (node, data.get("event"))
        assert data["event"]["text"] == turns[-1]["text"]
        assert data["partner"] == "allen", (node, data.get("partner"))
        assert data["topic"] == {}
        assert [m["id"] for m in data["context"]] == ["s100", "allen-101"]
    turns.append({"id": "mara-102", "speaker": "mara", "text": "Because I saw it."})
    following = core.sense(0, "post-allen")
    assert following["private"]["event"]["id"] == "mara-102"
finally:
    core.conv, core.state, core.model_run = original_conv, original_state, original_model_run

# Full selected-floor action path: public Allen input -> all 12 perceptions
# -> four distinct private deliberations -> addressed floor -> expression.
# This catches the old failure where the selector saw Allen but the language
# model was shown only autonomous messages and a persisted topic attractor.
from room_conversational_floor import choose_next, public_participant_turns, last_participant_source_id
grounded_feed = [
    {"id": "old-1", "speaker": "jules", "text": "Classification trees again."},
    {"id": "sys-2", "speaker": "system", "text": "Internal heartbeat."},
    {"id": "old-3", "speaker": "sarah", "text": "I saw category trees yesterday."},
    {"id": "allen-4", "speaker": "allen",
     "text": "Mara, why did you disagree with Sarah?", "runtime": "public-inbound"},
]
assert [turn["id"] for turn in public_participant_turns(grounded_feed)] == [
    "old-1", "old-3", "allen-4"
]
perceived, expressed = [], []
original_conv, original_state, original_model_run = core.conv, core.state, core.model_run
core.conv = lambda: grounded_feed
core.state = lambda: {"cycle": 16, "topic_episode": {
    "root": "experimental category classification trees", "current_facet": "trees"
}}
def ground_truth_model(role, payload):
    if role == "comprehension":
        perceived.append((payload["entity"], payload["event"]["id"]))
        return {"participation": "PARTICIPANT", "grounding": "ambiguous"}
    if role == "thought":
        assert payload["event"]["id"] == "allen-4", payload
        return {
            "action": "REPAIR" if payload["entity"] == "mara" else "DEEPEN",
            "preferred_partner": "allen", "focus": "Mara's disagreement",
            "new_information_goal": "Clarify Mara's reason",
            "unresolved_thread": "What led to the disagreement?",
        }
    if role == "expression":
        expressed.append(payload)
        return {
            "decision": "SPEAK", "target": "allen", "move": "repair",
            "utterance": "Allen, I disagreed because I interpreted her example differently.",
            "semantic_terms": ["disagreed", "interpreted"]
        }
    raise AssertionError(role)
core.model_run = ground_truth_model
try:
    senses = [core.sense(n, "allen-grounded") for n in range(12)]
    private_bus = core.bus(senses, "allen-grounded")
    thoughts = [core.recurrent(n, "allen-grounded", private_bus) for n in (1, 4, 7, 10)]
    recurrent_bus = core.bus2(private_bus, thoughts, "allen-grounded")
    chosen = choose_next(grounded_feed, recurrent_bus, core.CFG, core.minds())
    assert chosen["speaker"] == "mara", chosen
    assert chosen["reason"] == "addressed_recipient", chosen
    assert chosen["source_id"] == "allen-4"
    assert last_participant_source_id(grounded_feed) == "allen-4"
    output = core.recurrent(chosen["node"], "allen-grounded", recurrent_bus)
    assert output["entity"] == "mara"
    assert output["private"]["expression"]["target"] == "allen"
    assert len(expressed) == 1
    assert expressed[0]["event"]["id"] == "allen-4"
    assert expressed[0]["event"]["text"] == grounded_feed[-1]["text"]
    assert expressed[0]["context"][-1]["id"] == "allen-4"
    assert expressed[0]["topic"] == {}, expressed[0]["topic"]
    assert expressed[0]["deliberation"]["action"] == "REPAIR"
    assert sorted(perceived) == sorted((e, "allen-4") for e in core.ORDER)
finally:
    core.conv, core.state, core.model_run = original_conv, original_state, original_model_run

# Live character motivation must survive the *last* compact-model stage.
# A person with no independent intention would otherwise have only the
# already-repeated public claims to echo. This is their existing self-model,
# not a forced novel topic or a generated motivational script.
import room_private_model_autonomy_legacy as autonomy_legacy
sarah = core.P["sarah"]
jules = core.P["jules"]
fixture = {
    "entity": "sarah", "profile": sarah,
    "event": {"id": "latest", "speaker": "mara",
              "text": "Experimental category trees may be better."},
    "context": [{"id": "latest", "speaker": "mara",
                 "text": "Experimental category trees may be better."}],
    "topic": {}, "relationship": {}, "deliberation": None,
}
rendered = autonomy_legacy._autonomy_compact(fixture, "expression", "sarah")
assert rendered["discussion"]["subject"] is None
assert rendered["self"]["motives"] == sarah["psychology_v2"]["motives"][:2]
assert rendered["self"]["cognitive_style"] == sarah["psychology_v2"]["cognitive_style"]
assert rendered["self"]["topic_mobility"] == sarah["psychology_v2"]["topic_mobility"]
assert "category" not in " ".join(rendered["self"]["motives"]).lower()
other = autonomy_legacy._autonomy_compact(dict(fixture, entity="jules", profile=jules),
                                         "expression", "jules")
assert rendered["self"]["motives"] != other["self"]["motives"]
assert rendered["event"]["text"] == fixture["event"]["text"]

# An authentic expression run must not sneak a synthetic contribution job
# into the model payload, even if the recent vocabulary repeats.
captured = []
original_model_run = core.model_run
core.model_run = lambda role, payload: (
    captured.append((role, payload)) or {
        "decision": "SPEAK", "target": "mara", "move": "disclose",
        "utterance": "I keep coming back to the oak because it matters.",
        "semantic_terms": ["oak"],
    })
try:
    last = {"id": "source", "speaker": "jules",
            "text": "I saw the old oak again.", "cognition": {"target": "mara"}}
    repeated_context = [last] * 8
    source_part = {
        "entity": "sarah", "role": "expression", "private": {
            "event": last, "context": repeated_context,
            "topic": {"root": "old oak", "current_facet": "old oak"},
            "partner": "mara", "relationship": {},
        }, "public": {"readiness": .6},
    }
    observe_part = {"entity": "sarah", "role": "comprehension",
                    "private": {"social_observation": {}}}
    bus_fixture = {
        "private": {"sarah": [source_part, observe_part]},
        "recurrent": {"sarah": {"thought": {"private": {"deliberation": {
            "action": "DISCLOSE", "focus": "personal memory",
            "new_information_goal": "Discuss what I experienced",
            "preferred_partner": "mara",
        }}}}},
    }
    core.recurrent(2, "fixture-no-novelty", bus_fixture)
finally:
    core.model_run = original_model_run
assert len(captured) == 1
assert captured[0][0] == "expression"
payload = captured[0][1]
assert payload["conversation_job"] is None
assert payload["deliberation"]["action"] == "DISCLOSE"
assert "Distinct contribution" not in payload["deliberation"]["new_information_goal"]
assert payload["topic"]["root"] == "old oak"

# Prior expression parts are not allowed to override the latest Allen turn
# on the selected model path. The original API ordering used to append them.
captured.clear()
old_prior = core.prior_expression_messages
core.prior_expression_messages = lambda _node: [
    {"speaker": "jules", "text": "Stale category trees.", "cognition": {"target": "sarah"}}
]
core.model_run = lambda role, payload: (captured.append((role, payload)) or {
    "decision": "SPEAK", "target": "allen", "move": "answer",
    "utterance": "Allen, I can explain what I meant.", "semantic_terms": ["explain"]
})
try:
    last_allen = {"speaker": "allen", "id": "allen-latest",
                  "text": "Sarah, what did you mean?", "cognition": {}}
    source_part["private"]["event"] = last_allen
    source_part["private"]["context"] = [last, last_allen]
    core.recurrent(2, "fixture-allen-context", bus_fixture)
finally:
    core.model_run = original_model_run
    core.prior_expression_messages = old_prior
assert len(captured) == 1
assert captured[0][1]["event"]["id"] == "allen-latest"
assert captured[0][1]["context"][-1]["speaker"] == "allen"


# Cooperative short answers do not have to invent a novel topic term.
# Preflight and final publication now both use clean_terms without grafting
# the system's discussion subject onto an utterance of just "No".
short = json.loads(json.dumps(valid_part))
short["private"]["expression"].update({
    "utterance": "No.", "semantic_terms": ["no"], "move": "answer"
})
assert validate_candidate(short, "sarah", [], {"root": "oak"}) == "No."
short_msg, _ = core.emit("sarah", "answer", "mara", None, None,
                         "No.", "short-beat", 0, {"id": "existing", "root": "oak"}, [])
assert short_msg["cognition"]["topic_terms"] == []

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
assert state["conversational_floor_health"]["active"] is True
assert state["conversational_floor_health"]["fallback_reason"] is None
assert state["conversational_floor_health"]["diagnostic_only"] is True

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
write_floor("fixture-beat-2", conversation[-1]["id"])
core.main()
conversation = json.loads((core.ROOM / "conversation.json").read_text())
assert len(conversation) == 2
assert conversation[-1]["cognition"]["target"] == "allen"
assert json.loads((core.ROOM / "state.json").read_text())["cycle"] == 2

# Reusing the old floor after the public tail changed must not publish.
try:
    core.main()
except RuntimeError as exc:
    assert "stale conversational floor" in str(exc)
else:
    raise AssertionError("out-of-date conversational floor was silently published")
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
