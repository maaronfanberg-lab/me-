#!/usr/bin/env python3
from __future__ import annotations

"""Runtime guard around the preserved Emily + Olivia dialogue generator.

The implementation lives in community_cycle_impl.py.  This thin layer keeps the
strict grounding validator, adds cross-speaker echo protection, and guarantees
that the deterministic recovery path itself satisfies that same validator.
"""

import asyncio
import re
from difflib import SequenceMatcher

import community_cycle_impl as _impl

_base = _impl._base
_original_usable = _base._is_usable_utterance
_original_similarity = _impl._too_similar_to_own_history

_DAY_BACKSTORY = re.compile(
    r"\b(?:work|working|job|office|coworker|coworkers|team|project|projects|client|clients|boss|meeting|meetings)\b",
    re.IGNORECASE,
)
_RECOVERY_NOISE = {
    "anything", "doing", "fine", "glad", "good", "great", "like", "make", "making",
    "okay", "plan", "planning", "start", "starting", "thing", "things", "trying", "want",
    "well", "going",
}


def _is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    """Keep the upstream validator strict and reject invented work lore on a blank check-in."""
    if not _original_usable(text, inbound, agent_name, other_name):
        return False
    if inbound and _impl._is_day_checkin(inbound) and _DAY_BACKSTORY.search(str(text)):
        return False
    return True


def _signature(text: str) -> set[str]:
    return {
        word
        for word in _base._normalize_words(str(text))
        if word not in _base._STOP_WORDS
        and word not in _RECOVERY_NOISE
        and word not in {"emily", "olivia", "self", "partner"}
        and len(word) > 2
    }


def _too_similar_to_own_history(
    reply: str,
    agent_name: str,
    dialogue_history: list[tuple[str, str]] | None,
) -> bool:
    """Retain same-speaker checks and also block near-copying the partner's recent line."""
    if _original_similarity(reply, agent_name, dialogue_history):
        return True

    normalized = " ".join(_base._normalize_words(reply))
    signature = _signature(reply)
    if not normalized:
        return True

    for speaker, previous in list(dialogue_history or [])[-4:]:
        if speaker == agent_name:
            continue
        previous_normalized = " ".join(_base._normalize_words(str(previous)))
        if not previous_normalized:
            continue
        if SequenceMatcher(None, normalized, previous_normalized).ratio() >= 0.82:
            return True
        previous_signature = _signature(str(previous))
        if len(signature) >= 3 and len(previous_signature) >= 3:
            union = signature | previous_signature
            if union and len(signature & previous_signature) / len(union) >= 0.72:
                return True
    return False


def _recovery_anchor(inbound: str) -> str:
    anchors = _impl._grounding_words(inbound, limit=8)
    for word in reversed(anchors):
        if word not in _RECOVERY_NOISE:
            return word
    return ""


def _recovery_reply(
    agent: _base.CommunityAgent,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None,
) -> str:
    """Return a natural recovery line that is proven valid before it leaves this function."""
    lowered = " ".join(str(inbound).lower().split())
    anchor = _recovery_anchor(inbound)

    if _base._is_greeting_only(inbound):
        candidates = [
            "Hi. Good to see you.",
            "Hey. How are you?",
            "Hi. Nice to see you.",
        ]
    elif _impl._is_day_checkin(inbound):
        candidates = [
            "My day is pretty calm so far. How about yours?",
            "My day is going okay. How about you?",
            "Pretty good today. How are you doing?",
        ]
    elif _impl._is_intent_statement(inbound) and anchor:
        candidates = [
            f"What got you interested in {anchor}?",
            f"How do you want to start with {anchor}?",
            f"What would make {anchor} worth trying for you?",
        ]
    elif _impl._is_open_question(inbound) and "favorite" in lowered:
        candidates = [
            f"Probably the quiet part of the {anchor}." if anchor else "Probably the quiet part.",
            f"I like the calmer side of {anchor}." if anchor else "I usually like the calmer part.",
        ]
    elif _impl._is_open_question(inbound) and anchor:
        candidates = [
            f"I haven't decided on the {anchor} details yet.",
            f"For {anchor}, I'd keep it simple at first.",
            f"The {anchor} part is what I'd think about first.",
        ]
    elif anchor:
        candidates = [
            f"That makes sense about {anchor}. What happened next?",
            f"The {anchor} part caught my attention. What do you think about it?",
            f"I get what you mean about {anchor}. Where do you want to take it?",
        ]
    else:
        candidates = [
            "That makes sense. What are you thinking about now?",
            "Fair enough. What happened next?",
            "That makes sense. Where do you want to go from here?",
        ]

    prior_lines = {
        " ".join(_base._normalize_words(str(text)))
        for _speaker, text in (dialogue_history or [])
        if str(text).strip()
    }
    for candidate in candidates:
        normalized = " ".join(_base._normalize_words(candidate))
        if normalized in prior_lines:
            continue
        if _too_similar_to_own_history(candidate, agent.name, dialogue_history):
            continue
        if _is_usable_utterance(candidate, inbound, agent.name, "Olivia" if agent.name == "Emily" else "Emily"):
            return candidate

    # These are deliberately acknowledgement-based because the preserved validator explicitly
    # permits a short acknowledgement when an inbound line has no useful lexical anchor.
    for candidate in (
        "That makes sense. What happened next?",
        "Fair enough. What are you thinking now?",
    ):
        if _is_usable_utterance(candidate, inbound, agent.name, "Olivia" if agent.name == "Emily" else "Emily"):
            return candidate

    raise RuntimeError(f"{agent.name} recovery could not produce a grounded natural-language utterance.")


# Patch the preserved implementation in-place. Its direct generator resolves these names from
# its module globals at call time, while base choose_action resolves the validator from _base.
_impl._too_similar_to_own_history = _too_similar_to_own_history
_impl._recovery_reply = _recovery_reply
_base._is_usable_utterance = _is_usable_utterance

# Explicit compatibility exports used by the rest of the Community runtime and smoke checks.
CommunityAgent = _base.CommunityAgent
load_agents = _impl.load_agents
observation_text = _impl.observation_text
choose_action = _impl.choose_action
next_community_time_step = _impl.next_community_time_step
latest_community_time_step = _impl.latest_community_time_step
_grounding_words = _impl._grounding_words
_direct_bitnet_reply = _impl._direct_bitnet_reply


def __getattr__(name: str):
    return getattr(_impl, name)


if __name__ == "__main__":
    asyncio.run(_base.main())
