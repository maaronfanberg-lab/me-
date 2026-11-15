#!/usr/bin/env python3
"""Non-production, deterministic descriptive audit of Room conversation traces.

These signals are screening metrics, NOT a measurement of humanness or proof
that a task was actually executed. Human review and world-event joins required.
"""
from __future__ import annotations

from collections import Counter
import argparse
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

PEOPLE = {"sarah", "mara", "owen", "jules", "allen"}
WORDS = re.compile(r"[a-z0-9']+")
STOP = {"a", "an", "and", "are", "at", "be", "been", "by", "for", "from", "i",
        "in", "is", "it", "my", "of", "on", "or", "the", "their", "this",
        "to", "we", "with", "will", "you"}
INTENT = re.compile(r"\b(?:i(?:'ll| will| decide to| plan to| want to)|let's|going to)\b", re.I)


def semantic_terms(text: str) -> set[str]:
    return set(WORDS.findall(text.lower())) - STOP


def audit(turns: Sequence[Mapping], window: int = 20, threshold: float = 0.70) -> dict:
    """Report reproducible metrics. Never treat weak proxies as ground truth."""
    valid = [(str(t.get("speaker", "")).lower(), str(t.get("text", "")))
             for t in turns if isinstance(t, Mapping) and t.get("text")]
    counts = Counter(speaker for speaker, _ in valid)
    addresses = 0
    questions = 0
    intentions = 0
    echoes = 0
    echo_examples = []
    for i, (speaker, text) in enumerate(valid):
        terms = semantic_terms(text)
        if "?" in text:
            questions += 1
        if INTENT.search(text):
            intentions += 1
        if any(person != speaker and re.search(r"\b" + person + r"\b", text.lower())
               for person in PEOPLE):
            addresses += 1
        if len(terms) < 5:
            continue
        for j in range(max(0, i - window), i):
            prev_speaker, prev_text = valid[j]
            if prev_speaker != speaker:
                continue
            prev_terms = semantic_terms(prev_text)
            similarity = len(terms & prev_terms) / max(1, len(terms | prev_terms))
            if similarity >= threshold:
                echoes += 1
                if len(echo_examples) < 5:
                    echo_examples.append({"turn_index": i, "prior_index": j,
                                          "jaccard": round(similarity, 3)})
                break
    return {
        "turns": len(valid),
        "speakers": dict(sorted(counts.items())),
        "question_mark_turns": questions,
        "explicitly_addressed_turns": addresses,
        "intention_phrase_turns": intentions,
        "same_speaker_near_duplicates": echoes,
        "near_duplicate_examples": echo_examples,
        "notes": ("These are transparent lexical proxies, not social-quality scores. "
                  "They do not prove task execution, genuine emotions, or "
                  "a reply to an Allen message. Those require provenance joins "
                  "and human-reviewed trace evaluation."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", required=True, type=Path)
    parser.add_argument("--last", type=int, default=160)
    args = parser.parse_args()
    feed = json.loads(args.feed.read_text(encoding="utf-8"))
    turns = feed.get("conversation") if isinstance(feed, dict) else feed
    if not isinstance(turns, list):
        raise ValueError("Expected list of turns or feed with conversation list")
    print(json.dumps(audit(turns[-args.last:]), indent=2))


if __name__ == "__main__":
    main()
