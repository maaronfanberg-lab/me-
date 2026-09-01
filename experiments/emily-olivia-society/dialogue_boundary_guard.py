#!/usr/bin/env python3
"""Fail-closed grounding guards for paper-derived Emily + Olivia speech.

These checks never write replacement dialogue. They reject concrete role or
world-state claims that are unsupported by the current social evidence and ask
the same Stanford-derived generator for another stochastic sample.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from functools import wraps
import re

_MAX_BOUNDARY_ATTEMPTS = 3

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_GREETING_START = re.compile(r"^\s*(?:hi|hello|hey|oh\s*,?\s*hi)\b", re.IGNORECASE)
_DIRECT_SELF_ADDRESS_START = re.compile(
    r"^\s*(?:(?:hi|hey|hello)\s*[,!:\-]?\s*)?{name}\b\s*[,!?:\-]",
    re.IGNORECASE,
)
_SELF_VOCATIVE = re.compile(
    r"(?:^|[,;:!?]\s*|\b(?:hi|hey|hello)\s+){name}\b\s*[,!?.:]",
    re.IGNORECASE,
)
_PRESENCE_EVIDENCE = re.compile(
    r"(?:\bcommunity\s+contains\b|\bpresent\s+(?:together|in\s+the\s+private\s+two-person\s+community)\b)",
    re.IGNORECASE,
)
_PRESENCE_CONTRADICTION = re.compile(
    r"(?:\bwhere\s+are\s+you\b|\bi\s+(?:can't|cannot)\s+(?:see|find)\s+you\b|"
    r"\byou(?:'re|\s+are)\s+not\s+(?:here|visible)\b)",
    re.IGNORECASE,
)
_UNSUPPORTED_ROLE_CLAIM = re.compile(
    r"(?:\bi\s+am\s+(?:a\s+)?stranger\b|"
    r"\bi(?:'ve|\s+have)?\s*(?:been\s+)?sent\s+(?:here\s+)?to\s+(?:observe|watch|monitor)\b|"
    r"\bi\s+am\s+here\s+to\s+(?:observe|watch|monitor)\b|"
    r"\bi\s+(?:was|am)\s+assigned\s+to\s+(?:observe|watch|monitor)\b)",
    re.IGNORECASE,
)
_ROLE_EVIDENCE = re.compile(
    r"(?:\bstranger\b|\bsent\b[^.]{0,80}\b(?:observe|watch|monitor)\b|"
    r"\bassigned\b[^.]{0,80}\b(?:observe|watch|monitor)\b)",
    re.IGNORECASE,
)
_PHANTOM_LIVE_INTERLOCUTOR = re.compile(
    r"\byou\s+(?:seem|appear)\s+to\s+be\s+(?:having\s+a\s+conversation|talking|speaking|chatting)\s+with\s+(?:someone|somebody)\b",
    re.IGNORECASE,
)
_THIRD_INTERLOCUTOR_EVIDENCE = re.compile(
    r"\b(?:someone|somebody|another\s+person|third\s+person)\b[^.]{0,100}\b(?:talk|speak|chat|conversation)\b|"
    r"\b(?:talk|speak|chat|conversation)\b[^.]{0,100}\b(?:someone|somebody|another\s+person|third\s+person)\b",
    re.IGNORECASE,
)

_LOCATION_HEAD = (
    r"(?:town|city|hospital|school|office|center|centre|park|cafe|café|"
    r"restaurant|store|shop|house|home|apartment|library|church|clinic|"
    r"beach|station|airport|hotel|room|kitchen|garden|neighbou?rhood|"
    r"street|market|mall|gym|bar|pub|theat(?:er|re)|museum)"
)
_CONCRETE_SETTING_ANCHOR = re.compile(
    rf"\b(?:at|from|inside|outside|near|around|through|into|onto|to|back\s+to|"
    rf"during|after|before)\s+"
    rf"(?:(?:the|a|an|your|my|our|their|his|her)\s+)?"
    rf"((?:[A-Za-z][A-Za-z'-]*\s+){{0,2}}{_LOCATION_HEAD})\b",
    re.IGNORECASE,
)


def _word_list(text: object) -> list[str]:
    return [match.group(0).casefold() for match in _WORD.finditer(str(text or ""))]


def _words(text: object) -> set[str]:
    return set(_word_list(text))


def _addresses_self_as_peer(text: str, agent_name: str) -> bool:
    name = str(agent_name or "").strip()
    if not name:
        return False
    start = re.compile(_DIRECT_SELF_ADDRESS_START.pattern.format(name=re.escape(name)), _DIRECT_SELF_ADDRESS_START.flags)
    vocative = re.compile(_SELF_VOCATIVE.pattern.format(name=re.escape(name)), _SELF_VOCATIVE.flags)
    candidate = str(text or "")
    return bool(start.search(candidate) or vocative.search(candidate))


def _reintroduces_known_self(text: str, agent_name: str, dialogue_history) -> bool:
    if not list(dialogue_history or []):
        return False
    name = str(agent_name or "").strip()
    if not name:
        return False
    return bool(re.search(rf"\b(?:i\s+am|i'm|my\s+name\s+is)\s+{re.escape(name)}\b", str(text or ""), re.IGNORECASE))


def _is_mid_conversation_greeting_reset(text: str, dialogue_history) -> bool:
    """A continuous exchange should not keep restarting with fresh greetings."""
    return len(list(dialogue_history or [])) >= 4 and bool(_GREETING_START.search(str(text or "")))


def _support_text(inbound: str, dialogue_history, cognitive_context: str) -> str:
    parts = [str(inbound or ""), str(cognitive_context or "")]
    for speaker, line in list(dialogue_history or [])[-12:]:
        parts.append(str(speaker or ""))
        parts.append(str(line or ""))
    return "\n".join(parts)


def _contradicts_observed_presence(text: str, other_name: str, support_text: str) -> bool:
    other = str(other_name or "").strip().casefold()
    support = str(support_text or "")
    if not other or other not in support.casefold() or not _PRESENCE_EVIDENCE.search(support):
        return False
    return bool(_PRESENCE_CONTRADICTION.search(str(text or "")))


def _has_unsupported_role_claim(text: str, support_text: str) -> bool:
    if not _UNSUPPORTED_ROLE_CLAIM.search(str(text or "")):
        return False
    return not bool(_ROLE_EVIDENCE.search(str(support_text or "")))


def _has_phantom_live_interlocutor(text: str, support_text: str) -> bool:
    if not _PHANTOM_LIVE_INTERLOCUTOR.search(str(text or "")):
        return False
    return not bool(_THIRD_INTERLOCUTOR_EVIDENCE.search(str(support_text or "")))


def _is_short_recent_echo(text: str, dialogue_history) -> bool:
    output = _word_list(text)
    if len(output) < 3 or len(output) > 7:
        return False
    for _speaker, prior in list(dialogue_history or [])[-6:]:
        previous = _word_list(prior)
        if len(previous) < 3:
            continue
        if output == previous[: len(output)] or previous == output[: len(previous)]:
            return True
        if SequenceMatcher(None, output, previous, autojunk=False).ratio() >= 0.74:
            return True
    return False


def _location_phrase_words(phrase: str) -> set[str]:
    return _words(phrase)


def _has_unsupported_concrete_setting(text: str, inbound: str, dialogue_history, cognitive_context: str) -> bool:
    support_words = _words(_support_text(inbound, dialogue_history, cognitive_context))
    for match in _CONCRETE_SETTING_ANCHOR.finditer(str(text or "")):
        phrase_words = _location_phrase_words(match.group(1))
        if phrase_words and (not support_words or not phrase_words.issubset(support_words)):
            return True
    return False


def install_spoken_action_guard(generator):
    """Wrap a spoken-action generator with resampling-only boundary checks."""
    if getattr(generator, "_emily_olivia_dialogue_guard", False):
        return generator

    @wraps(generator)
    def guarded(agent, other, dialogue_history=None, inbound: str = "", cognitive_context: str = ""):
        rejected: list[str] = []
        for _ in range(_MAX_BOUNDARY_ATTEMPTS):
            text = generator(agent, other, dialogue_history=dialogue_history, inbound=inbound, cognitive_context=cognitive_context)
            support = _support_text(inbound, dialogue_history, cognitive_context)
            if _addresses_self_as_peer(text, getattr(agent, "name", "")):
                rejected.append(f"self-address:{str(text)[:180]}")
                continue
            if _reintroduces_known_self(text, getattr(agent, "name", ""), dialogue_history):
                rejected.append(f"self-reintroduction:{str(text)[:180]}")
                continue
            if _is_mid_conversation_greeting_reset(text, dialogue_history):
                rejected.append(f"greeting-reset:{str(text)[:180]}")
                continue
            if _contradicts_observed_presence(text, getattr(other, "name", ""), support):
                rejected.append(f"presence-contradiction:{str(text)[:180]}")
                continue
            if _has_unsupported_role_claim(text, support):
                rejected.append(f"unsupported-role:{str(text)[:180]}")
                continue
            if _has_phantom_live_interlocutor(text, support):
                rejected.append(f"phantom-interlocutor:{str(text)[:180]}")
                continue
            if _is_short_recent_echo(text, dialogue_history):
                rejected.append(f"short-echo:{str(text)[:180]}")
                continue
            if _has_unsupported_concrete_setting(text, inbound, dialogue_history, cognitive_context):
                rejected.append(f"unsupported-setting:{str(text)[:180]}")
                continue
            return text

        preview = " | ".join(repr(item) for item in rejected)
        raise RuntimeError(
            f"{getattr(agent, 'name', 'agent')} paper-derived Stanford act repeatedly crossed the live dialogue grounding boundary: {preview}"
        )

    guarded._emily_olivia_dialogue_guard = True
    return guarded
