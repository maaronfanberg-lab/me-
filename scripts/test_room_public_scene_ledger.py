#!/usr/bin/env python3
"""Common-ground ledger stores actual public speech, not omniscient scene cards."""
import os, json
from unittest.mock import patch
from room_hidden_world import (
    REPLICATION_START, LEDGER_ONSET, REPLICATION_END, public_scene_ledger,
    scene_common_ground, private_observation,
)
from room_chat_speech import messages

def line(speaker,text,beat,ident):
    return {"speaker":speaker,"text":text,"beat_id":f"beat-test-{beat:06d}",
            "id":ident}

turns = [
    line("owen", "I noticed the rainfall log only records rain on three consecutive days.",
         REPLICATION_START+1,"o-1"),
    line("sarah", "There's a puddle beside the tank's lower outlet.",
         REPLICATION_START+2,"s-2"),
    line("mara", "What if the open lid has been left that way for two days?",
         REPLICATION_START+3,"m-3"),
    line("jules", "We should stop talking about narrative structure.",
         REPLICATION_START+4,"j-4"),
    line("allen", "I saw a gutter with leaves in it.",
         REPLICATION_START+5,"allen-5"),
    line("jules", "I saw that the gutter and downpipe were blocked by wet leaves.",
         REPLICATION_START-1,"old-1"),
]
assert public_scene_ledger(LEDGER_ONSET-1, turns) == []
ledger = public_scene_ledger(LEDGER_ONSET,turns)
assert {e["speaker"] for e in ledger} == {"owen","sarah"}, ledger
assert all(e["source_id"] in {"o-1","s-2"} for e in ledger)
assert "gutter" not in scene_common_ground(LEDGER_ONSET,turns).lower()
assert "rainfall log" in scene_common_ground(LEDGER_ONSET,turns).lower()
assert "puddle" in scene_common_ground(LEDGER_ONSET,turns).lower()
assert "narrative structure" not in scene_common_ground(LEDGER_ONSET,turns)
assert "What if the open lid" not in scene_common_ground(LEDGER_ONSET,turns)
assert "NOT INDEPENDENTLY VERIFIED" in scene_common_ground(LEDGER_ONSET,turns)
assert public_scene_ledger(REPLICATION_END,turns) == []
assert private_observation("jules",LEDGER_ONSET) not in scene_common_ground(LEDGER_ONSET,turns)

payload = {
    "entity":"jules", "profile":{}, "room_cycle":LEDGER_ONSET,
    "context":[{"speaker":"owen","text":"Can anyone check that tank?"}],
}
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1","ROOM_SCENE_PUBLIC_LEDGER":"1"}):
    with patch("pathlib.Path.read_text",return_value=json.dumps({"conversation":turns})):
        m=messages(payload,"jules")
assert "PREVIOUSLY SPOKEN PUBLIC OBSERVATIONS" in m[1]["content"]
assert "Owen said:" in m[1]["content"]
assert "Jules said:" not in m[1]["content"]
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1","ROOM_SCENE_PUBLIC_LEDGER":"0"}):
    m=messages(payload,"jules")
assert "PREVIOUSLY SPOKEN PUBLIC OBSERVATIONS" not in m[1]["content"]
visitor=dict(payload,context=[{"speaker":"allen","text":"Please help me with something else."}])
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1","ROOM_SCENE_PUBLIC_LEDGER":"1"}):
    with patch("pathlib.Path.read_text",return_value=json.dumps({"conversation":turns})):
        m=messages(visitor,"jules")
assert "PREVIOUSLY SPOKEN PUBLIC OBSERVATIONS" not in m[1]["content"]
print("PASS: common-ground ledger is public-only, actor-bound, cycle-bound, visitor-safe")


# Actual Room 36425-36434 regression: several characters repeated a claimed
# 2015 stamp while Sarah physically inspected the frames. Keep the model's
# deterministic 1934 observation distinguishable from Owen's spoken 2015.
museum = [
    line("owen", 'I notice that the date embossed on the frame is "2015", and it is definitely older than the two photographs on display.', 36432, "live-36432"),
    line("sarah", "I take a closer look at the photograph frames and notice that the one with the older typeface on the storefront sign has a thin layer of dust coating the frame's edges, whereas the other frame is spotless.", 36426, "live-36426"),
]
common = scene_common_ground(36434, museum)
assert "SOURCE-LINKED SIMULATED ENVIRONMENT CONSEQUENCES" in common
assert "PUBLIC CHARACTER CLAIMS (NOT INDEPENDENTLY VERIFIED)" in common
assert "Sarah acted [live-36426]" in common
assert "1934" in common and '"2015"' in common
assert common.index("1934") < common.index('"2015"'), common
assert "[source live-36432]" in common
print("PASS: conflicting live photograph dates retain independent source provenance")
