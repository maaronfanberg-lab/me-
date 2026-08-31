#!/usr/bin/env python3
from __future__ import annotations

"""Runtime guard around the preserved Emily + Olivia dialogue generator.

The implementation lives in community_cycle_impl.py.  This thin layer keeps the
strict grounding validator, adds cross-speaker echo protection, blocks internal
self-repetition, and guarantees that deterministic recovery satisfies the same
quality bar.
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
    "well", "going", "detail", "details", "part", "parts", "next",
}
_VAGUE_ANCHORS = {
    "anything", "detail", "details", "part", "parts", "something", "thing", "things",
    "next", "that", "this", "it", "idea", "ideas",
}


def _has_internal_repetition(text: str) -> bool:
    """Reject obvious repeated clauses/sentences inside a single generated utterance."""
    pieces = [
        " ".join(_base._normalize_words(piece))
        for piece in re.split(r"[.!?;]+", str(text))
        if " ".join(_base._normalize_words(piece))
    ]
    if len(pieces) >= 2 and len(set(pieces)) < len(pieces):
        return True

    words = _base._normalize_words(str(text))
    for size in range(3, min(9, max(3, len(words) // 2 + 1))):
        seen: set[tuple[str, ...]] = set()
        for i in range(0, len(words) - size + 1):
            gram = tuple(words[i : i + size])
            if gram in seen:
                return True
            seen.add(gram)
    return False


def _is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    """Keep the upstream validator strict and add repetition/backstory guards."""
    if not _original_usable(text, inbound, agent_name, other_name):
        return False
    if _has_internal_repetition(str(text)):
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
        if word not in _RECOVERY_NOISE and word not in _VAGUE_ANCHORS:
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
            f"For {anchor}, I'd keep it simple at first.",
            f"I'd probably start with one small piece of {anchor}.",
            f"The {anchor} part is what I'd think about first.",
        ]
    elif anchor:
        candidates = [
            f"What happened with {anchor} after that?",
            f"What do you think about {anchor} now?",
            f"Where do you want to take {anchor} from here?",
        ]
    else:
        candidates = [
            "What happened next?",
            "What are you thinking about now?",
            "Where do you want to go from here?",
        ]

    prior_lines = {
        " ".join(_base._normalize_words(str(text)))
        for _speaker, text in (dialogue_history or [])
        if str(text).strip()
    }
    other_name = "Olivia" if agent.name == "Emily" else "Emily"
    for candidate in candidates:
        normalized = " ".join(_base._normalize_words(candidate))
        if normalized in prior_lines:
            continue
        if _too_similar_to_own_history(candidate, agent.name, dialogue_history):
            continue
        if _is_usable_utterance(candidate, inbound, agent.name, other_name):
            return candidate

    for candidate in (
        "What happened next?",
        "What are you thinking now?",
    ):
        if _is_usable_utterance(candidate, inbound, agent.name, other_name):
            return candidate

    raise RuntimeError(f"{agent.name} recovery could not produce a grounded natural-language utterance.")


_impl._too_similar_to_own_history = _too_similar_to_own_history
_impl._recovery_reply = _recovery_reply
_base._is_usable_utterance = _is_usable_utterance

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
