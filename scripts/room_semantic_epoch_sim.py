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
    "shared_references": ["public-expression", "language model", "speak"],
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
    rel = ent.get("people", {}).get("allen", {})
    assert rel.get("direct_turns") == 32, f"RED: {entity}/Allen relationship was reset"
    assert rel.get("shared_references") == [], f"RED: {entity}/Allen retained old semantic relationship references"

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

# Upgrade an already-live semantic epoch without resetting its clean conversation/topic/memory.
v1_state = deepcopy(recovered_state)
v1_state.pop("relationship_semantic_version", None)
v1_state["topic_episode"] = {
    "semantic_schema": 4,
    "id": "topic-003864",
    "root": "books",
    "current_facet": "to kill a mockingbird",
    "facets": ["harper lee"],
    "participants": ["sarah", "mara", "owen", "jules", "allen"],
}
v1_minds = deepcopy(recovered_minds)
for ent in v1_minds["entities"].values():
    ent["room_memories"] = [{"source": "clean-1", "speaker": "mara", "text": "I found a book by Harper Lee"}]
    ent["self_history"] = [{"source": "clean-self", "text": "Books can change how a story feels"}]
    ent["people"]["allen"]["shared_references"] = ["public-expression", "language model", "speak"]
clean_conv = [{"id": "clean-1", "speaker": "mara", "text": "I found a book by Harper Lee"}]
clean_discourse = {"nodes": [{"id": "d-clean-1", "speaker": "mara", "text": "I found a book by Harper Lee"}], "roots": ["d-clean-1"]}

upgrade_state, upgrade_minds, upgrade_conv, upgrade_discourse, upgrade_archive, upgraded = recover_documents(
    v1_state,
    v1_minds,
    clean_conv,
    clean_discourse,
    "2026-08-20T13:10:00Z",
)
assert upgraded, "RED: live v1 state did not perform relationship semantic cleanup"
assert upgrade_archive is None, "RED: relationship-only cleanup created a second transcript archive"
assert upgrade_conv == clean_conv and upgrade_discourse == clean_discourse, "RED: relationship-only cleanup wiped live conversation"
assert upgrade_state.get("topic_episode") == v1_state.get("topic_episode"), "RED: relationship-only cleanup reset the live topic"
for entity, ent in upgrade_minds["entities"].items():
    assert ent.get("room_memories") == v1_minds["entities"][entity].get("room_memories"), f"RED: {entity} clean memory was reset"
    assert ent.get("self_history") == v1_minds["entities"][entity].get("self_history"), f"RED: {entity} clean self history was reset"
    assert ent["people"]["allen"].get("direct_turns") == 32, f"RED: {entity}/Allen counter changed during relationship cleanup"
    assert ent["people"]["allen"].get("shared_references") == [], f"RED: {entity}/Allen relationship text was not cleaned"

print("PASS: semantic epoch archives poisoned cognition, preserves people, and cleans relationship semantic residue without resetting live dialogue")
