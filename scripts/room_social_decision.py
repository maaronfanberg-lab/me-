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
    an acknowledged event or overwrite unfinished work. A grounded reply may
    coexist with an active task; no new work is started while occupied.
    """
    if person not in PEOPLE:
        raise ValueError("Unknown Room participant")
    # A colliding ledger ID cannot authenticate a reply opportunity.
    ids = [event.get("id") for event in events
           if isinstance(event, Mapping) and isinstance(event.get("id"), str)
           and event.get("id")]
    unique_ids = set()
    collisions = set()
    for event_id in ids:
        if event_id in unique_ids:
            collisions.add(event_id)
        unique_ids.add(event_id)
    seen = set(acknowledged) | collisions
    pending_address_id = None
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
                if not isinstance(proposal, Mapping):
                    continue
                if (proposal.get("kind") == "reply" and
                        proposal.get("source_event_id") == event_id and
                        isinstance(proposal.get("text"), str) and
                        proposal["text"].strip()):
                    # Speaking does not cancel or overwrite existing physical work.
                    # A grounded reply is allowed while an unfinished task persists;
                    # the world referee, not this pure decision gate, advances work.
                    return Decision("reply", "grounded_unanswered_address", event_id)
            # Preserve the unanswered address without blocking valid independent work.
            pending_address_id = event_id
            break
    if active_task:
        return Decision("observe", "continuing_unfinished_task", pending_address_id)
    for proposal in proposals:
        if not isinstance(proposal, Mapping):
            continue
        if proposal.get("kind") != "work":
            continue
        verb, obj = proposal.get("verb"), proposal.get("object")
        if isinstance(verb, str) and isinstance(obj, str) and (
                verb in AFFORDANCES and obj in AFFORDANCES[verb]):
            return Decision("work", "valid_independent_proposal",
                            verb=verb, object=obj)
    if pending_address_id:
        return Decision("observe", "awaiting_grounded_reply", pending_address_id)
    return Decision("observe", "no_grounded_proposal")


def decide_from_history(person: str, events: Sequence[Mapping], *,
                        acknowledged: Sequence[str] = (),
                        proposals: Sequence[Mapping] = (),
                        active_task: Mapping | None = None) -> Decision:
    """Join witnessed conversational bids to a *proposal*, without writing speech.

    The legacy public feed has no explicit visibility or addresses metadata.
    joint_context identifies genuine vocatives and permissible witnesses.
    Only absent legacy visibility is public; explicit unknown stays blocked.
    Raw duplicate IDs remain in the input to decide(), which rejects collisions.
    Nothing here generates a response or commits a world action.
    """
    from room_social_joint_context import joint_context

    bids = {bid["source_id"] for bid in joint_context(events, person)["open_bids"]}
    eligible = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_id = event.get("id")
        if not isinstance(event_id, str) or event_id not in bids:
            continue
        normalized = dict(event)
        if "visibility" not in normalized:
            normalized["visibility"] = "public"
        normalized["addresses"] = [person]  # Derived from witnessed bid, not model text.
        eligible.append(normalized)
    return decide(person, eligible, acknowledged=acknowledged,
                  proposals=proposals, active_task=active_task)
