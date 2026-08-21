#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import room_topic_bounded as bounded
import room_topic_preflight as preflight


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_path = root / "state.json"
        minds_path = root / "cognitive_state.json"

        # Exact live shape inherited by post-PR139 runner before cycle 4866:
        # the episode is massively over-age but still looks active. Preflight must
        # rotate it before the first cognition node can consume stale process context.
        stale_topic = bounded.new_topic_from_terms(["use", "data", "page", "metrics"], 4815)
        stale_topic["turns"] = 101
        stale_topic["last_shift_cycle"] = 4815
        stale_topic["status"] = "active"
        stale_topic["bridge_pending"] = False
        stale_topic["bridge_reason"] = ""
        state = {"cycle": 4865, "topic_episode": stale_topic}
        minds = {
            "entities": {
                entity: {"medium": {"topics": ["use", "data", "metrics"]}}
                for entity in ("sarah", "mara", "owen", "jules")
            }
        }
        write(state_path, state)
        write(minds_path, minds)

        changed = preflight.preflight(state_path, minds_path, next_cycle=4866)
        assert changed is True, "over-age live topic was not rotated before cognition"
        after = read(state_path)
        after_minds = read(minds_path)
        topic = after["topic_episode"]
        old_vocab = [stale_topic.get("root"), stale_topic.get("current_facet"), *stale_topic.get("facets", []), *stale_topic.get("recent_terms", [])]
        assert topic.get("id") == "topic-004866", topic
        assert topic.get("turns") == 0, topic
        assert topic.get("last_shift_cycle") == 4866, topic
        assert topic.get("bridge_pending") is False and topic.get("bridge_reason") == "", topic
        assert topic.get("root") and not any(
            bounded._near(topic["root"], old) for old in old_vocab if old
        ), topic
        for entity, record in after_minds["entities"].items():
            topics = ((record or {}).get("medium") or {}).get("topics") or []
            assert topics and topics[0] == topic["root"], (entity, topics, topic)

        # A normal young episode must not be rewritten merely because a runner starts.
        fresh_topic = bounded.new_topic_from_terms(["garden", "soil", "rain"], 4866)
        fresh_topic["turns"] = max(0, bounded.MAX_EPISODE_UPDATES - 3)
        fresh_state = {"cycle": 4866, "topic_episode": fresh_topic}
        fresh_minds = {"entities": {"sarah": {"medium": {"topics": ["garden", "soil"]}}}}
        write(state_path, fresh_state)
        write(minds_path, fresh_minds)
        before_state = state_path.read_text()
        before_minds = minds_path.read_text()
        changed = preflight.preflight(state_path, minds_path, next_cycle=4867)
        assert changed is False, "fresh topic was rotated too early"
        assert state_path.read_text() == before_state
        assert minds_path.read_text() == before_minds

    print("ROOM TOPIC PREFLIGHT SIM: GREEN")


if __name__ == "__main__":
    main()
