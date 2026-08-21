#!/usr/bin/env python3
from __future__ import annotations

"""Rotate an already-over-age Room topic before any cognition node runs.

The normal bounded-topic commit path rotates an episode when it reaches its age
limit. This preflight exists for runner handoffs and migrations: if persisted
state is already beyond that limit, no model call should consume one more stale
beat before the commit boundary gets a chance to repair it.
"""

import json
import sys
from pathlib import Path

import room_topic_bounded as bounded


def _load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _is_over_age(topic: dict) -> bool:
    try:
        turns = int((topic or {}).get("turns") or 0)
    except (TypeError, ValueError):
        turns = 0
    return turns >= int(bounded.MAX_EPISODE_UPDATES)


def preflight(state_path: Path, minds_path: Path, *, next_cycle: int | None = None) -> bool:
    """Replace an over-age persisted topic and align entity working-topic views.

    Returns True only when files were changed. Young/normal topics are byte-for-byte
    untouched so runner startup itself cannot cause gratuitous topic churn.
    """
    state_path = Path(state_path)
    minds_path = Path(minds_path)
    state = _load(state_path)
    topic = state.get("topic_episode")
    if not isinstance(topic, dict) or not topic.get("root") or not _is_over_age(topic):
        return False

    if next_cycle is None:
        try:
            next_cycle = int(state.get("cycle") or 0) + 1
        except (TypeError, ValueError):
            next_cycle = 1
    next_cycle = max(1, int(next_cycle))

    prior = dict(topic)
    prior["bridge_pending"] = True
    prior["status"] = "ready_to_bridge"
    prior["bridge_reason"] = "episode_age"
    replacement = bounded.new_topic_from_terms([], next_cycle, prior)
    if not replacement.get("root"):
        raise RuntimeError("Room topic preflight could not establish breakout subject")

    state["topic_episode"] = replacement

    minds = _load(minds_path)
    entities = minds.get("entities")
    if isinstance(entities, dict):
        visible_topics = [
            value for value in [
                replacement.get("root"),
                replacement.get("current_facet"),
                *list(replacement.get("facets") or [])[:6],
            ]
            if value
        ]
        deduped: list[str] = []
        for value in visible_topics:
            text = str(value).strip().lower()
            if text and text not in deduped:
                deduped.append(text)
        for record in entities.values():
            if not isinstance(record, dict):
                continue
            medium = record.get("medium")
            if not isinstance(medium, dict):
                medium = {}
                record["medium"] = medium
            medium["topics"] = list(deduped)

    _dump(state_path, state)
    if minds_path.exists() or minds:
        _dump(minds_path, minds)
    return True


def main(argv: list[str]) -> int:
    state_path = Path(argv[1]) if len(argv) > 1 else Path("room/state.json")
    minds_path = Path(argv[2]) if len(argv) > 2 else Path("room/cognitive_state.json")
    state = _load(state_path)
    try:
        next_cycle = int(state.get("cycle") or 0) + 1
    except (TypeError, ValueError):
        next_cycle = 1
    changed = preflight(state_path, minds_path, next_cycle=next_cycle)
    print("ROOM TOPIC PREFLIGHT: ROTATED" if changed else "ROOM TOPIC PREFLIGHT: unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
