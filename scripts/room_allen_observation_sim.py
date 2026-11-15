#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room_engine_v5 as engine
import room_participant as participant

AI = ("sarah", "mara", "owen", "jules")


def require(name: str, ok: bool, detail: object = "") -> None:
    if not ok:
        raise AssertionError(f"{name}: {detail}")
    print(f"PASS: {name}")


def main() -> int:
    observe = getattr(participant, "observe_allen_history", None)
    require("participant observation helper exists", callable(observe), observe)

    mind = engine.fresh_minds()
    state = engine.fresh_state()
    state["cycle"] = 50
    message = {
        "id": "20260819T220000000-allen-v5-sim",
        "at": "2026-08-19T22:00:00Z",
        "speaker": "allen",
        "text": "Sarah, what do you think about this?",
        "runtime": engine.VERSION,
        "boot_id": engine.BOOT,
        "beat_id": f"beat-{engine.BOOT}-000042",
        "beat_index": -1,
        "cognition": {
            "move_type": "follow_up",
            "target": "sarah",
            "topic_episode": "topic-000001",
            "topic_terms": ["think"],
        },
        "discourse_id": "d-20260819T220000000-allen-v5-sim",
        "parent_discourse_id": None,
        "derived_from": None,
    }
    node = {
        "id": message["discourse_id"],
        "speaker": "allen",
        "parent": None,
        "target": "sarah",
        "text": message["text"],
    }
    history = [message]
    discourse = {"nodes": [node], "roots": [node["id"]]}

    observed = observe(mind, history, discourse, state)
    require("one unseen Allen turn is observed", observed == 1, observed)

    for entity in AI:
        rel = mind["entities"][entity]["people"].get("allen", {})
        require(f"{entity} records Allen exposure", int(rel.get("observed_turns", 0)) == 1, rel)
        memories = mind["entities"][entity].get("room_memories") or []
        require(
            f"{entity} stores Allen as an observed room memory",
            any(item.get("source") == message["id"] and item.get("speaker") == "allen" for item in memories),
            memories[-3:],
        )

    sarah = mind["entities"]["sarah"]["people"]["allen"]
    require("explicit Allen-to-Sarah address is direct", int(sarah.get("direct_turns", 0)) == 1, sarah)
    for entity in ("mara", "owen", "jules"):
        rel = mind["entities"][entity]["people"]["allen"]
        require(f"{entity} does not invent direct address", int(rel.get("direct_turns", 0)) == 0, rel)

    seen = list(mind.get("participant_observation_ids") or [])
    require("processed Allen message ID is persisted", message["id"] in seen, seen)

    before = {
        entity: (
            int(mind["entities"][entity]["people"]["allen"].get("observed_turns", 0)),
            int(mind["entities"][entity]["people"]["allen"].get("direct_turns", 0)),
        )
        for entity in AI
    }
    second = observe(mind, history, discourse, state)
    after = {
        entity: (
            int(mind["entities"][entity]["people"]["allen"].get("observed_turns", 0)),
            int(mind["entities"][entity]["people"]["allen"].get("direct_turns", 0)),
        )
        for entity in AI
    }
    require("Allen history observation is idempotent", second == 0 and after == before, {"second": second, "before": before, "after": after})
    require("Allen remains outside autonomous entities", "allen" not in mind.get("entities", {}), mind.get("entities", {}).keys())

    print("PASS: Allen social observation persistence boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
