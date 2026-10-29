#!/usr/bin/env python3
"""World actions are witnessed, not inserted as fake speech."""
from __future__ import annotations
from room_world_actions import action_consequence

cases = (
    ("garden-irrigation", "sarah", "I check the pressure gauge.", "20 kPa"),
    ("garden-irrigation", "jules", "I tighten the hose connector.", "recede"),
    ("flea-market-radio", "mara", "I flip the AM switch.", "spoken broadcast"),
    ("flea-market-radio", "owen", "I turn the tuning knob.", "indistinct voice"),
    ("lantern-festival", "mara", "I check the breaker.", "tripped"),
    ("lantern-festival", "jules", "I reset the breaker.", "row of lanterns"),
    ("library-exhibit", "sarah", "I inspect the photograph frame.", "1934"),
    ("rainwater-tank", "owen", "I inspect the gutter.", "leaves"),
)
# Actual cycle-36303 speech was silently ignored by the earlier parser.
# An adverb does not turn an already-completed physical act into a plan.
assert "quieter" in action_consequence(
    "choir-recording", "mara",
    "I just moved the microphone cable, and it's now lying in a different location, but I'm not sure if that's going to make a difference.")["effect"]
assert action_consequence("choir-recording", "mara",
                          "I already moved the microphone cable.")["action"] == "move"
for proposed in ("I'm going to move the microphone cable.",
                 "I'll move the microphone cable.",
                 "I just could move the microphone cable.",
                 "I might just move the microphone cable.",
                 "I just imagined moving the microphone cable."):
    assert action_consequence("choir-recording", "mara", proposed) is None, proposed

assert action_consequence("greenhouse-watering", "jules", "I check the irrigation filter.")["action"] == "inspect"
assert action_consequence("greenhouse-watering", "owen", "I checked the irrigation filter.")["object"] == "irrigation filter"
assert action_consequence("greenhouse-watering", "jules", "I could check the irrigation filter.") is None
for scene, actor, spoken, expected in cases:
    observed = action_consequence(scene, actor, spoken)
    assert observed is not None, (scene, spoken)
    assert expected in observed["effect"], observed
    assert observed["actor"] == actor and observed["scene"] == scene

for spoken in (
    "What if I check the pressure gauge?",
    "I could check the pressure gauge.",
    "Mara checked the pressure gauge.",
    "I think about checking the pressure gauge.",
    "Someone said: I check the pressure gauge.",
    "I check the pressure gauge?",
):
    assert action_consequence("garden-irrigation", "sarah", spoken) is None, spoken
assert action_consequence("garden-irrigation", "allen", "I check the pressure gauge.") is None
assert action_consequence("flea-market-radio", "jules", "I check the pressure gauge.") is None
assert action_consequence("choir-recording","jules", "I just checked the mixer's power cable.")["object"]=="mixer power cable"
assert "mixer end" in action_consequence("choir-recording","jules", "I checked the mixer's power cable.")["effect"]
assert "nearly closed" in action_consequence("greenhouse-watering","jules", "I took a closer look at the valve itself.")["effect"]
assert action_consequence("greenhouse-watering","jules", "I'm going to take a closer look at the valve itself.") is None
assert action_consequence("greenhouse-watering","jules",
    "I inspected the irrigation filter, but it might still be clogged.")["object"]=="irrigation filter"
assert action_consequence("greenhouse-watering","jules",
    "I might inspect the irrigation filter, but I haven't done it.") is None
print("PASS: witnessed first-person actions yield distinct fictional consequences; hypotheticals do not")

import os
from unittest.mock import patch
from room_chat_speech import messages
from room_hidden_world import GROUNDING_ONSET, GROUNDING_SECOND_ONSET
payload = {
    "entity": "mara", "profile": {}, "room_cycle": GROUNDING_SECOND_ONSET+1,
    "context": [{"speaker":"sarah","text":"I check the breaker."}],
}
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1", "ROOM_WORLD_ACTIONS":"1"}):
    with_feedback = messages(payload,"mara")
assert "SIMULATED ENVIRONMENT RESPONSE" in with_feedback[1]["content"]
assert "tripped" in with_feedback[1]["content"]
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1", "ROOM_WORLD_ACTIONS":"0"}):
    no_feedback = messages(payload,"mara")
assert "SIMULATED ENVIRONMENT RESPONSE" not in no_feedback[1]["content"]
not_an_action = dict(payload, context=[{"speaker":"sarah","text":"What if I check the breaker?"}])
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1", "ROOM_WORLD_ACTIONS":"1"}):
    hypothetical = messages(not_an_action, "mara")
assert "SIMULATED ENVIRONMENT RESPONSE" not in hypothetical[1]["content"]
visitor = dict(payload, context=[{"speaker":"allen","text":"I check the pressure gauge."}])
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1", "ROOM_WORLD_ACTIONS":"1"}):
    visitor_reply = messages(visitor, "mara")
assert "SIMULATED ENVIRONMENT RESPONSE" not in visitor_reply[1]["content"]
print("PASS: optional speech-linked environment effects never fabricate actions, speech, or visitor facts")

with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT":"1", "ROOM_WORLD_ACTIONS":"1"}):
    earlier_phase = messages(dict(payload,room_cycle=GROUNDING_ONSET+1), "mara")
assert "SIMULATED ENVIRONMENT RESPONSE" not in earlier_phase[1]["content"]

with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1', 'ROOM_WORLD_ACTIONS':'1'}):
    later_phase = messages(dict(payload, room_cycle=GROUNDING_SECOND_ONSET+13), 'mara')
assert 'SIMULATED ENVIRONMENT RESPONSE' not in later_phase[1]['content']
