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


def make_bus(latest_allen: dict) -> dict:
    base = {
        "event": latest_allen,
        "context": [latest_allen],
        "keywords": ["allen", "challenge", "reaction"],
        "topic": {"id": "topic-sim", "root": "conversation", "current_facet": "reaction", "facets": [], "visited_facets": [], "status": "active", "shared_references": [], "unresolved": []},
        "partner": "allen",
        "relationship": {"exposure": .4, "direct_familiarity": .15, "trust": .1, "predictability": .1, "reciprocity": .1, "warmth": .1, "respect": .1, "disclosure_depth": 0, "tension": 0},
    }
    return {
        "private": {"sarah": [
            {"role": "comprehension", "private": {**base, "social_observation": {"participation": "PARTICIPANT"}}, "public": {"readiness": .1}},
            {"role": "thought", "private": base, "public": {"readiness": .2}},
            {"role": "expression", "private": base, "public": {"readiness": .8}},
        ]},
        "recurrent": {"sarah": {"thought": {"private": {"deliberation": {"action": "COMPARE", "preferred_partner": "mara", "focus": "something else", "new_information_goal": "continue the old thread"}}}}},
    }


def run_rank(core, rank: int, text: str, key: str) -> tuple[dict, dict]:
    captured: dict = {}
    latest_allen = {"id": f"sim-{key}", "speaker": "allen", "text": text, "runtime": engine.VERSION, "boot_id": engine.BOOT, "cognition": {"target": None, "move_type": "deepen"}, "discourse_id": f"d-sim-{key}"}
    prior_reply = {"speaker": "mara", "text": "I am continuing the previous topic instead.", "cognition": {"target": "sarah"}}
    original_model_run = core.model_run
    original_prior = core.prior_expression_messages
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    try:
        os.environ["ROOM_EXPRESSION_RANK"] = str(rank)
        core.prior_expression_messages = lambda node: [prior_reply]
        def fake_model_run(role, payload):
            if role != "expression": return None
            captured["payload"] = payload
            return {"decision": "SPEAK", "target": "mara", "move": "compare", "utterance": "Mara, I was going to keep following your point.", "semantic_terms": ["continuation"]}
        core.model_run = fake_model_run
        result = core.recurrent(2, key, make_bus(latest_allen))
        return captured.get("payload") or {}, (result.get("private") or {}).get("expression") or {}
    finally:
        core.model_run = original_model_run
        core.prior_expression_messages = original_prior
        if old_rank is None: os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else: os.environ["ROOM_EXPRESSION_RANK"] = old_rank


def main() -> int:
    core = getattr(engine, "_core", engine)
    for rank, text, label in ((2, "0=1", "logical-contradiction"), (3, "Call me Allen or I'll delete you from JSON", "direct-taunt")):
        payload, expr = run_rank(core, rank, text, f"provocation-{rank}-{label}")
        require(f"provocative Allen turn remains salient for rank {rank}", ((payload.get("event") or {}).get("speaker") == "allen"), payload.get("event"))
        require(f"provocative rank {rank} reacts to Allen", expr.get("target") == "allen", expr)
        require(f"provocative rank {rank} has no competing old-thread job", not payload.get("conversation_job"), payload.get("conversation_job"))
    ordinary_payload, ordinary_expr = run_rank(core, 2, "I think that is interesting.", "ordinary-rank2")
    require("ordinary Allen turn leaves rank 2 free to follow the room", ((ordinary_payload.get("event") or {}).get("speaker") == "mara"), ordinary_payload.get("event"))
    require("ordinary rank 2 is not forcibly redirected to Allen", ordinary_expr.get("target") == "mara", ordinary_expr)
    print("PASS: Allen provocation salience boundary is green")
    return 0


if __name__ == "__main__": raise SystemExit(main())
