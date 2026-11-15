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

# Diagnostic only: recognize recurring *intended* work on an affordance from
# room_life. This is not a judgment about whether the work happened or whether
# revisiting it was appropriate. Keep model behavior completely unchanged.
from room_life import AFFORDANCES

_VERB = "|".join(sorted(map(re.escape, AFFORDANCES), key=len, reverse=True))
_OBJ = "|".join(sorted((re.escape(obj) for objs in AFFORDANCES.values()
                        for obj in objs), key=len, reverse=True))
_EXPLICIT_WORK = re.compile(
    rf"\b(?P<verb>{_VERB})\s*\(\s*(?P<obj>{_OBJ})\b", re.I)
_NATURAL_WORK = re.compile(
    rf"\b(?P<verb>{_VERB})\b[^.!?\n]{{0,52}}?\b(?P<obj>{_OBJ})\b", re.I)


def proposed_work_signature(text: str) -> tuple[str, str] | None:
    """High-precision first intended verb/object, not a world-action receipt."""
    if not INTENT.search(text):
        return None
    for pattern in (_EXPLICIT_WORK, _NATURAL_WORK):
        for match in pattern.finditer(text):
            verb, obj = match.group("verb").lower(), match.group("obj").lower()
            if obj in AFFORDANCES[verb]:
                return verb, obj
    return None



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
    # A semantically different promise to inspect the *same notebook* is
    # invisible to a high Jaccard threshold. Count repeated intended work
    # signatures separately without treating them as near-duplicate dialogue.
    # Count at most once per turn and only against the preceding 80 turns.
    prior_work: dict[tuple[str, str, str], int] = {}
    repeated_work = 0
    work_examples = []
    seen_signatures = set()
    for i, (speaker, text) in enumerate(valid):
        signature = proposed_work_signature(text)
        if not signature:
            continue
        key = (speaker, *signature)
        seen_signatures.add(key)
        previous = prior_work.get(key)
        if previous is not None and i - previous <= 80:
            repeated_work += 1
            if len(work_examples) < 6:
                work_examples.append({
                    "turn_index": i, "prior_index": previous,
                    "speaker": speaker, "verb": signature[0], "object": signature[1],
                })
        prior_work[key] = i
    return {
        "turns": len(valid),
        "speakers": dict(sorted(counts.items())),
        "question_mark_turns": questions,
        "explicitly_addressed_turns": addresses,
        "intention_phrase_turns": intentions,
        "same_speaker_near_duplicates": echoes,
        "distinct_intended_work_signatures": len(seen_signatures),
        "repeated_intended_work_turns_within_80": repeated_work,
        "repeated_intended_work_examples": work_examples,
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
