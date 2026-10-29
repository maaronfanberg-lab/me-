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
    Effect("choir-recording", "check", "mixer power cable",
           "The mixer's power cable is firmly seated, so the buzz is unlikely to be caused by a loose power connection."),
    Effect("choir-recording", "move", "microphone cable",
           "As the microphone lead moves away from the adapter, the electrical buzz becomes noticeably quieter."),
    Effect("choir-recording", "push", "input plug",
           "The mixer input plug clicks fully into place, and the recording's intermittent crackle stops."),
    Effect("greenhouse-watering", "inspect", "irrigation filter",
           "The irrigation filter is clogged with brown sediment."),
    Effect("greenhouse-watering", "open", "supply valve",
           "Water starts flowing along the greenhouse irrigation line."),
)

_VERBS = {
    "check": ("check", "checked", "inspect", "inspected", "look at", "looked at"),
    "tighten": ("tighten", "tightened", "reattach", "reattached"),
    "flip": ("flip", "flipped", "switch", "switched"),
    "turn": ("turn", "turned", "rotate", "rotated"),
    "reset": ("reset",),
    "inspect": ("inspect", "inspected", "check", "checked", "examine", "examined", "look at", "looked at"),
    "move": ("move", "moved", "shift", "shifted"),
    "push": ("push", "pushed", "seat", "seated"),
    "open": ("open", "opened", "turn", "turned"),
}
_OBJECTS = {
    "pressure gauge": ("pressure gauge", "the gauge"),
    "hose connector": ("hose connector", "loose hose", "hose fitting"),
    "am switch": ("am switch", "band switch", "am/fm switch"),
    "tuning knob": ("tuning knob", "tuning dial", "radio dial"),
    "breaker": ("breaker", "breaker panel", "fuse box"),
    "photograph frame": ("photo frame", "photograph frame", "picture frame"),
    "gutter": ("gutter", "downpipe", "downspout"),
    "mixer power cable": ("mixer power cable", "mixer cord", "mixer power cord", "mixer cable"),
    "microphone cable": ("microphone cable", "mic cable", "microphone lead"),
    "input plug": ("input plug", "mixer plug", "input connector"),
    "irrigation filter": ("irrigation filter", "water filter"),
    "supply valve": ("supply valve", "water valve"),
}


def action_consequence(scene: str, speaker: str, utterance: str) -> dict | None:
    """Return grounded fictional effect, or None when action wasn't witnessed."""
    if str(speaker).lower() not in {"sarah", "mara", "owen", "jules"}:
        return None
    text = str(utterance or "").strip()
    # Guard conditional, quoted, or hypothetical utterances and reported speech.
    if not text or text.endswith("?") or len(text) > 500:
        return None
    if re.search(r"\b(?:could|would|should|might|maybe|what if|imagine|hypothetically|pretend)\b",text,re.I):
        return None
    # The first-person performative must occur near the start, not inside an
    # unrelated description of somebody else's actions.
    # Ordinary completed-action speech often contains an aspect adverb:
    # "I just moved the microphone cable." This is a witnessed action;
    # "I'm going to move it" and "I could move it" remain proposals.
    prelude = re.match(
        r"^\s*(?:[A-Za-z]+\s*[:,]\s*)?(?:I|we)\s+(?:just\s+|already\s+|now\s+)?",
        text, re.I)
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


def available_actions(scene: str) -> list[str]:
    """Physical possibilities, not instructions or pretend actions.

    An agent can ignore these, speak, or choose a real first-person action.
    Only the ordinary witnessed-action parser can cause a consequence.
    """
    return ["I " + effect.action + " the " + effect.object
            for effect in _EFFECTS if effect.scene == scene]
