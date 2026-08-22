#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room_engine_v5 as engine


def require(name: str, ok: bool, detail: object = "") -> None:
    if not ok:
        raise AssertionError(f"{name}: {detail}")
    print(f"PASS: {name}")


def relationship() -> dict:
    return {
        "exposure": .4,
        "direct_familiarity": .2,
        "trust": .2,
        "predictability": .2,
        "reciprocity": .2,
        "warmth": .2,
        "respect": .2,
        "disclosure_depth": 0,
        "tension": 0,
    }


def make_bus(latest: dict, partner: str) -> dict:
    base = {
        "event": latest,
        "context": [latest],
        "keywords": ["conversation", "response"],
        "topic": {"id": "topic-responsive", "root": "conversation", "current_facet": "response", "facets": [], "visited_facets": [], "status": "active", "shared_references": [], "unresolved": []},
        "partner": partner,
        "relationship": relationship(),
    }
    return {
        "private": {"sarah": [
            {"role": "comprehension", "private": {**base, "social_observation": {"participation": "PARTICIPANT"}}, "public": {"readiness": .1}},
            {"role": "thought", "private": base, "public": {"readiness": .2}},
            {"role": "expression", "private": base, "public": {"readiness": .8}},
        ]},
        "recurrent": {"sarah": {"thought": {"private": {"deliberation": {"action": "DEEPEN", "preferred_partner": partner, "focus": "response", "new_information_goal": "respond naturally"}}}}},
    }


def run_rank(core, rank: int, latest: dict, partner: str, prior: list[dict], key: str) -> tuple[dict, dict]:
    captured: dict = {}
    original_model_run = core.model_run
    original_prior = core.prior_expression_messages
    original_minds = core.minds
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    try:
        os.environ["ROOM_EXPRESSION_RANK"] = str(rank)
        core.prior_expression_messages = lambda node: list(prior)
        core.minds = lambda: {
            "entities": {
                "sarah": {
                    "people": {
                        "mara": relationship(),
                    }
                }
            }
        }

        def fake_model_run(role, payload):
            if role != "expression":
                return None
            captured["payload"] = payload
            event_speaker = str((payload.get("event") or {}).get("speaker") or "")
            target = str(payload.get("partner") or event_speaker or "mara")
            return {
                "decision": "SPEAK",
                "target": target,
                "move": "deepen",
                "utterance": f"I am responding to {target} here.",
                "semantic_terms": ["response"],
            }

        core.model_run = fake_model_run
        result = core.recurrent(2, key, make_bus(latest, partner))
        return captured.get("payload") or {}, (result.get("private") or {}).get("expression") or {}
    finally:
        core.model_run = original_model_run
        core.prior_expression_messages = original_prior
        core.minds = original_minds
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank


def allen_event(key: str) -> dict:
    return {"id": f"allen-{key}", "speaker": "allen", "text": "I think this is interesting.", "runtime": engine.VERSION, "boot_id": engine.BOOT, "cognition": {"target": None, "move_type": "deepen"}, "discourse_id": f"da-{key}"}


def ai_event(speaker: str, key: str) -> dict:
    return {"id": f"{speaker}-{key}", "speaker": speaker, "text": "Here is my thought about it.", "runtime": engine.VERSION, "boot_id": engine.BOOT, "cognition": {"target": "sarah", "move_type": "deepen"}, "discourse_id": f"d-{speaker}-{key}"}


def main() -> int:
    core = getattr(engine, "_core", engine)

    # Allen now has explicit high conversational gravity: all four voices stay
    # with his newest turn for the beat.
    rates = {}
    for rank in (0, 1, 2, 3):
        hits = 0
        total = 256
        for i in range(total):
            prior = [] if rank == 0 else [{
                "speaker": "mara",
                "text": "I already reacted to Allen's comment.",
                "cognition": {"target": "allen"},
            }]
            payload, expr = run_rank(core, rank, allen_event(f"{rank}-{i}"), "allen", prior, f"ordinary-allen-{rank}-{i}")
            if expr.get("target") == "allen" and ((payload.get("event") or {}).get("speaker") == "allen"):
                hits += 1
        rates[rank] = hits / total
    require("rank 0 always responds to ordinary Allen", rates[0] == 1.0, rates)
    require("rank 1 always responds to ordinary Allen", rates[1] == 1.0, rates)
    require("rank 2 always responds to ordinary Allen", rates[2] == 1.0, rates)
    require("rank 3 always responds to ordinary Allen", rates[3] == 1.0, rates)

    # Same-beat interaction should not show Mara as the current event while
    # leaving Sarah as the relationship/partner frame.
    latest = ai_event("sarah", "partner-follow")
    prior = [{"speaker": "mara", "text": "Sarah, I think there is another angle.", "cognition": {"target": "sarah"}}]
    payload, expr = run_rank(core, 2, latest, "sarah", prior, "entity-partner-follow")
    require("later voice sees Mara's newest same-beat line", ((payload.get("event") or {}).get("speaker") == "mara"), payload.get("event"))
    require("later voice partner follows Mara", payload.get("partner") == "mara", payload.get("partner"))
    require("later voice naturally targets Mara", expr.get("target") == "mara", expr)

    print("PASS: Room responsiveness boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
