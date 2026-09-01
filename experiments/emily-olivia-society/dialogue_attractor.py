#!/usr/bin/env python3
"""Generic recurring-content detection for Emily + Olivia dialogue.

This module does not prescribe topics, moves, or replacement dialogue. It only
recognizes when the model keeps recycling the same meaningful word-pairs across
recent turns, including light morphological variants such as make/making.
"""
from __future__ import annotations

from collections import Counter
import re

_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?", re.IGNORECASE)
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had", "has",
    "have", "having", "he", "her", "hers", "him", "his", "how", "i", "if", "in",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours", "she", "so",
    "that", "the", "their", "theirs", "them", "they", "this", "to", "us", "was",
    "we", "were", "what", "when", "where", "which", "who", "why", "will", "with",
    "would", "you", "your", "yours", "emily", "olivia",
    # Greeting/courtesy tokens are too common to carry an attractor signal.
    "hey", "hi", "hello", "yeah", "yes", "okay", "ok", "thanks", "thank", "sorry",
    "please", "oh", "uh", "well",
}
_IRREGULAR = {
    "making": "make",
    "taking": "take",
    "having": "have",
    "giving": "give",
    "using": "use",
    "moving": "move",
    "going": "go",
    "doing": "do",
}


def _root(word: str) -> str:
    word = word.lower().strip("'")
    if word in _IRREGULAR:
        return _IRREGULAR[word]
    if word.endswith("ies") and len(word) >= 6:
        return word[:-3] + "y"
    if word.endswith("ed") and len(word) >= 6:
        base = word[:-2]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if word.endswith("ing") and len(word) >= 7 and not word.endswith("thing"):
        base = word[:-3]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if word.endswith("s") and not word.endswith("ss") and len(word) >= 6:
        return word[:-1]
    return word


def content_tokens(text: str) -> tuple[str, ...]:
    tokens = []
    for raw in _WORD_RE.findall(str(text or "")):
        rooted = _root(raw)
        if rooted in _STOP or len(rooted) < 3:
            continue
        tokens.append(rooted)
    return tuple(tokens)


def _pairs(tokens: tuple[str, ...]) -> set[tuple[str, str]]:
    return {
        (tokens[index], tokens[index + 1])
        for index in range(len(tokens) - 1)
        if tokens[index] != tokens[index + 1]
    }


def candidate_repeats_recurring_attractor(
    text: str,
    dialogue_history,
    history_limit: int = 12,
) -> bool:
    """Reject a candidate that would reinforce a recurring recent phrase cluster."""
    candidate = content_tokens(text)
    if len(candidate) < 2:
        return False

    histories = []
    for _speaker, prior in list(dialogue_history or [])[-history_limit:]:
        tokens = content_tokens(str(prior))
        if tokens:
            histories.append(tokens)
    if len(histories) < 2:
        return False

    pair_message_counts: Counter[tuple[str, str]] = Counter()
    token_message_counts: Counter[str] = Counter()
    for tokens in histories:
        pair_message_counts.update(_pairs(tokens))
        token_message_counts.update(set(tokens))

    # If the same meaningful pair already appeared in two distinct recent
    # messages, a third use is a recurring-content loop even when surrounding
    # wording has been paraphrased.
    if any(pair_message_counts[pair] >= 2 for pair in _pairs(candidate)):
        return True

    # Catch looser paraphrase attractors whose vocabulary is repeatedly drawn
    # from the same small hot cluster without requiring a particular topic.
    candidate_set = set(candidate)
    hot = {token for token, count in token_message_counts.items() if count >= 3}
    shared = candidate_set & hot
    return len(shared) >= 3 and len(shared) / max(1, len(candidate_set)) >= 0.45


def detect_recurring_content_attractor(messages: list[str]) -> dict | None:
    """Detect a durable recurring-content loop in a recent message window."""
    tokenized = [content_tokens(text) for text in messages]
    tokenized = [tokens for tokens in tokenized if len(tokens) >= 2]
    if len(tokenized) < 4:
        return None

    pair_message_counts: Counter[tuple[str, str]] = Counter()
    for tokens in tokenized:
        pair_message_counts.update(_pairs(tokens))

    recurring = [
        (pair, count)
        for pair, count in pair_message_counts.items()
        if count >= 3
    ]
    recurring.sort(key=lambda item: (-item[1], item[0]))

    # One phrase in five messages, or two different phrases in at least three
    # messages each, is strong enough to reject an interrupted checkpoint.
    if recurring and (recurring[0][1] >= 5 or len(recurring) >= 2):
        return {
            "reason": "recurring_content_attractor",
            "count": recurring[0][1],
            "phrase": " ".join(recurring[0][0]),
            "recurring_pairs": [
                {"phrase": " ".join(pair), "count": count}
                for pair, count in recurring[:5]
            ],
        }
    return None
