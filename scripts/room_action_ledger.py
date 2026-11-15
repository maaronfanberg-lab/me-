"""Evidence-only projection of observed directed questions in the public Room.

This module does not guess whether an agent understood, agreed, answered,
or resolved anything. A later turn by the named recipient is only evidence
that they spoke later. Semantic response assessment is separate.
"""
from __future__ import annotations

from room_conversational_floor import (
    ORDER, audible_addressee, public_participant_turns,
)


def directed_question_evidence(history: list, recipient: str, *,
                               window: int = 32, maximum: int = 8) -> list[dict]:
    """Bounded, source-linked history of questions audibly sent to recipient.

    Ambiguous multi-recipient and merely third-person name mentions do not
    create an exclusive recipient debt. Only stable public source IDs survive.
    """
    person = str(recipient or "").strip().casefold()
    if person not in ORDER:
        return []
    if type(window) is not int or type(maximum) is not int:
        raise ValueError("bounds must be integers")
    if not (1 <= window <= 128 and 1 <= maximum <= 32):
        raise ValueError("bounds outside safe limits")
    public = public_participant_turns(list(history or []))[-window:]
    seen: set[str] = set()
    events: list[dict] = []
    for turn in public:
        source_id = str(turn.get("id") or "")
        if source_id in seen:
            continue
        seen.add(source_id)
        events.append(turn)

    records: list[dict] = []
    for i, item in enumerate(events):
        speaker = str(item.get("speaker") or "").strip().casefold()
        spoken = str(item.get("text") or "").strip()
        if speaker == person or not spoken.endswith("?"):
            continue
        if audible_addressee(speaker, spoken, ORDER) != person:
            continue
        # A subsequent turn by the named recipient may or may not answer.
        # Do not silently convert co-occurrence into semantic closure.
        later = [
            str(reply.get("id"))
            for reply in events[i + 1:]
            if str(reply.get("speaker") or "").strip().casefold() == person
        ]
        records.append({
            "kind": "directed_question",
            "source_id": str(item["id"]),
            "source_speaker": speaker,
            "recipient": person,
            "source_text": spoken[:500],
            "subsequent_recipient_turn_ids": later[:8],
            "semantic_resolution": "not_assessed",
            "provenance": "witnessed_public_utterance",
        })
    return records[-maximum:]
