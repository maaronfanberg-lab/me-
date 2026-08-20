#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy

from room_semantic_epoch import recover_documents

START = "2026-08-20T12:30:00Z"

state = {
    "cycle": 3863,
    "boot_id": "room-sterile-v4-2026-08-18",
    "topic_episode": {
        "semantic_schema": 4,
        "id": "topic-000001",
        "root": "learning",
        "current_facet": "public-expression",
        "facets": ["skepticism", "language model", "speak"],
        "visited_facets": ["public expression", "memory"],
        "participants": ["sarah", "mara", "owen", "jules", "allen"],
    },
}

relationship = {
    "exposure": 0.43,
    "direct_familiarity": 0.11,
    "trust": 0.10,
    "predictability": 0.13,
    "reciprocity": 0.10,
    "warmth": 0.13,
    "respect": 0.12,
    "direct_turns": 32,
    "observed_turns": 50,
}

minds = {"entities": {}}
for entity in ("sarah", "mara", "owen", "jules"):
    minds["entities"][entity] = {
        "fast": {"activation": 0.87, "attention": ["skepticism", "public-expression"]},
        "medium": {"topics": ["learning", "skepticism"], "branch_interest": 0.8},
        "slow": {"social_energy": 0.55},
        "noise": {"kept": True},
        "room_memories": [
            {"source": "old-1", "speaker": "sarah", "text": "public-expression in INPUT_JSON"},
            {"source": "old-2", "speaker": "mara", "text": "remember skepticism better in the future"},
        ],
        "self_history": [{"source": "old-3", "text": "language model speak"}],
        "last_event": "old-3",
        "spoken": 3863,
        "silences": 0,
        "people": {"allen": deepcopy(relationship)},
    }

conversation = [
    {
        "id": "old-1",
        "at": "2026-08-20T12:20:00Z",
        "speaker": "sarah",
        "text": "public-expression in INPUT_JSON",
        "runtime": "room-cognition-v5",
        "boot_id": "room-sterile-v4-2026-08-18",
    },
    {
        "id": "old-2",
        "at": "2026-08-20T12:25:00Z",
        "speaker": "mara",
        "text": "remember skepticism better in the future",
        "runtime": "room-cognition-v5",
        "boot_id": "room-sterile-v4-2026-08-18",
    },
]

discourse = {
    "nodes": [{"id": "d-old-1", "speaker": "sarah", "text": "public-expression in INPUT_JSON"}],
    "roots": ["d-old-1"],
}

recovered_state, recovered_minds, active_conversation, active_discourse, archive, changed = recover_documents(
    state,
    minds,
    conversation,
    discourse,
    START,
)

assert changed, "RED: first recovery must perform a migration"
assert recovered_state.get("semantic_epoch_version") == 1
assert recovered_state.get("semantic_epoch_started_at") == START
assert (recovered_state.get("topic_episode") or {}).get("root") is None, "RED: poisoned topic root survived"
assert active_conversation == [], "RED: poisoned transcript remains active cognition"
assert active_discourse == {"nodes": [], "roots": []}, "RED: poisoned discourse remains active cognition"
assert [m.get("id") for m in archive.get("conversation", [])] == ["old-1", "old-2"], "RED: old transcript was deleted instead of archived"
assert (archive.get("previous_topic_episode") or {}).get("current_facet") == "public-expression", "RED: old topic was not archived"

for entity, ent in recovered_minds["entities"].items():
    assert ent.get("room_memories") == [], f"RED: {entity} retained poisoned semantic memory"
    assert ent.get("self_history") == [], f"RED: {entity} retained poisoned self history"
    assert ent.get("last_event") is None, f"RED: {entity} retained pre-epoch last event"
    assert (ent.get("fast") or {}).get("attention") == [], f"RED: {entity} retained poisoned attention"
    assert (ent.get("medium") or {}).get("topics") == [], f"RED: {entity} retained poisoned topic attention"
    assert ent.get("spoken") == 3863, f"RED: {entity} development counter was reset"
    assert ent.get("noise") == {"kept": True}, f"RED: {entity} unrelated state was reset"
    assert ent.get("people", {}).get("allen", {}).get("direct_turns") == 32, f"RED: {entity}/Allen relationship was reset"

# The first post-recovery participant turn enters an otherwise clean active transcript.
active_conversation.append({
    "id": "new-allen",
    "at": "2026-08-20T12:31:00Z",
    "speaker": "allen",
    "text": "Let's talk about bioluminescent mushrooms",
    "runtime": "room-cognition-v5-participant",
    "boot_id": "room-sterile-v4-2026-08-18",
})
assert [m.get("id") for m in active_conversation] == ["new-allen"]
assert "bioluminescent mushrooms" in active_conversation[0]["text"]

state2, minds2, conv2, discourse2, archive2, changed2 = recover_documents(
    recovered_state,
    recovered_minds,
    active_conversation,
    active_discourse,
    "2026-08-20T12:40:00Z",
)
assert not changed2, "RED: semantic recovery is not idempotent"
assert archive2 is None, "RED: second recovery created a duplicate archive"
assert state2 == recovered_state and minds2 == recovered_minds, "RED: second recovery mutated clean state"
assert conv2 == active_conversation and discourse2 == active_discourse, "RED: second recovery wiped new conversation"

print("PASS: semantic epoch archives poisoned cognition while preserving people and new participant turns")
