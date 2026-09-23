#!/usr/bin/env python3
import copy

import room_engine_v5 as engine
import room_private_commit as commit

assert "jules" in engine._SLEEPING_ENTITIES
assert "jules" not in engine._AWAKE_AUTONOMOUS
assert "jules" in engine._AUTONOMOUS
assert "jules" in engine._social.PARTICIPANTS

assert "jules" in commit.SLEEPING_ENTITIES
assert commit.AWAKE_ORDER == ("sarah", "mara", "owen")
assert "jules" in commit.c.ORDER

# Sleeping means no new model generation for Jules.
assert engine._llama_model_run("expression", {"entity": "jules"}, timeout=1) is None

# Awake participants can still perceive/address Jules as a Room participant.
minds = commit.c.fresh_minds()
topic = commit.c.fresh_state().get("topic_episode") or {}
plans = commit.c.plan_actions(list(commit.AWAKE_ORDER), "jules", minds, topic, 1)
assert set(plans) == {"sarah", "mara", "owen"}
assert all(plan["target"] == "jules" for plan in plans.values())

# Jules' private state is frozen while asleep.
snapshot = copy.deepcopy(minds["entities"]["jules"])
minds["entities"]["jules"]["last_event"] = "new-event"
minds["entities"]["jules"]["room_memories"].append({"text": "should disappear"})
commit._restore_sleeping_minds(minds, {"jules": snapshot})
assert minds["entities"]["jules"] == snapshot

print("PASS: Jules is asleep, remains visible/addressable, and receives no new private state")
