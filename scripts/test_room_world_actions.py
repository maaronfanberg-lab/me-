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
print("PASS: witnessed first-person actions yield distinct fictional consequences; hypotheticals do not")
