#!/usr/bin/env python3
"""Non-publishing, deterministic event-driven decision gate for Room agents.

This module chooses among *proposed* agent options. It does not generate speech,
invent motives or commit actions. A real agent must supply the proposals and the
world referee must verify any physical effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from room_life import AFFORDANCES, PEOPLE


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str
    source_event_id: str | None = None
    verb: str | None = None
    object: str | None = None


def visible(event: Mapping, person: str) -> bool:
    """Unknown visibility is never implicitly public."""
    visibility = event.get("visibility")
    if visibility == "public":
        return True
    if visibility != "private":
        return False
    witnesses = event.get("witnesses")
    return (person == str(event.get("speaker", "")).lower() or
            isinstance(witnesses, (list, tuple)) and person in
            [str(w).lower() for w in witnesses])


def decide(person: str, events: Sequence[Mapping], *,
           acknowledged: Sequence[str] = (),
           proposals: Sequence[Mapping] = (),
           active_task: Mapping | None = None) -> Decision:
    """Gate grounded, already proposed choices without mandatory speaking.

    Priority: explicitly addressed *unanswered* witnessed message; then an
    independently proposed and valid work choice; otherwise quiet observation.
    A pending address alone does not create a fabricated reply. Never replay
    an acknowledged event or interrupt existing work.
    """
    if person not in PEOPLE:
        raise ValueError("Unknown Room participant")
    seen = set(acknowledged)
    for event in reversed(events):
        if not isinstance(event, Mapping) or not visible(event, person):
            continue
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id or event_id in seen:
            continue
        speaker = str(event.get("speaker", "")).lower()
        addresses = event.get("addresses")
        if (speaker != person and speaker in (*PEOPLE, "allen") and
                isinstance(addresses, (list, tuple)) and
                person in [str(x).lower() for x in addresses]):
            for proposal in proposals:
                if (proposal.get("kind") == "reply" and
                        proposal.get("source_event_id") == event_id and
                        isinstance(proposal.get("text"), str) and
                        proposal["text"].strip()):
                    return Decision("reply", "grounded_unanswered_address", event_id)
            # Never pretend a reply exists; preserve pending event.
            return Decision("observe", "awaiting_grounded_reply", event_id)
    if active_task:
        return Decision("observe", "continuing_unfinished_task")
    for proposal in proposals:
        if proposal.get("kind") != "work":
            continue
        verb, obj = proposal.get("verb"), proposal.get("object")
        if isinstance(verb, str) and isinstance(obj, str) and (
                verb in AFFORDANCES and obj in AFFORDANCES[verb]):
            return Decision("work", "valid_independent_proposal",
                            verb=verb, object=obj)
    return Decision("observe", "no_grounded_proposal")
