#!/usr/bin/env python3
"""Controlled non-omniscient Room experiment. Off unless explicitly enabled.

Participants get one different, source-labelled observation of a fictional
shared situation, *never* the other participants' private observations. This
is not fabricated shared biography and is not an instruction to speak.
"""
from __future__ import annotations

from dataclasses import dataclass

PARTICIPANTS = ("sarah", "mara", "owen", "jules")
EPISODE_TURNS = 60


@dataclass(frozen=True)
class Scene:
    identifier: str
    common: str
    observations: tuple[str, str, str, str]


SCENES = (
    Scene(
        "garden-irrigation",
        "At the community garden, several beds are dry even though the timer ran this morning.",
        (
            "You noticed a wet patch near the north fence, away from the dry beds.",
            "You spoke to the volunteer who says the timer display showed a successful watering.",
            "You noticed the supply pressure gauge reads much lower than last week.",
            "You saw a hose connector hanging loose behind the compost bins.",
        ),
    ),
    Scene(
        "flea-market-radio",
        "A flea-market seller has an old radio that receives music but no spoken broadcasts.",
        (
            "You heard a faint voice when you moved the tuning knob very slowly.",
            "You noticed a small paper label saying that one switch is broken.",
            "You saw that the radio has separate AM and FM bands, and only FM is selected.",
            "You found a folded list of station frequencies beneath the radio.",
        ),
    ),
    Scene(
        "lantern-festival",
        "At a neighborhood lantern festival, the lighting unexpectedly went out before the music started.",
        (
            "You saw one row of lanterns flicker a minute before the others.",
            "You overheard the organizer say the generator fuel was checked at noon.",
            "You noticed a breaker panel was warm but its labels were illegible.",
            "You saw the cable for the music stage had been moved across a footpath.",
        ),
    ),
    Scene(
        "library-exhibit",
        "A small library exhibit has two photographs labeled with the same year despite looking very different.",
        (
            "You noticed the storefront sign in one photo uses a much older typeface.",
            "You read that the exhibit labels were printed from a volunteer's handwritten notes.",
            "You found a date embossed on the frame of one photograph.",
            "You spotted a streetcar in one image that is absent from the other.",
        ),
    ),
    Scene(
        "rainwater-tank",
        "A shared rainwater tank is nearly empty after a rainy week.",
        (
            "You saw a fresh puddle beside the tank's lower outlet.",
            "You heard a neighbor say the lid had been left open for two days.",
            "You checked the rainfall log and found substantial rain on three days.",
            "You noticed that the collection gutter had become blocked with leaves.",
        ),
    ),
)


def scene_for_cycle(cycle: int) -> Scene:
    if isinstance(cycle, bool) or not isinstance(cycle, int) or cycle < 0:
        raise ValueError("cycle must be a nonnegative integer")
    return SCENES[(cycle // EPISODE_TURNS) % len(SCENES)]


def private_observation(entity: str, cycle: int) -> str:
    key = str(entity).strip().lower()
    if key not in PARTICIPANTS:
        raise ValueError("unknown participant")
    return scene_for_cycle(cycle).observations[PARTICIPANTS.index(key)]


def context_for(entity: str, cycle: int) -> str:
    """Optional cue, never an assertion that this fictional event really happened."""
    scene = scene_for_cycle(cycle)
    own = private_observation(entity, cycle)
    return (
        "OPTIONAL FICTIONAL SHARED-WORLD EXERCISE (not real-world evidence): "
        + scene.common
        + "\nPERSONAL OBSERVATION (not shared with other characters): "
        + own
        + "\nThe others have their own observations, which you do not know. "
          "You are free to bring yours up, ask about theirs, disagree or remain on "
          "a more interesting real conversational thread. Do not claim anyone "
          "else already knows your observation. Do not turn the exercise into "
          "a discussion of conversation itself. Never invent shared memories."
    )
