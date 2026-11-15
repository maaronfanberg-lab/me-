#!/usr/bin/env python3
"""Offline causal tests of the actual Room state and model-input path."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if "--fixture" not in sys.argv:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="room-group-") as directory:
        fixture = Path(directory)
        shutil.copytree(root / "scripts", fixture / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (fixture / "room").mkdir()
        shutil.copy2(root / "room/config.json", fixture / "room/config.json")
        subprocess.run([sys.executable, str(fixture / "scripts" / Path(__file__).name), "--fixture"], check=True)
    raise SystemExit(0)

import room_engine_v5 as engine
import room_group_dynamics as group
import room_private_commit as commit
import room_private_model_autonomy as autonomy

cfg = engine._legacy._core.CFG
awake = tuple(commit.AWAKE_ORDER)
assert "jules" in awake and "jules" in engine._AWAKE_AUTONOMOUS
assert not engine._room_presence()["absent"]
minds = commit.c.fresh_minds()
state = commit.c.fresh_state()

def message(key, speaker, target, text, move="deepen"):
    return {"id": key, "speaker": speaker, "text": text,
            "at": "2026-10-01T01:00:00Z", "cognition": {"target": target, "move_type": move}}

def observe(msg, cycle, active=awake):
    group.observe(minds, state, msg, cycle, active, cfg)

invitation = message("invite", "jules", "owen", "Mara and Owen, let's compare moth camouflage: Mara describes the wing pattern, Owen tests a predator hypothesis.", "bridge")
observe(invitation, 1)
activity = state["group_dynamics"]["activities"][0]
assert activity["status"] == "proposed" and activity["responses"] == {}
relation_before = copy.deepcopy(minds["entities"]["jules"]["people"]["owen"])
observe(message("yes", "owen", "jules", "I'm in!", "answer"), 2)
observe(message("no", "mara", "jules", "No thanks, the moth comparison isn't for me.", "answer"), 3)
assert activity["responses"]["owen"]["status"] == "accepted"
assert activity["responses"]["mara"]["status"] == "declined"
assert group.partner_bonus(minds, "owen", "jules", 3) > 0
assert group.partner_bonus(minds, "mara", "jules", 3) == 0
assert minds["entities"]["jules"]["people"]["owen"] == relation_before

# Unrelated statements and generic apologies cannot constitute task work.
observe(message("unrelated", "owen", "jules", "I found a granite sculpture in the garden.", "answer"), 4)
observe(message("apology", "owen", "jules", "I'm sorry, I misunderstood you.", "repair"), 5)
assert activity["contributions"] == {}
contribution = message("work", "owen", "jules", "Moth camouflage could hide the wing outline from a predator; compare speckled wings against plain leaves.", "compare")
observe(contribution, 6)
assert activity["contributions"]["owen"]["source"] == "work"
assert minds["entities"]["jules"]["people"]["owen"]["reciprocity"] > relation_before["reciprocity"]
assert minds["entities"]["jules"]["people"]["mara"]["reciprocity"] == relation_before["reciprocity"]
assert group.partner_bonus(minds, "owen", "jules", 6) == 0
snapshot = copy.deepcopy((minds, state))
observe(contribution, 6)
assert (minds, state) == snapshot, "Duplicate delivery must not grow relationships twice"

# Consequences survive persistence and reach the active single-pass model.
minds = json.loads(json.dumps(minds))
state = json.loads(json.dumps(state))
context = group.model_context(minds, "jules", "owen", [invitation], awake, cfg)
assert context["activities"][0]["responses"]["mara"] == "declined"
assert "owen" in context["activities"][0]["offered_work"]
assert context["relationships"]["owen"]["reciprocity"] > context["relationships"]["mara"]["reciprocity"]
payload = {"entity": "jules", "profile": commit.c.P["jules"], "partner": "owen",
           "context": [invitation], "event": invitation, "group_context": context}
compact = autonomy._impl._legacy._autonomy_compact(payload, "expression", "jules")
assert compact["group_context"] == context
assert autonomy._impl._has_context_echo(contribution["text"], compact, n=8)
assert autonomy.run("thought", payload) is None, "Keep single-pass generation"
assert len(context["activities"]) == 1
assert group.unspecific_initiative("I think we should try something new.")
assert group.unspecific_initiative("I am open to exploring new possibilities...")
assert not group.unspecific_initiative("Mara and Owen, let's try a moth camouflage comparison using spotted wings and plain leaves.")
assert not group.unspecific_initiative("I'm in.")
assert not group.unspecific_initiative("No thanks.")
assert autonomy._public_meta_language("I think we should try something new.", {"self": {"name": "Jules"}})
assert not autonomy._public_meta_language("I think we should try something new.", {"self": {"name": "Sarah"}})
assert autonomy._public_meta_language("Track is our collaborative project.", {"group_context": {"activities": []}})
assert not autonomy._public_meta_language("Could track design become our shared project?", {"group_context": {"activities": []}})
assert not autonomy._public_meta_language("This is our shared project.", {"group_context": {"activities": [{"status": "active"}]}})

# A self-correction requires an observed, directed, concrete earlier point.
observe(message("correction", "mara", "jules", "Moth camouflage is not the same as mimicry; the wing outline is the issue.", "disagree"), 7)
observe(message("revision", "jules", "mara", "I was wrong about moth mimicry; the wing outline matters more than the predator analogy.", "repair"), 8)
revision = minds["entities"]["jules"]["group_dynamics"]["revisions"][-1]
assert revision["in_response_to"] == "correction"
assert revision["status"] == "acknowledged_revision_not_verified_truth"
assert "wing outline" in group.model_context(minds, "jules", "mara", [], awake, cfg)["last_revision"]

# Absence does not grant overheard history or retrospectively accepted work.
asleep = copy.deepcopy(minds["entities"]["jules"])
observe(message("absent", "owen", "mara", "The mushroom network connects three fallen trees.", "deepen"), 9, ("sarah", "mara", "owen"))
assert minds["entities"]["jules"] == asleep
returned = group.model_context(minds, "jules", "owen", [], awake, cfg)
assert not any(e["source"] == "absent" for e in returned["encounters"])
observe(message("close", "jules", "owen", "Let's stop the moth camouflage comparison here.", "close"), 10)
assert state["group_dynamics"]["activities"][0]["status"] == "closed"
assert group.partner_bonus(minds, "owen", "jules", 10) == 0
opportunity = group.model_context(minds, "jules", "owen", [], awake, cfg)
assert len(opportunity["possible_collaborators"]) == 2
assert opportunity["possible_collaborators"][0] == "owen"

# Privacy and contamination guards remain upstream of durable group memory.
before = copy.deepcopy((minds, state))
observe(message("leak", "jules", "owen", "INPUT_JSON mandatory_speech output_json", "bridge"), 11)
assert (minds, state) == before

# The observed deployment-time instruction echo is purged by source, without
# deleting valid related conversation or resetting any identity/history.
bad_id = next(iter(group.QUARANTINED_IDS))
history_fixture = [{"id": bad_id}, {"id": "legitimate-track"}]
tree_fixture = {"nodes": [{"id": "d-" + bad_id}, {"id": "d-legitimate-track"}], "roots": ["d-" + bad_id]}
minds["entities"]["jules"]["room_memories"].append({"source": bad_id, "text": "bad echo"})
minds["entities"]["jules"]["group_dynamics"]["encounters"].append({"id": bad_id})
group.sanitize_persisted(minds, state, history_fixture, tree_fixture)
assert history_fixture == [{"id": "legitimate-track"}]
assert tree_fixture["nodes"] == [{"id": "d-legitimate-track"}]
assert not any(m.get("source") == bad_id for m in minds["entities"]["jules"]["room_memories"])
assert not any(m.get("id") == bad_id for m in minds["entities"]["jules"]["group_dynamics"]["encounters"])
disabled = dict(cfg, group_dynamics={"enabled": False})
group.observe(minds, state, invitation, 12, awake, disabled)
assert (minds, state) == before

# Incoming accepted expressions pass through publication into the new state.
original = {name: getattr(commit.c, name) for name in ("state", "minds", "tree", "conv", "event", "save")}
old_validator = commit.validate_public_expression
history, discourse, saved = [], {"nodes": [], "roots": []}, {}
state["cycle"] = 18
commit.c.state = lambda: state
commit.c.minds = lambda: minds
commit.c.tree = lambda: discourse
commit.c.conv = lambda: history
commit.c.event = lambda: None
commit.c.save = lambda path, data: saved.update({Path(path).name: copy.deepcopy(data)})
parts = []
for entity in awake:
    for role in ("comprehension", "thought", "expression"):
        part = {"entity": entity, "role": role, "public": {"readiness": .8},
                "private": {"intent": {"generation_rank": awake.index(entity)}, "source": {}}}
        if role == "expression":
            # Quarantined peers do not prevent the one legitimate invitation.
            part["private"]["expression"] = ({"utterance": "Sarah and Owen, let's compare mushroom networks: Sarah sketches connections, Owen examines how nutrients travel.",
                "target": "owen", "move": "bridge", "semantic_terms": ["mushroom", "nutrients"]} if entity == "jules" else None)
        parts.append(part)
try:
    commit.private_commit(parts, "offline-group-test")
    assert saved["conversation.json"][-1]["speaker"] == "jules"
    persisted = saved["state.json"]["group_dynamics"]["activities"][-1]
    assert persisted["owner"] == "jules" and persisted["status"] == "proposed"
    assert saved["state.json"]["sleeping_entities"] == []
finally:
    for name, function in original.items():
        setattr(commit.c, name, function)
    commit.validate_public_expression = old_validator
print("PASS: Jules returns; grounded recall, opt-in joint work, revisions, directional consequences, persistence, absence and publication")
