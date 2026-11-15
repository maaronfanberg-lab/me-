#!/usr/bin/env python3
"""Non-omniscient follow-up experiment and persistent shared consequences.

Run with Python's assert enabled; all fixtures are synthetic, never production data.
"""
from __future__ import annotations

import os
import json
from unittest.mock import patch
import room_hidden_world as h
from room_chat_speech import messages
from room_world_actions import action_consequence

start = h.FOLLOWUP_START
assert h.followup_active(start)
assert h.followup_active(h.FOLLOWUP_END - 1)
assert not h.followup_active(h.FOLLOWUP_END)
assert not h.followup_active(h.REPLICATION_END)
assert not h.followup_active(True)
assert h.scene_for_cycle(start).identifier == "choir-recording"
assert h.scene_for_cycle(start + 48).identifier == "greenhouse-watering"
assert h.scene_for_cycle(start + 96).identifier == "garden-irrigation"
assert h.scene_for_cycle(start + 144).identifier == "library-exhibit"
for onset in range(start, h.FOLLOWUP_END, h.FOLLOWUP_SCENE_TURNS):
    assert h.event_at(onset)
    assert not h.event_at(onset + 1)
    assert h.active_scene_window(onset + 35)
    assert not h.active_scene_window(onset + 36)

# Each character knows only their own clue. Context must not invent a group memory.
for cycle in (start, start + 48):
    for speaker in h.PARTICIPANTS:
        private = h.context_for(speaker, cycle)
        assert h.private_observation(speaker, cycle) in private
        for other in h.PARTICIPANTS:
            if other != speaker:
                assert h.private_observation(other, cycle) not in private

def turn(speaker, text, cycle, ident):
    return {"speaker": speaker, "text": text, "id": ident,
            "beat_id": "beat-fixture-%06d" % cycle}

spoken = [
    turn("sarah", "I saw the microphone cable lying across a mains power adapter.", start + 1, "s1"),
    turn("mara", "I think the problem needs discussion.", start + 2, "m2"),
    turn("owen", "I move the microphone cable.", start + 3, "o3"),
    turn("jules", "I could move the microphone cable.", start + 4, "j4"),
    turn("allen", "I push the input plug.", start + 5, "a5"),
]
assert h.public_scene_ledger(start + 2, spoken) == []
assert {e["source_id"] for e in h.public_scene_ledger(start + 6, spoken)} == {"s1", "o3"}
effects = h.scene_action_ledger(start + 6, spoken)
assert len(effects) == 1 and effects[0]["source_id"] == "o3"
assert "quieter" in effects[0]["effect"]
shared = h.scene_common_ground(start + 6, spoken)
assert "Sarah said:" in shared and "Owen acted;" in shared
assert h.private_observation("jules", start) not in shared
assert "Jules said:" not in shared and "Allen acted;" not in shared
# A question with an unsupported presupposition cannot turn into a fact
# simply by sharing two nouns with the asker's private observation.
false_premise = turn("owen",
    "I'm curious, Mara, did you notice anything unusual when you moved the microphone cable?",
    start + 7, "o7")
jules_report = turn("jules",
    "I just noticed the input plug was only halfway inserted.",
    start + 8, "j8")
source_entries = h.public_scene_ledger(start + 9, [false_premise, jules_report])
assert {e["source_id"] for e in source_entries} == {"j8"}, source_entries
assert source_entries[0]["evidence_status"] == "firsthand_report"
assert "when you moved the microphone cable" not in h.scene_common_ground(start + 9, [false_premise, jules_report])

assert h.scene_action_ledger(start + 48, spoken) == []
assert h.scene_common_ground(start + 48, spoken) == ""

# The second scene's action is distinct from the first; hypothetical actions do nothing.
assert action_consequence("greenhouse-watering", "jules", "I open the supply valve.")["effect"].startswith("Water")
assert action_consequence("greenhouse-watering", "owen", "I inspect the irrigation filter.")["object"] == "irrigation filter"
assert action_consequence("greenhouse-watering", "jules", "What if I open the supply valve?") is None
assert action_consequence("choir-recording", "jules", "I open the supply valve.") is None

payload = {"entity": "mara", "profile": {}, "room_cycle": start + 6,
           "context": [{"speaker": "owen", "text": "I move the microphone cable.", "id": "o3"}]}
flags = {"ROOM_HIDDEN_WORLD_EXPERIMENT": "1", "ROOM_WORLD_ACTIONS": "1",
         "ROOM_SCENE_PUBLIC_LEDGER": "1"}
with patch.dict(os.environ, flags):
    with patch("pathlib.Path.read_text", return_value=json.dumps({"conversation": spoken})):
        rendered = messages(payload, "mara")
assert "ONGOING FICTIONAL SITUATION" in rendered[1]["content"]
assert "SIMULATED ENVIRONMENT RESPONSE" in rendered[1]["content"]
assert "CLAIMS SPOKEN ALOUD" in rendered[1]["content"]
assert "electrical buzz" in rendered[1]["content"]
assert "PHYSICAL OPTIONS" in rendered[1]["content"]
assert "an action happens when you" in rendered[1]["content"]
offered = rendered[1]["content"].split("PHYSICAL OPTIONS IN THE FICTIONAL SETTING", 1)[1]
assert "I move the microphone cable" not in offered  # Owen already did this.
assert "I check the mixer power cable" in offered
assert "I check the mixer power cable" in rendered[1]["content"]
assert "I push the input plug" in rendered[1]["content"]
from room_world_actions import available_actions
assert "I move the microphone cable" in available_actions("choir-recording")
assert "I move the microphone cable" not in available_actions("choir-recording",completed={("move","microphone cable")})
assert "I push the input plug" in available_actions("choir-recording",completed={("move","microphone cable")})
assert "I move the microphone cable" in available_actions("choir-recording",completed={("open","supply valve")})
assert h.private_observation("jules", start) not in rendered[1]["content"]
assert h.private_observation("sarah", start) not in rendered[0]["content"]

visitor = dict(payload, context=[{"speaker": "allen", "text": "Can you help me with something else?", "id": "visitor"}])
with patch.dict(os.environ, flags):
    with patch("pathlib.Path.read_text", return_value=json.dumps({"conversation": spoken})):
        reply = messages(visitor, "mara")
assert "ONGOING FICTIONAL SITUATION" not in reply[1]["content"]
assert "SIMULATED ENVIRONMENT RESPONSE" not in reply[1]["content"]
assert "CLAIMS SPOKEN ALOUD" not in reply[1]["content"]
assert "PHYSICAL OPTIONS" not in reply[1]["content"]

# No indefinite topic lock after the finite trial, even when flags are on.
with patch.dict(os.environ, flags):
    after = messages(dict(payload, room_cycle=h.FOLLOWUP_END), "mara")
assert "ONGOING FICTIONAL SITUATION" not in after[1]["content"]
assert "CLAIMS SPOKEN ALOUD" not in after[1]["content"]
print("PASS: bounded scene succession, distinct private clues, durable witnessed actions and visitor priority")
