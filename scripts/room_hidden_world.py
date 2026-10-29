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
TRIAL_START = 35160
TRIAL_END = TRIAL_START + 100
REPLICATION_START = TRIAL_END + 8  # eight unprompted washout turns
REPLICATION_END = REPLICATION_START + 24

# Bounded second trial. Reversible, with unprompted gaps between situations.
FOLLOWUP_START = 36280
FOLLOWUP_SCENE_TURNS = 48
FOLLOWUP_SCENE_IDS = (5, 6, 0, 3)
FOLLOWUP_END = FOLLOWUP_START + FOLLOWUP_SCENE_TURNS * len(FOLLOWUP_SCENE_IDS)
FOLLOWUP_NOTICE_TURNS = 36

def followup_active(cycle: int) -> bool:
    return type(cycle) is int and FOLLOWUP_START <= cycle < FOLLOWUP_END



def trial_active(cycle: int) -> bool:
    """A finite 100-public-beat canary, never an indefinite production mode."""
    return type(cycle) is int and (TRIAL_START <= cycle < TRIAL_END or REPLICATION_START <= cycle < REPLICATION_END or followup_active(cycle))


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
    Scene(
        "choir-recording",
        "At a volunteer choir rehearsal, the recording has an electrical buzz, although the singers sound clear.",
        (
            "You saw the microphone cable lying directly across a mains power adapter.",
            "You noticed the buzz gets louder when the mixer is plugged into the wall.",
            "You heard the buzz briefly disappear when the microphone cable was moved.",
            "You noticed one of the mixer's input plugs is only halfway inserted.",
        ),
    ),
    Scene(
        "greenhouse-watering",
        "In the community greenhouse, seedlings are wilting although the irrigation reservoir is full.",
        (
            "You saw a pool of water collecting beneath the supply valve.",
            "You heard the timer click on but couldn't hear any water moving.",
            "You noticed brown debris caught inside the irrigation filter.",
            "You saw the valve handle is almost perpendicular to the pipe.",
        ),
    ),
)


# A later, independently registered intervention replaces a recurring
# self-referential radio scene with genuinely different shared situations.
# Outside the finite trial, retain the original deterministic scene mapping.
GROUNDING_ONSET = 35200
GROUNDING_SECOND_ONSET = 35220
GROUNDING_WINDOW = 12


def scene_phase(cycle: int) -> tuple[int, int]:
    """(scene index, actual onset) for a trial beat, without agent speech."""
    if followup_active(cycle):
        episode = (cycle - FOLLOWUP_START) // FOLLOWUP_SCENE_TURNS
        return FOLLOWUP_SCENE_IDS[episode], FOLLOWUP_START + episode * FOLLOWUP_SCENE_TURNS
    if REPLICATION_START <= cycle < REPLICATION_END:
        return 4, REPLICATION_START
    if trial_active(cycle) and cycle >= GROUNDING_SECOND_ONSET:
        return 2, GROUNDING_SECOND_ONSET
    if trial_active(cycle) and cycle >= GROUNDING_ONSET:
        return 0, GROUNDING_ONSET
    onset = (cycle // EPISODE_TURNS) * EPISODE_TURNS
    return (cycle // EPISODE_TURNS) % len(SCENES), onset


def event_at(cycle: int) -> bool:
    """Only observed environmental onsets, never a repetitive topic schedule."""
    return trial_active(cycle) and (
        (followup_active(cycle) and (cycle - FOLLOWUP_START) % FOLLOWUP_SCENE_TURNS == 0)
        or cycle == TRIAL_START + 15
        or cycle == GROUNDING_ONSET
        or cycle == GROUNDING_SECOND_ONSET
        or cycle == REPLICATION_START
    )


def scene_for_cycle(cycle: int) -> Scene:
    if isinstance(cycle, bool) or not isinstance(cycle, int) or cycle < 0:
        raise ValueError("cycle must be a nonnegative integer")
    return SCENES[scene_phase(cycle)[0]]


def active_scene_window(cycle: int) -> bool:
    """A short-lived scene to recall, not an indefinite mandatory topic."""
    return trial_active(cycle) and (
        (followup_active(cycle) and
         (cycle - FOLLOWUP_START) % FOLLOWUP_SCENE_TURNS < FOLLOWUP_NOTICE_TURNS)
        or GROUNDING_ONSET <= cycle < GROUNDING_ONSET + GROUNDING_WINDOW
        or GROUNDING_SECOND_ONSET <= cycle < GROUNDING_SECOND_ONSET + 3 * GROUNDING_WINDOW
        or REPLICATION_START <= cycle < REPLICATION_END
    )


def situational_notice(entity: str, cycle: int) -> str:
    """Truthful fictional-world evidence for one agent, not a forged turn."""
    if not active_scene_window(cycle):
        return ""
    scene = scene_for_cycle(cycle)
    return (
        f"ONGOING FICTIONAL SITUATION: {scene.common} "
        f"YOUR OWN OBSERVATION ONLY: {private_observation(entity, cycle)} "
        "No one else has automatically been told your observation. "
        "This notice is an environmental observation, not another person's words. "
        "You can tell the others what you saw, ask something about it, "
        "test an explanation, or respond to a more urgent direct question. "
        "Make your response specific to what is happening, without inventing "
        "another character's memory. You may conclude a problem is solved only "
        "when a witnessed action or observation supports that conclusion."
    )


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


# An independently staged phase of the rainwater replication. No private
# observation ever becomes "shared" just because the coordinator knows it.
LEDGER_ONSET = REPLICATION_START + 12
_LEDGER_STOP = {"someone", "another", "before", "after", "about", "there",
                "would", "could", "which", "their", "these", "those",
                "noticed", "notice", "checked", "saying", "found",
                "whole", "seems", "think", "looks", "really", "other",
                "three", "given", "having"}


def _evidence_words(text: str) -> set[str]:
    import re
    raw = re.findall(r"[a-z]{4,}", str(text or "").lower())
    return {word for word in raw if word not in _LEDGER_STOP}


def public_scene_ledger(cycle: int, public_turns: list[dict]) -> list[dict]:
    """Only actual public statements can be promoted to common-ground notes.

    Use an abbreviated verbatim *public* statement as evidence. Never insert
    another character's private card, even when two words happen to match.
    """
    if followup_active(cycle):
        onset = scene_phase(cycle)[1]
        if cycle < onset + 3 or not active_scene_window(cycle):
            return []
    elif LEDGER_ONSET <= cycle < REPLICATION_END:
        onset = REPLICATION_START
    else:
        return []
    facts = {}
    for turn in public_turns:
        if not isinstance(turn, dict):
            continue
        speaker = str(turn.get("speaker") or "").lower()
        if speaker not in PARTICIPANTS:
            continue
        beat = str(turn.get("beat_id") or "")
        try:
            beat_cycle = int(beat.rsplit("-", 1)[-1])
        except (ValueError, TypeError):
            continue
        if not (onset <= beat_cycle < cycle):
            continue
        actual = str(turn.get("text") or "").strip()
        # A question is evidence that someone ASKED something, not evidence
        # that its presupposition is true. Do not launder a question into
        # publicly established common ground.
        if not actual or actual.endswith("?"):
            continue
        import re
        if re.search(r"\bI\s+(?:didn't|did not|never)\s+(?:see|notice|hear|find|check|read|observe)\b", actual, re.I):
            continue
        own_fact = private_observation(speaker, cycle)
        overlap = _evidence_words(actual) & _evidence_words(own_fact)
        # A firsthand public report can paraphrase its private clue using
        # one distinctive term. Other statements still need two.
        first_hand = bool(re.search(
            r"\bI\s+(?:just\s+|also\s+|personally\s+)?(?:saw|noticed|heard|read|found|checked|measured|observed)\b",
            actual, re.I))
        if len(overlap) < 2 and not (first_hand and len(overlap) >= 1):
            continue
        report = {
            "speaker": speaker,
            "public_text": actual[:240],
            "source_id": str(turn.get("id") or ""),
            "evidence_status": "firsthand_report" if first_hand else "unverified_statement",
        }
        prior = facts.get(speaker)
        if prior is None or (first_hand and prior["evidence_status"] != "firsthand_report"):
            facts[speaker] = report
    return [facts[p] for p in PARTICIPANTS if p in facts]


def scene_action_ledger(cycle: int, public_turns: list[dict]) -> list[dict]:
    """Reconstruct witnessed actions; effects are not invented speech or private facts."""
    if not followup_active(cycle) or not active_scene_window(cycle):
        return []
    from room_world_actions import action_consequence
    scene = scene_for_cycle(cycle).identifier
    onset = scene_phase(cycle)[1]
    effects = []
    seen = set()
    for turn in public_turns:
        if not isinstance(turn, dict):
            continue
        try:
            beat_cycle = int(str(turn.get("beat_id") or "").rsplit("-", 1)[-1])
        except (TypeError, ValueError):
            continue
        if not onset <= beat_cycle < cycle:
            continue
        effect = action_consequence(scene, turn.get("speaker"), turn.get("text"))
        if not effect:
            continue
        signature = (effect["action"], effect["object"])
        if signature in seen:
            continue
        seen.add(signature)
        effects.append({"source_id": str(turn.get("id") or ""), **effect})
    return effects[-4:]


def scene_common_ground(cycle: int, public_turns: list[dict]) -> str:
    entries = public_scene_ledger(cycle, public_turns)
    effects = scene_action_ledger(cycle, public_turns)
    if not entries and not effects:
        return ""
    # Evidence order matters for a small local model. Keep independently
    # simulated consequences distinct from unverified character assertions:
    # repeating an incorrect date does not make it a witnessed world fact.
    lines = ["PREVIOUSLY SPOKEN PUBLIC OBSERVATIONS ABOUT THIS SAME SITUATION "
             "(not new dialogue; evidence is attributed below):"]
    if effects:
        lines.append("SOURCE-LINKED SIMULATED ENVIRONMENT CONSEQUENCES "
                     "(these followed witnessed public actions):")
        for e in effects:
            lines.append(e["actor"].capitalize() + " acted [" + e["source_id"]
                         + "]; the simulated result was: " + e["effect"])
    if entries:
        lines.append("PUBLIC CHARACTER CLAIMS (NOT INDEPENDENTLY VERIFIED):")
        for e in entries:
            lines.append(e["speaker"].capitalize() + " said: " + e["public_text"]
                         + " [source " + e["source_id"] + "]")
    lines.append("A character's claim may disagree with a simulated observation. "
                 "Keep their provenance distinct; examine the discrepancy rather "
                 "than treating repeated claims as independent confirmation. "
                 "No observation alone proves an explanation.")
    return "\n".join(lines)
