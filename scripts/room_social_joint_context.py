#!/usr/bin/env python3
"""Source-bound conversational opportunities for the experimental social Room.

This is an observer and context compiler, NOT a floor scheduler, dialogue
template, LLM, recommendation mechanism, or production writer. The agents
remain free to reply, initiate, pursue their own work, observe, or rest.

It deliberately separates mentioning somebody from addressing them and
distinguishes a claimed response link from proof of mutual understanding.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re

from room_social_memory import PEOPLE, witnessed_history

_NAME = "|".join(sorted(PEOPLE))
# A vocative is a conservative, explicit address, not a reference to
# somebody's work: "Sarah, ..." is different from "Sarah's notebook".
_INITIAL_VOCATIVE = re.compile(
    rf'^\s*["“‘]?\s*(?:hey|hi|hello)\s+(?P<person>{_NAME})\s*[,!?.]|'
    rf'^\s*["“‘]?\s*(?P<direct>{_NAME})\s*[,!?.]', re.I
)


def _recipients(item: Mapping, text: str) -> set[str]:
    explicit = item.get("to")
    if isinstance(explicit, str):
        recipients = {explicit.lower().strip()}
    elif isinstance(explicit, (list, tuple)):
        recipients = {x.lower().strip() for x in explicit if isinstance(x, str)}
    else:
        recipients = set()
    recipients &= PEOPLE
    if recipients:
        return recipients
    # A name elsewhere in the sentence is not evidence of an addressee.
    m = _INITIAL_VOCATIVE.match(text)
    return {str(m.group("person") or m.group("direct")).lower()} if m else set()


def _can_witness(item: Mapping, person: str) -> bool:
    speaker = str(item.get("speaker") or "").lower()
    # Mirror witnessed_history exactly: absent legacy visibility is public,
    # but an explicit unknown/empty classification never grants access.
    visibility = item["visibility"] if "visibility" in item else "public"
    if visibility == "public":
        return True
    if visibility != "private":
        return False
    witnesses = item.get("witnesses")
    known = (
        {x.lower() for x in witnesses if isinstance(x, str)}
        if isinstance(witnesses, (list, tuple)) else set()
    )
    return person == speaker or person in known


def joint_context(events: Sequence[Mapping], person: str, *, limit: int = 6) -> dict:
    """Build voluntary, unresolved response opportunities from witnessed events.

    A directed bid is eligible only if it was witnessed by this participant.
    A later, explicitly linked reply can retire the bid only when that reply
    was also visible to the original speaker. Silence and unlinked turns
    never count as a reply, but neither is a reply mandatory.
    """
    if person not in PEOPLE:
        raise ValueError("Unknown Room participant")
    if not isinstance(limit, int) or limit < 0 or limit > 30:
        raise ValueError("limit out of bounds")

    history = witnessed_history(events, person)
    if not history:
        return {"person": person, "open_bids": [], "linked_reply_ids": [],
                "no_speech_required": True, "evidence": "witnessed_events_only"}

    # Keep first-appearance metadata, matching witnessed_history's duplicate
    # policy, and never admit source metadata absent from the owned history.
    original_by_id = {}
    for item in events:
        if isinstance(item, Mapping):
            event_id = str(item.get("id") or "")
            # Match the accessible first occurrence chosen by witnessed_history.
            # A hidden collision must never supply someone else's metadata.
            if (event_id and _can_witness(item, person)
                    and str(item.get("speaker") or "").lower() in PEOPLE
                    and str(item.get("text") or "").strip()):
                original_by_id.setdefault(event_id, item)

    witnessed_ids = {entry.event_id for entry in history}
    incoming = []
    for idx, entry in enumerate(history):
        if entry.speaker == person:
            continue
        source = original_by_id[entry.event_id]
        recipients = _recipients(source, entry.text)
        addressed = person in recipients
        allen_public = (
            entry.speaker == "allen"
            and not recipients
            and str(source.get("visibility") or "public").lower() == "public"
        )
        if addressed or allen_public:
            incoming.append((idx, entry, "allen_input" if allen_public
                             else ("question" if "?" in entry.text else "address")))

    answered = set()
    for idx, entry in enumerate(history):
        if entry.speaker != person:
            continue
        reply = original_by_id[entry.event_id]
        parent = reply.get("reply_to")
        if not isinstance(parent, str) or parent not in witnessed_ids:
            continue
        for first_idx, original, _ in incoming:
            # A reference to a future or unrelated event isn't a response.
            if first_idx >= idx or original.event_id != parent:
                continue
            # A private journal reply that its addressee never saw doesn't
            # count as delivered reciprocal communication.
            if _can_witness(reply, original.speaker):
                answered.add(parent)

    return {
        "person": person,
        "open_bids": [
            {"source_id": entry.event_id, "from": entry.speaker,
             "kind": kind, "text": entry.text, "at": entry.at}
            for _, entry, kind in incoming if entry.event_id not in answered
        ][-limit:] if limit else [],
        "linked_reply_ids": sorted(answered),
        "no_speech_required": True,
        "evidence": "witnessed_events_only",
    }
