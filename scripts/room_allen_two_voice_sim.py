#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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


def second_voice_expected(key: str) -> bool:
    # Rank 1 now stays with an ordinary Allen turn about 90% of the time.
    # Determinism keeps a replayed beat on the same routing decision.
    return hashlib.sha256(f"allen-responsive:1:{key}".encode()).digest()[0] < 230


def pick_key(expected: bool) -> str:
    for i in range(10000):
        key = f"allen-responsive-rank1-sim-{i}"
        if second_voice_expected(key) is expected:
            return key
    raise AssertionError("could not find deterministic test key")


def make_bus(latest_allen: dict) -> dict:
    base = {
        "event": latest_allen,
        "context": [latest_allen],
        "keywords": ["allen", "hello", "question"],
        "topic": {
            "id": "topic-sim",
            "root": "conversation",
            "current_facet": "greeting",
            "facets": [],
            "visited_facets": [],
            "status": "active",
            "shared_references": [],
            "unresolved": [],
        },
        "partner": "allen",
        "relationship": {
            "exposure": .4,
            "direct_familiarity": .15,
            "trust": .1,
            "predictability": .1,
            "reciprocity": .1,
            "warmth": .1,
            "respect": .1,
            "disclosure_depth": 0,
            "tension": 0,
        },
    }
    return {
        "private": {
            "sarah": [
                {"role": "comprehension", "private": {**base, "social_observation": {"participation": "PARTICIPANT"}}, "public": {"readiness": .1}},
                {"role": "thought", "private": base, "public": {"readiness": .2}},
                {"role": "expression", "private": base, "public": {"readiness": .8}},
            ]
        },
        "recurrent": {
            "sarah": {
                "thought": {
                    "private": {
                        "deliberation": {
                            "action": "COMPARE",
                            "preferred_partner": "mara",
                            "focus": "greeting",
                            "new_information_goal": "change the subject",
                        }
                    }
                }
            }
        },
    }


def run_rank1(core, key: str) -> tuple[dict, dict]:
    captured: dict = {}
    latest_allen = {
        "id": f"sim-{key}",
        "speaker": "allen",
        "text": "Hey, does anybody want to answer me?",
        "runtime": engine.VERSION,
        "boot_id": engine.BOOT,
        "cognition": {"target": None, "move_type": "follow_up"},
        "discourse_id": f"d-sim-{key}",
    }
    first_reply = {
        "speaker": "mara",
        "text": "I already answered Allen first.",
        "cognition": {"target": "allen"},
    }

    original_model_run = core.model_run
    original_prior = core.prior_expression_messages
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    try:
        os.environ["ROOM_EXPRESSION_RANK"] = "1"
        core.prior_expression_messages = lambda node: [first_reply]

        def fake_model_run(role, payload):
            if role != "expression":
                return None
            captured["payload"] = payload
            return {
                "decision": "SPEAK",
                "target": "mara",
                "move": "compare",
                "utterance": "Mara, I was going to compare your answer instead.",
                "semantic_terms": ["comparison"],
            }

        core.model_run = fake_model_run
        result = core.recurrent(2, key, make_bus(latest_allen))
        expression = (result.get("private") or {}).get("expression") or {}
        return captured.get("payload") or {}, expression
    finally:
        core.model_run = original_model_run
        core.prior_expression_messages = original_prior
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank


def main() -> int:
    core = getattr(engine, "_core", engine)
    positive = pick_key(True)
    negative = pick_key(False)

    yes_payload, yes_expr = run_rank1(core, positive)
    require(
        "selected rank-1 voice still sees Allen rather than the first AI reply",
        ((yes_payload.get("event") or {}).get("speaker") == "allen"),
        yes_payload.get("event"),
    )
    require("selected rank-1 voice targets Allen", yes_expr.get("target") == "allen", yes_expr)
    require("selected rank-1 voice deepens Allen's turn", str(yes_expr.get("move") or "").lower() == "deepen", yes_expr)
    require("selected rank-1 voice has no competing conversation job", not yes_payload.get("conversation_job"), yes_payload.get("conversation_job"))
    require(
        "selected rank-1 deliberation stays with Allen",
        str(((yes_payload.get("deliberation") or {}).get("preferred_partner") or "")).lower() == "allen",
        yes_payload.get("deliberation"),
    )

    no_payload, no_expr = run_rank1(core, negative)
    require(
        "unselected rank-1 voice remains free to follow the first AI reply",
        ((no_payload.get("event") or {}).get("speaker") == "mara"),
        no_payload.get("event"),
    )
    require("unselected rank-1 voice is not forcibly redirected to Allen", no_expr.get("target") == "mara", no_expr)

    ratio = sum(second_voice_expected(f"distribution-{i}") for i in range(4096)) / 4096
    require("rank-1 deterministic gate is approximately 90 percent", 0.88 <= ratio <= 0.92, ratio)
    print("PASS: Allen high-response rank-1 boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
