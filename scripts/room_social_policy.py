#!/usr/bin/env python3
"""Non-publishing deterministic opportunity policy for the Room social prototype.

This is a decision *proposal*, never a referee action or generated dialogue.
It intentionally has no clock, I/O, model call, or production side effects.
"""
from __future__ import annotations

from collections.abc import Mapping

from room_life import AFFORDANCES, PEOPLE


def choose_opportunity(person: str, life: Mapping, opportunities: list[Mapping]) -> dict:
    """Prefer witnessed direct requests, then unfinished work, else quiet.

    All candidate events must be explicitly visible. This deliberately does
    not invent a new task, a completed action, or a relationship.
    """
    if person not in PEOPLE:
        raise ValueError("Unknown character")
    if not isinstance(life, Mapping) or not isinstance(opportunities, list):
        raise ValueError("Malformed decision input")
    for event in opportunities:
        if not isinstance(event, Mapping):
            raise ValueError("Malformed opportunity")
        if event.get("kind") != "allen_request" or person not in event.get("addresses", ()):
            continue
        eid = event.get("id")
        if not isinstance(eid, str) or not eid:
            raise ValueError("Unidentified Allen request")
        visibility = event.get("visibility")
        witnesses = event.get("witnesses")
        if visibility == "public" or (visibility == "private" and
                isinstance(witnesses, (tuple, list)) and person in witnesses):
            return {"choice": "reply", "source_event_id": eid, "actor": person}
    task = life.get("task")
    if isinstance(task, Mapping) and task.get("status") in ("pending", "active"):
        verb, obj = task.get("verb"), task.get("object")
        if verb in AFFORDANCES and obj in AFFORDANCES[verb]:
            decision_id = task.get("decision_id")
            if isinstance(decision_id, str) and decision_id:
                return {"choice": "continue_work", "actor": person,
                        "decision_id": decision_id, "verb": verb, "object": obj}
    return {"choice": "quiet", "actor": person}
