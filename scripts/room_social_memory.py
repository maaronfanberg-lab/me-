#!/usr/bin/env python3
"""Experimental relationship-centered memory for a future non-Concordia Room engine.

This module is deliberately side-effect free. It derives personal memories only
from witnessed public events, never invents friendship history, and cannot
write to the production Room. Inspired by Park et al. (UIST 2023) and
Humanoid Agents (EMNLP 2023).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Mapping, Sequence

PEOPLE = frozenset(("sarah", "mara", "owen", "jules", "allen"))
TOKEN = re.compile(r"[a-z0-9']+")


def words(value: str) -> set[str]:
    return set(TOKEN.findall(value.lower()))


@dataclass(frozen=True)
class Experience:
    event_id: str
    speaker: str
    text: str
    at: str
    witnesses: tuple[str, ...]


def witnessed_history(events: Sequence[Mapping], person: str) -> list[Experience]:
    """A person's accessible history. No omniscient memory transfer."""
    if person not in PEOPLE:
        raise ValueError("Unknown Room participant")
    seen = set()
    result = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        eid = str(event.get("id") or "")
        speaker = str(event.get("speaker") or "").lower()
        text = str(event.get("text") or "").strip()
        # Old Room public feed is visible to all. New private events MUST
        # explicitly identify witnesses and are never globally visible.
        # Only absent legacy visibility is public. Explicitly empty, unknown
        # or malformed classifications fail closed, including for the actor.
        visibility = event["visibility"] if "visibility" in event else "public"
        raw_witnesses = event.get("witnesses")
        witnesses = (tuple(str(x).lower() for x in raw_witnesses)
                     if isinstance(raw_witnesses, (tuple, list)) else ())
        accessible = (visibility == "public" or
                      visibility == "private" and
                      (person in witnesses or speaker == person))
        if not eid or eid in seen or speaker not in PEOPLE or not text or not accessible:
            continue
        seen.add(eid)
        result.append(Experience(eid, speaker, text[:1200],
                                 str(event.get("at") or ""), witnesses))
    return result


def retrieve(events: Sequence[Experience], query: str, limit: int = 6) -> list[Experience]:
    """Recency + lexical relevance; no fabricated episodic memories."""
    query_terms = words(query)
    ranked = []
    for i, event in enumerate(events):
        overlap = len(query_terms & words(event.text))
        score = overlap * 5 + (i + 1) / max(1, len(events))
        ranked.append((score, i, event))
    ranked.sort(reverse=True)
    return [event for _, _, event in ranked[:max(0, limit)]]


def relationship_evidence(events: Sequence[Experience], person: str) -> dict:
    """Grounded interaction counts, not invented emotional affinity scores."""
    if person not in PEOPLE:
        raise ValueError("Unknown Room participant")
    counts = Counter()
    for event in events:
        if event.speaker == person:
            for other in PEOPLE - {person}:
                if re.search(r"\b" + re.escape(other) + r"\b", event.text.lower()):
                    counts[other] += 1
        elif event.speaker in PEOPLE:
            if re.search(r"\b" + re.escape(person) + r"\b", event.text.lower()):
                counts[event.speaker] += 1
    return dict(counts)


def context_for(person: str, events: Sequence[Mapping], current_subject: str) -> dict:
    memories = witnessed_history(events, person)
    return {
        "person": person,
        "recalled_events": [vars(x) for x in retrieve(memories, current_subject)],
        "interaction_evidence": relationship_evidence(memories, person),
        "rule": ("Use only witnessed events as facts. Friends may remember, disagree, "
                 "respond, act, or remain quiet. Never invent shared history or "
                 "claim an action occurred without a verified world event."),
    }
