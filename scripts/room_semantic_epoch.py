#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from room_social_v5 import migrate_minds, topic_template

SEMANTIC_EPOCH_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
ARCHIVE = ROOM / "archive" / "semantic-epoch-v1"


def _load(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text())


def _save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _semantic_memory_snapshot(minds: dict) -> dict:
    out = {"entities": {}}
    for entity, ent in (minds.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        out["entities"][entity] = {
            "fast": copy.deepcopy(ent.get("fast")),
            "medium": copy.deepcopy(ent.get("medium")),
            "room_memories": copy.deepcopy(ent.get("room_memories") or []),
            "self_history": copy.deepcopy(ent.get("self_history") or []),
            "last_event": ent.get("last_event"),
        }
    return out


def recover_documents(
    state: dict,
    minds: dict,
    conversation: list,
    discourse: dict,
    started_at: str,
):
    """Start one clean semantic epoch without resetting identity or relationships.

    The visible pre-recovery transcript/discourse is returned as an archive, while
    active cognition starts with an empty transcript, empty discourse tree, a new
    topic episode, and cleared semantic memories/attention. Social relationships,
    personality-bearing state, slow state, counters, and unknown future fields are
    preserved. Calling this again after version 1 is a no-op.
    """

    source_state = copy.deepcopy(state or {})
    source_minds = migrate_minds(copy.deepcopy(minds or {"entities": {}}))
    source_conversation = copy.deepcopy(conversation or [])
    source_discourse = copy.deepcopy(discourse or {"nodes": [], "roots": []})

    if int(source_state.get("semantic_epoch_version", 0) or 0) >= SEMANTIC_EPOCH_VERSION:
        return (
            source_state,
            source_minds,
            source_conversation,
            source_discourse,
            None,
            False,
        )

    cycle = int(source_state.get("cycle", 0) or 0)
    archive = {
        "semantic_epoch_version": SEMANTIC_EPOCH_VERSION,
        "archived_at": started_at,
        "previous_topic_episode": copy.deepcopy(source_state.get("topic_episode") or {}),
        "semantic_memory": _semantic_memory_snapshot(source_minds),
        "conversation": source_conversation,
        "discourse": source_discourse,
    }

    recovered_state = source_state
    recovered_state["semantic_epoch_version"] = SEMANTIC_EPOCH_VERSION
    recovered_state["semantic_epoch_started_at"] = started_at
    recovered_state["semantic_epoch_reason"] = "replace-pre-boundary-semantic-contamination"
    recovered_state["topic_episode"] = topic_template(cycle)
    recovered_state["last_public_event"] = None
    recovered_state["last_speaker"] = None
    recovered_state["last_beat_id"] = None
    recovered_state["beat_contributors"] = []
    recovered_state["beat_message_count"] = 0
    recovered_state["messages"] = 0
    recovered_state["silence_cycles"] = 0
    recovered_state["note"] = "semantic epoch v1: social continuity preserved; active semantic memory rebuilt cleanly"

    recovered_minds = source_minds
    for ent in (recovered_minds.get("entities") or {}).values():
        if not isinstance(ent, dict):
            continue
        ent["fast"] = {"activation": 0.2, "attention": []}
        ent["medium"] = {"topics": [], "branch_interest": 0}
        ent["room_memories"] = []
        ent["self_history"] = []
        ent["last_event"] = None

    return (
        recovered_state,
        recovered_minds,
        [],
        {"nodes": [], "roots": []},
        archive,
        True,
    )


def migrate_files(started_at: str | None = None) -> bool:
    started_at = started_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state_path = ROOM / "state.json"
    minds_path = ROOM / "cognitive_state.json"
    conversation_path = ROOM / "conversation.json"
    discourse_path = ROOM / "discourse.json"

    state = _load(state_path, {})
    minds = _load(minds_path, {"entities": {}})
    conversation = _load(conversation_path, [])
    discourse = _load(discourse_path, {"nodes": [], "roots": []})

    recovered_state, recovered_minds, recovered_conversation, recovered_discourse, archive, changed = recover_documents(
        state,
        minds,
        conversation,
        discourse,
        started_at,
    )
    if not changed:
        print("Semantic epoch v1 already active; no recovery needed")
        return False

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    if not (ARCHIVE / "conversation.json").exists():
        _save(ARCHIVE / "conversation.json", archive.get("conversation") or [])
    if not (ARCHIVE / "discourse.json").exists():
        _save(ARCHIVE / "discourse.json", archive.get("discourse") or {"nodes": [], "roots": []})
    if not (ARCHIVE / "semantic-state.json").exists():
        _save(
            ARCHIVE / "semantic-state.json",
            {
                "semantic_epoch_version": archive.get("semantic_epoch_version"),
                "archived_at": archive.get("archived_at"),
                "previous_topic_episode": archive.get("previous_topic_episode") or {},
                "semantic_memory": archive.get("semantic_memory") or {"entities": {}},
            },
        )

    _save(state_path, recovered_state)
    _save(minds_path, recovered_minds)
    _save(conversation_path, recovered_conversation)
    _save(discourse_path, recovered_discourse)
    print("Semantic epoch v1 recovery applied; transcript archived and social continuity preserved")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate"])
    args = parser.parse_args()
    if args.command == "migrate":
        migrate_files()


if __name__ == "__main__":
    main()
