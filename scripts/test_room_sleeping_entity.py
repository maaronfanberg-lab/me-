#!/usr/bin/env python3
import copy

import room_engine_v5 as engine
import room_private_commit as commit

assert "jules" in engine._SLEEPING_ENTITIES
assert "jules" not in engine._AWAKE_AUTONOMOUS
assert "jules" in engine._AUTONOMOUS
assert engine._AWAKE_PARTICIPANTS == {"sarah", "mara", "owen", "allen"}

assert "jules" in commit.SLEEPING_ENTITIES
assert commit.AWAKE_ORDER == ("sarah", "mara", "owen")
assert "jules" in commit.c.ORDER

# Sleeping means no new model generation for Jules.
assert engine._llama_model_run("expression", {"entity": "jules"}, timeout=1) is None

# Awake participants cannot select or target Jules while she is asleep.
minds = commit.c.fresh_minds()
topic = commit.c.fresh_state().get("topic_episode") or {}
for cycle in range(1, 40):
    for entity in commit.AWAKE_ORDER:
        assert engine._awake_choose_partner(entity, minds, topic, cycle) in commit.AWAKE_ORDER

plans = commit.c.plan_actions(list(commit.AWAKE_ORDER), "jules", minds, topic, 1)
assert set(plans) == {"sarah", "mara", "owen"}
assert all(plan["target"] in commit.AWAKE_ORDER for plan in plans.values())
assert all(plan["target"] != "jules" for plan in plans.values())

# Jules' private state is frozen while asleep, so she cannot observe new turns.
snapshot = copy.deepcopy(minds["entities"]["jules"])
minds["entities"]["jules"]["last_event"] = "new-event"
minds["entities"]["jules"]["room_memories"].append({"text": "should disappear"})
commit._restore_sleeping_minds(minds, {"jules": snapshot})
assert minds["entities"]["jules"] == snapshot

print("PASS: Jules is asleep, hidden from awake participants, and receives no new private state")
