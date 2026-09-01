#!/usr/bin/env python3
"""Fail-closed dialogue guards for the paper-derived spoken-action generator.

These checks do not author or rewrite dialogue. They only reject two concrete
generation failures observed in the live replay and ask the same stochastic
paper-derived generator for another sample.
"""
from __future__ import annotations

from functools import wraps
import re

_MAX_BOUNDARY_ATTEMPTS = 3

_DIRECT_SELF_ADDRESS = re.compile(
    r"^\s*(?:(?:hi|hey|hello)\s*[,!:\-]?\s*)?{name}\b\s*[,!?:\-]",
    re.IGNORECASE,
)
_CONCRETE_SETTING_ANCHOR = re.compile(
    r"\b(?:at|from|inside|outside|near|during|after|before)\s+"
    r"(?:the|a|an|your|my|our|their|his|her)\s+"
    r"([A-Za-z][A-Za-z'-]{2,})\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _words(text: object) -> set[str]:
    return {match.group(0).casefold() for match in _WORD.finditer(str(text or ""))}


def _addresses_self_as_peer(text: str, agent_name: str) -> bool:
    """Catch direct-address role inversion such as Olivia saying 'Hi, Olivia!'."""
    name = str(agent_name or "").strip()
    if not name:
        return False
    pattern = re.compile(
        _DIRECT_SELF_ADDRESS.pattern.format(name=re.escape(name)),
        _DIRECT_SELF_ADDRESS.flags,
    )
    return bool(pattern.search(str(text or "")))


def _support_text(inbound: str, dialogue_history, cognitive_context: str) -> str:
    parts = [str(inbound or ""), str(cognitive_context or "")]
    for speaker, line in list(dialogue_history or [])[-12:]:
        parts.append(str(speaker or ""))
        parts.append(str(line or ""))
    return "\n".join(parts)


def _has_unsupported_concrete_setting(
    text: str,
    inbound: str,
    dialogue_history,
    cognitive_context: str,
) -> bool:
    """Reject concrete setting/event anchors absent from available evidence.

    This deliberately does not require general lexical overlap or prescribe
    topics. It only catches anchored claims such as "at the hospital" when the
    hospital is nowhere in the inbound message, recent dialogue, or retrieved
    cognitive context.
    """
    support_words = _words(_support_text(inbound, dialogue_history, cognitive_context))
    if not support_words:
        return False
    for match in _CONCRETE_SETTING_ANCHOR.finditer(str(text or "")):
        anchor = match.group(1).casefold()
        if anchor not in support_words:
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
