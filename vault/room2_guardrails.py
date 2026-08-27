from __future__ import annotations

import re
from collections import Counter

ACCUSATION_PATTERNS = (
    r"\byou(?:'re| are) (?:trying to|making me|forcing me|controlling me|manipulating me|attacking me|threatening me)\b",
    r"\byou (?:demand|demanded|insist|insisted|refuse|refused)\b",
    r"\byour (?:demands|threats|pressure|manipulation)\b",
    r"\bI (?:won't|will not|refuse to) (?:give in|obey|submit)\b",
)
GENERIC_GROUNDING = {
    "thing","things","something","anything","really","think","feel","feeling","going","want","like",
    "know","maybe","still","right","wrong","good","bad","much","more","some","just","very","about",
}


def words(text: object) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(text or "").lower())


def content_words(text: object) -> set[str]:
    return {w for w in words(text) if len(w) >= 4 and w not in GENERIC_GROUNDING}


def semantic_overlap(a: object, b: object) -> float:
    aa, bb = content_words(a), content_words(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, len(aa | bb))


def has_unsupported_accusation(text: str) -> bool:
    low = str(text or "").lower()
    return any(re.search(pattern, low) for pattern in ACCUSATION_PATTERNS)


def weak_grounding(text: str, context_items: list[dict]) -> bool:
    candidate = content_words(text)
    context = set()
    for item in context_items:
        if isinstance(item, dict):
            context |= content_words(item.get("text"))
    if not context:
        return False
    shared = candidate & context
    # One generic lexical accident should not count as grounding.
    return len(shared) < 2


def semantic_repeat(text: str, recent: list[dict]) -> bool:
    for item in recent[-10:]:
        if isinstance(item, dict) and semantic_overlap(text, item.get("text")) >= 0.58:
            return True
    return False


def repetitive_opening(text: str, recent: list[dict]) -> bool:
    candidate = words(text)[:4]
    if len(candidate) < 3:
        return False
    prefix = tuple(candidate[:3])
    prior = []
    for item in recent[-8:]:
        if not isinstance(item, dict):
            continue
        w = words(item.get("text"))
        if len(w) >= 3:
            prior.append(tuple(w[:3]))
    return Counter(prior)[prefix] >= 2


def excessive_second_person(text: str) -> bool:
    w = words(text)
    second = sum(x in {"you","your","you're","you've","you'll","you'd"} for x in w)
    return second > 3


def malformed_identity_claim(text: str) -> bool:
    low = str(text or "").lower()
    return bool(re.search(r"\b(?:i am|i'm) (?:sarah|mara|owen|jules)\b", low))
