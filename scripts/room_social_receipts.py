#!/usr/bin/env python3
"""Isolated evidence join between proposed work and referee-confirmed outcomes.

This does NOT commit world effects, run the production scheduler or treat an
agent's claim as a receipt. Caller must supply events from the trusted referee
ledger (room_life or its eventual replacement), not generated dialogue.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from room_life import AFFORDANCES, PEOPLE


def verify_work_receipt(person: str, decision_id: str, verb: str, obj: str,
                        requested_cycle: int, referee_events: Sequence[Mapping]) -> dict | None:
    """Return a grounded receipt only for an exact, later, trusted completion.

    The future referee adapter MUST populate decision_id, verb and object on
    committed events; existing legacy life events lack this provenance and
    intentionally cannot be upgraded into receipts by guessing from prose.
    """
    if person not in PEOPLE:
        raise ValueError("Unknown Room participant")
    if (not isinstance(decision_id, str) or not decision_id or
            not isinstance(verb, str) or not isinstance(obj, str) or
            verb not in AFFORDANCES or obj not in AFFORDANCES[verb] or
            not isinstance(requested_cycle, int) or isinstance(requested_cycle, bool) or
            requested_cycle < 0):
        raise ValueError("Invalid work request")
    receipts = []
    # A reused ledger identifier is ambiguous even if only one of its
    # records matches this decision. Do not certify a forged/colliding ID.
    ids = set()
    collisions = set()
    for event in referee_events:
        if isinstance(event, Mapping) and isinstance(event.get("id"), str) and event["id"]:
            if event["id"] in ids:
                collisions.add(event["id"])
            ids.add(event["id"])
    for event in referee_events:
        if not isinstance(event, Mapping):
            continue
        cycle = event.get("cycle")
        if (event.get("kind") != "work_completed" or
                event.get("actor") != person or
                event.get("source_decision_id") != decision_id or
                event.get("verb") != verb or event.get("object") != obj or
                event.get("visibility") not in ("public", "private") or
                (event.get("visibility") == "private" and
                 not isinstance(event.get("witnesses"), (list, tuple))) or
                not isinstance(cycle, int) or isinstance(cycle, bool) or
                cycle <= requested_cycle or
                not isinstance(event.get("id"), str) or not event["id"]):
            continue
        receipts.append(event)
    # Duplicate or contradictory ledger records are not proof of a unique
    # completion. Refuse to invent a tie-breaker.
    if len(receipts) != 1 or receipts[0]["id"] in collisions:
        return None
    event = receipts[0]
    return {"event_id": event["id"], "source_decision_id": decision_id,
            "actor": person, "verb": verb, "object": obj, "cycle": event["cycle"]}


def witnessed_receipt(receipt: Mapping | None, referee_event: Mapping,
                      person: str) -> bool:
    """Do not disclose a private completion even when a receipt exists."""
    if not receipt or person not in PEOPLE:
        return False
    if receipt.get("event_id") != referee_event.get("id"):
        return False
    visibility = referee_event.get("visibility")
    if visibility == "public":
        return True
    if visibility != "private":
        return False
    witnesses = referee_event.get("witnesses")
    return (person == referee_event.get("actor") or
            isinstance(witnesses, (tuple, list)) and
            person in [str(w).lower() for w in witnesses])
