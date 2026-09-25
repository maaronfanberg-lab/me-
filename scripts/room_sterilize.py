#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOM = ROOT / "room"
SOCIETY = ROOT / "society"
CONFIG = ROOM / "config.json"
MARKER = ROOM / "sterilization.json"
STERILIZATION_VERSION = 6


def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def rel_template() -> dict:
    return {
        "social_model": 3, "legacy_familiarity": 0.02, "exposure": 0.064,
        "direct_familiarity": 0.08, "trust": 0.10, "predictability": 0.12,
        "reciprocity": 0.08, "warmth": 0.12, "respect": 0.12,
        "disclosure_depth": 0.0, "tension": 0.0, "direct_turns": 0,
        "observed_turns": 0, "repair_attempts": 0, "repair_successes": 0,
        "last_direct_cycle": None, "shared_references": [], "events": [], "reports": [],
    }


def fresh_minds(order: list[str]) -> dict:
    return {"entities": {entity: {
        "fast": {"activation": 0.2, "attention": []},
        "medium": {"topics": [], "branch_interest": 0},
        "slow": {"social_energy": 0.55}, "noise": {}, "room_memories": [],
        "self_history": [], "last_event": None, "spoken": 0, "silences": 0,
        "people": {other: rel_template() for other in order if other != entity},
    } for entity in order}}


def clean_subject_state() -> dict:
    return {
        "semantic_schema": 3, "id": "topic-000000", "root": None,
        "current_facet": None, "facets": [], "visited_facets": [], "facet_index": 0,
        "unresolved": [], "examples": [], "disagreements": [], "shared_references": [],
        "participants": ["sarah", "mara", "owen", "jules"], "turns": 0,
        "low_novelty_beats": 0, "recent_terms": [], "last_shift_cycle": 0, "status": "forming",
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    stamp = now.isoformat().replace("+00:00", "Z")
    clean_boot = "room-sterile-v4-" + now.strftime("%Y%m%dT%H%M%S%fZ")

    cfg = load(CONFIG, {})
    cfg["boot_id"] = clean_boot
    save(CONFIG, cfg)

    order = ["sarah", "mara", "owen", "jules"]
    sleeping = {
        str(entity).strip().lower()
        for entity in (cfg.get("sleeping_entities") or [])
        if str(entity).strip()
    }
    awake = [entity for entity in order if entity not in sleeping]
    profiles = cfg.get("p", {})
    minds = fresh_minds(order)
    subject_state = clean_subject_state()
    subject_state["participants"] = awake + ["allen"]
    state = {
        "version": "room-cognition-v5", "boot_id": clean_boot, "cycle": 0,
        "silence_cycles": 0, "last_speaker": None, "last_run": stamp, "messages": 0,
        "last_public_event": None, "note": "fresh Room boot; prior conversation deleted",
        "last_beat_id": None, "beat_contributors": [], "beat_message_count": 0,
        "topic_episode": subject_state,
        "sleeping_entities": sorted(sleeping),
        "room_generation": int(cfg.get("room_generation", 6) or 6),
    }
    discourse = {"nodes": [], "roots": []}

    summary_entities = {}
    for entity in order:
        profile = profiles.get(entity, {})
        rels = minds["entities"][entity]["people"]
        summary_entities[entity] = {
            "name": profile.get("name", entity.title()),
            "status": "sleeping" if entity in sleeping else "awake",
            "profile": profile,
            "genome": profile.get("traits", {}),
            "development": {"turns": 0, "spoken": 0, "silences": 0, "topic_weights": {},
                "relationships": {other: {key: value for key, value in rel.items() if key in {
                    "exposure", "direct_familiarity", "trust", "predictability", "reciprocity",
                    "warmth", "respect", "disclosure_depth", "tension", "direct_turns", "repair_successes"
                }} for other, rel in rels.items()}},
            "memory": [],
        }

    live = {
        "generated_at": stamp, "architecture_version": "room-cognition-v5", "boot_id": clean_boot,
        "minds": {"schema": 5, "entities": summary_entities}, "profiles": profiles,
        "state": state, "conversation": [], "discourse": discourse, "topic_episode": subject_state,
        "network": {"compute_nodes": 12, "entities": 4, "nodes_per_entity": 3, "tasks_per_node": 4,
            "active_processes": 48, "voting": False, "public_bus": True, "private_scope": "same_entity",
            "beat_output": "4 mandatory unique speakers", "private_pipeline": "perception->deliberation->expression",
            "history_generation": clean_boot, "public_fallback": False, "contamination_gate": True,
            "semantic_grounding_gate": True, "identity_blind_expression": True},
    }
    feed = {"generated_at": stamp, "state": state, "minds": {"entities": summary_entities}, "conversation": []}

    save(ROOM / "conversation.json", [])
    save(ROOM / "discourse.json", discourse)
    save(ROOM / "cognitive_state.json", minds)
    save(ROOM / "state.json", state)
    save(ROOM / "live.json", live)
    save(ROOM / "feed.json", feed)
    save(SOCIETY / "conversation.json", [])
    save(SOCIETY / "minds.json", {"entities": {}})
    save(SOCIETY / "cognition.json", {"sterilized": True, "boot_id": clean_boot, "at": stamp})
    save(SOCIETY / "state.json", {"sterilized": True, "boot_id": clean_boot, "at": stamp})
    save(SOCIETY / "live.json", live)

    # Purge archived semantic/conversational reservoirs too. This resets what the
    # Room can remember, not merely what the live viewer happens to show.
    for archive in (ROOM / "archive", SOCIETY / "archive"):
        if archive.exists():
            shutil.rmtree(archive)

    for name in ("private-full-beat-diagnostic.json", "private-model-diagnostic.json", "private-secret-presence.json"):
        path = ROOM / name
        if path.exists(): save(path, {"sterilized": True, "boot_id": clean_boot, "at": stamp})

    save(MARKER, {"sterilization_version": STERILIZATION_VERSION, "boot_id": clean_boot,
        "sterilized_at": stamp, "policy": "Prior conversational and derived historical state deleted.",
        "reset": ["room conversation", "room discourse", "entity self histories", "entity room memories",
                  "relationship histories", "subject history", "live snapshots", "public feed",
                  "legacy society state", "room semantic archives", "society archives", "diagnostic historical traces"]})
    print(f"STERILIZED_V5 {clean_boot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
