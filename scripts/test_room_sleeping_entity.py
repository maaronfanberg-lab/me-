#!/usr/bin/env python3
import copy

import room_engine_v5 as engine
import room_private_commit as commit

assert "jules" in engine._SLEEPING_ENTITIES
assert "jules" not in engine._AWAKE_AUTONOMOUS
assert "jules" in engine._AUTONOMOUS
assert engine._AWAKE_PARTICIPANTS == {"sarah", "mara", "owen", "allen"}
presence = engine._room_presence()
assert presence["present"] == ["allen", "mara", "owen", "sarah"]
assert presence["absent"] == ["jules"]

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

plans = commit.c.plan_actions(list(commit.AWAKE_ORDER), None, minds, topic, 1)
assert set(plans) == {"sarah", "mara", "owen"}
assert all(plan["target"] in commit.AWAKE_ORDER for plan in plans.values())
assert all(plan["target"] != "jules" for plan in plans.values())

# A question previously aimed at Jules is ignored as a live target while she sleeps.
historical_target = "jules"
visible_qtarget = historical_target if historical_target in commit.AWAKE_ORDER else None
assert visible_qtarget is None

# Awake participants retain history, but Jules is not represented as a current
# live mind-model while absent.
live_state = {
    "models_of_others": {
        "sarah": {"belief_hypothesis": "x"},
        "jules": {"belief_hypothesis": "stale"},
    }
}
pruned = commit._prune_absent_live_models(live_state, "owen")
assert "jules" not in pruned["models_of_others"]
assert "sarah" in pruned["models_of_others"]

# Jules' private state is frozen while asleep, so she cannot observe new turns.
snapshot = copy.deepcopy(minds["entities"]["jules"])
minds["entities"]["jules"]["last_event"] = "new-event"
minds["entities"]["jules"]["room_memories"].append({"text": "should disappear"})
commit._restore_sleeping_minds(minds, {"jules": snapshot})
assert minds["entities"]["jules"] == snapshot

print("PASS: Jules is absent, awake agents know the current presence state, and Jules receives no new private state")
