#!/usr/bin/env python3
"""Fail-closed grounding guards for paper-derived Emily + Olivia speech.

These checks never write replacement dialogue. They reject concrete role or
world-state claims that are unsupported by the current social evidence and ask
the same Stanford-derived generator for another stochastic sample.
"""
from __future__ import annotations

from functools import wraps
import re

_MAX_BOUNDARY_ATTEMPTS = 3

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_DIRECT_SELF_ADDRESS_START = re.compile(
    r"^\s*(?:(?:hi|hey|hello)\s*[,!:\-]?\s*)?{name}\b\s*[,!?:\-]",
    re.IGNORECASE,
)
_SELF_VOCATIVE = re.compile(
    r"(?:^|[,;:!?]\s*|\b(?:hi|hey|hello)\s+){name}\b\s*[,!?.:]",
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


def _words(text: object) -> set[str]:
    return {match.group(0).casefold() for match in _WORD.finditer(str(text or ""))}


def _addresses_self_as_peer(text: str, agent_name: str) -> bool:
    """Catch role inversion, including mid-sentence self-vocatives."""
    name = str(agent_name or "").strip()
    if not name:
        return False
    start = re.compile(
        _DIRECT_SELF_ADDRESS_START.pattern.format(name=re.escape(name)),
        _DIRECT_SELF_ADDRESS_START.flags,
    )
    vocative = re.compile(
        _SELF_VOCATIVE.pattern.format(name=re.escape(name)),
        _SELF_VOCATIVE.flags,
    )
    candidate = str(text or "")
    return bool(start.search(candidate) or vocative.search(candidate))


def _support_text(inbound: str, dialogue_history, cognitive_context: str) -> str:
    parts = [str(inbound or ""), str(cognitive_context or "")]
    for speaker, line in list(dialogue_history or [])[-12:]:
        parts.append(str(speaker or ""))
        parts.append(str(line or ""))
    return "\n".join(parts)


def _location_phrase_words(phrase: str) -> set[str]:
    return _words(phrase)


def _has_unsupported_concrete_setting(
    text: str,
    inbound: str,
    dialogue_history,
    cognitive_context: str,
) -> bool:
    """Reject location claims that are absent from available evidence.

    A clean opening often has almost no support text. That is precisely when
    grounding must be strict, not disabled. A detected concrete location is
    therefore unsupported when no evidence words exist.
    """
    support_words = _words(_support_text(inbound, dialogue_history, cognitive_context))
    for match in _CONCRETE_SETTING_ANCHOR.finditer(str(text or "")):
        phrase_words = _location_phrase_words(match.group(1))
        if not phrase_words:
            continue
        if not support_words or not phrase_words.issubset(support_words):
            return True
    return False


def install_spoken_action_guard(generator):
    """Wrap a spoken-action generator with resampling-only boundary checks."""
    if getattr(generator, "_emily_olivia_dialogue_guard", False):
        return generator

    @wraps(generator)
    def guarded(
        agent,
        other,
        dialogue_history=None,
        inbound: str = "",
        cognitive_context: str = "",
    ):
        rejected: list[str] = []
        for _ in range(_MAX_BOUNDARY_ATTEMPTS):
            text = generator(
                agent,
                other,
                dialogue_history=dialogue_history,
                inbound=inbound,
                cognitive_context=cognitive_context,
            )
            if _addresses_self_as_peer(text, getattr(agent, "name", "")):
                rejected.append(f"self-address:{str(text)[:180]}")
                continue
            if _has_unsupported_concrete_setting(
                text,
                inbound,
                dialogue_history,
                cognitive_context,
            ):
                rejected.append(f"unsupported-setting:{str(text)[:180]}")
                continue
            return text

        preview = " | ".join(repr(item) for item in rejected)
        raise RuntimeError(
            f"{getattr(agent, 'name', 'agent')} paper-derived Stanford act repeatedly "
            f"crossed the live dialogue grounding boundary: {preview}"
        )

    guarded._emily_olivia_dialogue_guard = True
    return guarded
