#!/usr/bin/env python3
"""External-reality grounding checks for Emily + Olivia dialogue.

This module never authors replacement dialogue. It only classifies model output
whose claimed external evidence is absent from the current social evidence.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_REPORTED_CONTENT = re.compile(
    r"\b(?:it|the\s+(?:message|email|text|note))\s+says?\b",
    re.IGNORECASE,
)
_FILLER = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "her", "here", "him", "his", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "she", "that", "the", "their",
    "them", "they", "this", "to", "us", "was", "we", "were", "with", "you",
    "your", "says", "say", "said",
}


def _content_words(text: object) -> set[str]:
    return {
        match.group(0).casefold()
        for match in _WORD.finditer(str(text or ""))
        if match.group(0).casefold() not in _FILLER and len(match.group(0)) >= 3
    }


def _has_unsupported_reported_content(text: str, support_text: str) -> bool:
    """Reject invented quoted/reported message contents.

    A next-line completion may discuss reported content only when its substantive
    words are already present in the inbound/history/retrieved evidence. This is
    an evidence boundary, not a topic rule.
    """
    candidate = str(text or "")
    match = _REPORTED_CONTENT.search(candidate)
    if not match:
        return False
    reported_words = _content_words(candidate[match.end():])
    if len(reported_words) < 4:
        return False
    support_words = _content_words(support_text)
    shared = len(reported_words & support_words)
    return shared / max(1, len(reported_words)) < 0.5


def candidate_external_grounding_blocker(
    text: str,
    support_text: str,
    *,
    agent_name: str = "",
    other_name: str = "",
) -> str | None:
    _ = (agent_name, other_name)
    if _has_unsupported_reported_content(text, support_text):
        return "unsupported-reported-content"
    return None
