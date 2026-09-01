#!/usr/bin/env python3
"""External-reality and role-grounding checks for Emily + Olivia dialogue.

This module never authors replacement dialogue. It only classifies model output
whose claimed external evidence or conversational role is absent from the
current social evidence.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_REPORTED_CONTENT = re.compile(r"\b(?:it|the\s+(?:message|email|text|note))\s+says?\b", re.IGNORECASE)
_LINK_OFFER = re.compile(r"\b(?:here(?:'s|\s+is)|this\s+is)\s+(?:a|the)\s+link\b", re.IGNORECASE)
_CLICK_LINK_REQUEST = re.compile(r"\b(?:click|open|follow)\s+(?:the|this|that)\s+link\b", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s)\]>'\"]+|www\.[^\s)\]>'\"]+", re.IGNORECASE)
_MEDIA_ARTIFACT_CLAIM = re.compile(
    r"\b(?:here(?:'s|\s+is)|i(?:'ve|\s+have)\s+attached|i(?:'m|\s+am)\s+sending|"
    r"i\s+want\s+to\s+share)\b[^.!?]{0,100}\b(?:photo|picture|image|video|file|attachment)\b",
    re.IGNORECASE,
)
_MEDIA_WORD = re.compile(r"\b(?:photo|picture|image|video|file|attachment)\b", re.IGNORECASE)
_SERVICE_RESPONSE_TEMPLATE = re.compile(
    r"(?:\bthank\s+you\s+for\s+your\s+response\b|"
    r"\bi\s+will\s+be\s+happy\s+to\s+answer\s+(?:any\s+)?questions\b|"
    r"\bplease\s+let\s+me\s+know\s+if\s+you\s+have\s+(?:any\s+)?questions\b)",
    re.IGNORECASE,
)
_RESIDENCE_CLAIM = re.compile(
    r"\bi\s+(?:live|reside)\s+in\s+([A-Za-z][A-Za-z .'-]{1,60}?)(?=[.!?]|$)",
    re.IGNORECASE,
)
_FILLER = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "her", "here", "him", "his", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "she", "that", "the", "their",
    "them", "they", "this", "to", "us", "was", "we", "were", "with", "you",
    "your", "says", "say", "said", "live", "reside",
}


def _content_words(text: object) -> set[str]:
    return {
        match.group(0).casefold()
        for match in _WORD.finditer(str(text or ""))
        if match.group(0).casefold() not in _FILLER and len(match.group(0)) >= 3
    }


def _has_unsupported_reported_content(text: str, support_text: str) -> bool:
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


def _has_unsupported_link_offer(text: str, support_text: str) -> bool:
    candidate = str(text or "")
    if not _LINK_OFFER.search(candidate):
        return False
    urls = {url.casefold() for url in _URL.findall(candidate)}
    if not urls:
        return True
    support_urls = {url.casefold() for url in _URL.findall(str(support_text or ""))}
    return not urls.issubset(support_urls)


def _has_nonexistent_link_action(text: str, support_text: str) -> bool:
    if not _CLICK_LINK_REQUEST.search(str(text or "")):
        return False
    return not bool(_URL.search(str(support_text or "")))


def _has_unsupported_media_artifact(text: str, support_text: str) -> bool:
    candidate = str(text or "")
    if not _MEDIA_ARTIFACT_CLAIM.search(candidate):
        return False
    return not bool(_MEDIA_WORD.search(str(support_text or "")))


def _has_unsupported_residence(text: str, support_text: str) -> bool:
    match = _RESIDENCE_CLAIM.search(str(text or ""))
    if not match:
        return False
    place_words = _content_words(match.group(1))
    if not place_words:
        return False
    return not place_words.issubset(_content_words(support_text))


def _splits_current_peer_identity(text: str, other_name: str) -> bool:
    other = str(other_name or "").strip()
    if not other:
        return False
    pattern = re.compile(
        rf"\b(?:a|the)\s+(?:woman|man|girl|boy|person)\s+(?:named|called)\s+{re.escape(other)}\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(str(text or "")))


def candidate_external_grounding_blocker(
    text: str,
    support_text: str,
    *,
    agent_name: str = "",
    other_name: str = "",
) -> str | None:
    _ = agent_name
    if _SERVICE_RESPONSE_TEMPLATE.search(str(text or "")):
        return "service-response-template"
    if _splits_current_peer_identity(text, other_name):
        return "same-name-peer-split"
    if _has_unsupported_reported_content(text, support_text):
        return "unsupported-reported-content"
    if _has_unsupported_link_offer(text, support_text):
        return "unsupported-link-offer"
    if _has_nonexistent_link_action(text, support_text):
        return "nonexistent-link-action"
    if _has_unsupported_media_artifact(text, support_text):
        return "unsupported-media-artifact"
    if _has_unsupported_residence(text, support_text):
        return "unsupported-residence"
    return None
