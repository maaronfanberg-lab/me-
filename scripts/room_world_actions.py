#!/usr/bin/env python3
"""Conservative, optional physical consequences in fictional Room scenes.

A character may *actually do* a small observable action by saying "I check
the pressure gauge" or similar. Only a witnessed, affirmative first-person
action can change the simulated world. We do not invent the character's
action, infer intent from a question, or replace model-generated speech.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Effect:
    scene: str
    action: str
    object: str
    observation: str

_EFFECTS = (
    Effect("garden-irrigation", "check", "pressure gauge",
           "The garden pressure gauge shows low pressure, about 20 kPa."),
    Effect("garden-irrigation", "tighten", "hose connector",
           "Water stops escaping at the loose hose connector; the wet patch begins to recede."),
    Effect("flea-market-radio", "flip", "am switch",
           "A faint spoken broadcast is audible on the radio's AM band."),
    Effect("flea-market-radio", "turn", "tuning knob",
           "An indistinct voice briefly comes through between two music stations."),
    Effect("lantern-festival", "check", "breaker",
           "The warm breaker panel has one switch in its tripped position."),
    Effect("lantern-festival", "reset", "breaker",
           "One row of lanterns comes back on; the music stage is still dark."),
    Effect("library-exhibit", "inspect", "photograph frame",
           "The frame bears a clearly stamped date: 1934."),
    Effect("rainwater-tank", "inspect", "gutter",
           "Wet leaves are blocking the downpipe that fills the tank."),
    Effect("rainwater-tank", "inspect", "outlet valve",
           "A thin trickle runs from the outlet valve into the puddle at the tank base."),
    Effect("rainwater-tank", "check", "rainfall log",
           "The log confirms rain on three days; it gives no evidence that data entries were truncated."),
    Effect("rainwater-tank", "clear", "gutter",
           "The blocked wet leaves are removed from the gutter; water can flow into the tank at the next rainfall."),
    Effect("rainwater-tank", "tighten", "outlet valve",
           "The slow trickle at the tank's outlet stops."),
    Effect("rainwater-tank", "close", "tank lid",
           "The tank lid now seals, although the water level does not instantly rise."),
)

_VERBS = {
    "check": ("check", "checked", "inspect", "inspected", "look at", "looked at"),
    "tighten": ("tighten", "tightened", "reattach", "reattached"),
    "flip": ("flip", "flipped", "switch", "switched"),
    "turn": ("turn", "turned", "rotate", "rotated"),
    "reset": ("reset",),
    "inspect": ("inspect", "inspected", "inspecting", "examine", "examined", "look at", "looked at", "look around", "looking at"),
    "clear": ("clear", "cleared", "remove leaves from", "unblock"),
    "close": ("close", "closed", "shut"),
}
_OBJECTS = {
    "pressure gauge": ("pressure gauge", "the gauge"),
    "hose connector": ("hose connector", "loose hose", "hose fitting"),
    "am switch": ("am switch", "band switch", "am/fm switch"),
    "tuning knob": ("tuning knob", "tuning dial", "radio dial"),
    "breaker": ("breaker", "breaker panel", "fuse box"),
    "photograph frame": ("photo frame", "photograph frame", "picture frame"),
    "gutter": ("gutter", "downpipe", "downspout"),
    "outlet valve": ("outlet valve", "tank outlet", "outlet"),
    "rainfall log": ("rainfall log", "rain log", "rain records"),
    "tank lid": ("tank lid", "lid"),
}


def action_consequence(scene: str, speaker: str, utterance: str) -> dict | None:
    """Return grounded fictional effect, or None when action wasn't witnessed."""
    if str(speaker).lower() not in {"sarah", "mara", "owen", "jules"}:
        return None
    text = str(utterance or "").strip()
    # Guard conditional, quoted, or hypothetical utterances and reported speech.
    if not text or text.endswith("?") or len(text) > 500:
        return None
    # The first-person performative must occur near the start, not inside an
    # unrelated description of somebody else's actions.
    prelude = re.match(
        r"^\\s*(?:[A-Za-z]+\\s*[:,]\\s*)?"
        r"(?:I|we|I'm\\s+going\\s+to|I\\s+am\\s+going\\s+to|"
        r"we're\\s+going\\s+to|we\\s+are\\s+going\\s+to|"
        r"let\\s+me|I\\s+will|we\\s+will)\\s+",
        text, re.I,
    )
    if not prelude:
        return None
    action = text[prelude.end():]
    for effect in _EFFECTS:
        if effect.scene != scene:
            continue
        verbs = _VERBS[effect.action]
        obj = _OBJECTS[effect.object]
        pattern = r"^(?:" + "|".join(re.escape(v) for v in verbs) + r")\s+(?:the\s+|a\s+)?(?:"
        pattern += "|".join(re.escape(o) for o in obj) + r")\b"
        if re.match(pattern, action, flags=re.I):
            return {
                "origin": "observed_fictional_action",
                "actor": speaker.lower(),
                "scene": effect.scene,
                "action": effect.action,
                "object": effect.object,
                "effect": effect.observation,
            }
    return None
