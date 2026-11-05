"""Conservative publication hygiene for an endogenous Room.

This is a **negative safety gate**, not a conversation director. It may only
decline to publish an exact/near-duplicate sentence or a confident claim to
another character's private cognitive state. It may never suggest a topic,
generate replacement dialogue, pick a new speaker, or order disagreement.

Similarity only blocks near-copies, not the repetition of a *subject* or a
participant returning to a belief for a good reason. Long-term semantic
naturalness needs model and human evaluation; this gate cannot prove it.
"""
from __future__ import annotations

import difflib
import re
from collections.abc import Mapping

from room_endogenous_preflight import AGENTS

MAX_LOOKBACK = 12
PRIVATE_WORDS = (
    r"private (?:hypothesis|belief|thought|memory|goal|state|reflection|reasoning)"
    r"|hidden (?:hypothesis|belief|thought|memory|goal|state)"
)
CONFIDENT_COGNITION = (
    r"(?:confidence level|belief confidence|private confidence)"
    r".{0,55}(?:drop|rose|rise|fell|declin|chang|lower|higher|increas|decreas)"
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.casefold())


def _ngrams(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i+size]) for i in range(max(0,len(tokens)-size+1))}


def _is_close_copy(text: str, earlier: str) -> bool:
    now, before = _tokens(text), _tokens(earlier)
    if now == before and len(now) >= 5:
        return True
    if min(len(now),len(before)) < 12:
        return False
    # High ratios avoid suppressing substantive changes to an explanation.
    ratio = difflib.SequenceMatcher(a=now,b=before,autojunk=False).ratio()
    if ratio >= .89:
        return True
    new4, old4 = _ngrams(now,4),_ngrams(before,4)
    if new4 and old4:
        containment = len(new4 & old4)/min(len(new4),len(old4))
        if containment >= .82 and ratio >= .75:
            return True
    return False


def _third_party_private_claim(text: str, speaker: str) -> bool:
    """Block *asserted* access to peers' hidden cognition, not social guesses."""
    lower = text.casefold()
    private_terms = (
        "private hypothesis", "private belief", "private thought",
        "private memory", "private goal", "private state",
        "private reflection", "hidden belief", "hidden thought",
    )
    for name in AGENTS:
        if name == speaker:
            continue
        # Name-bound windows are intentionally easier to audit than one giant
        # regex with nested optional and alternative capture groups.
        for mention in re.finditer(rf"\\b{re.escape(name)}\\b", text, flags=re.I):
            forward = lower[mention.end():mention.end()+125]
            backward = lower[max(0,mention.start()-85):mention.start()]
            if any(term in forward for term in private_terms):
                return True
            if ("confidence level" in forward and
                    re.search(r"\\b(?:drop|fell|declin|chang|lower|higher|increas|decreas|rose)\\w*", forward)):
                return True
            if any(term in backward for term in private_terms):
                return True
    return False

def publication_issue(*, speaker: str, text: str,
                      public_history: list[dict]) -> str | None:
    if (speaker not in AGENTS or not isinstance(text,str)
            or not isinstance(public_history,list)):
        return "invalid_publication_context"
    if _third_party_private_claim(text,speaker):
        return "asserts_other_mind_private_state"
    for observed in public_history[-MAX_LOOKBACK:]:
        if (not isinstance(observed,Mapping)
                or observed.get("speaker") not in AGENTS
                or not isinstance(observed.get("text"),str)):
            continue
        if _is_close_copy(text,observed["text"]):
            return "near_duplicate_public_speech"
    return None
