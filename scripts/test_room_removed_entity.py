#!/usr/bin/env python3
import room_engine_v5 as engine
import room_private_commit as commit

assert "jules" in engine._REMOVED_ENTITIES
assert "jules" not in engine._ACTIVE_AUTONOMOUS
assert engine._ACTIVE_PARTICIPANTS == {"sarah", "mara", "owen", "allen"}

assert "jules" in commit.REMOVED_ENTITIES
assert commit.ACTIVE_ORDER == ("sarah", "mara", "owen")

# A removed participant must be cut off before any model request can happen.
assert engine._llama_model_run("expression", {"entity": "jules"}, timeout=1) is None

print("PASS: Jules is removed from generation and active Room publication")
