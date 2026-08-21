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
        "exposure": .5,
        "direct_familiarity": .3,
        "trust": .25,
        "predictability": .25,
        "reciprocity": .25,
        "warmth": .25,
        "respect": .25,
        "disclosure_depth": 0,
        "tension": 0,
    }


def make_bus(event: dict, partner: str = "owen") -> dict:
    base = {
        "event": event,
        "context": [event],
        "keywords": ["question", "answer"],
        "topic": {
            "id": "topic-question",
            "root": "conversation",
            "current_facet": "questions",
            "facets": [],
            "visited_facets": [],
            "status": "active",
            "shared_references": [],
            "unresolved": [],
        },
        "partner": partner,
        "relationship": relationship(),
    }
    return {
        "private": {
            "sarah": [
                {"role": "comprehension", "private": {**base, "social_observation": {"participation": "DIRECT_ADDRESSEE"}}, "public": {"readiness": .1}},
                {"role": "thought", "private": base, "public": {"readiness": .2}},
                {"role": "expression", "private": base, "public": {"readiness": .8}},
            ]
        },
        "recurrent": {
            "sarah": {
                "thought": {
                    "private": {
                        "deliberation": {
                            "action": "DEEPEN",
                            "preferred_partner": partner,
                            "focus": "questions",
                            "new_information_goal": "introduce my own unrelated angle",
                        }
                    }
                }
            }
        },
    }


def question(speaker: str, target: str, text: str, key: str) -> dict:
    return {
        "id": f"{speaker}-{key}",
        "speaker": speaker,
        "text": text,
        "runtime": engine.VERSION,
        "boot_id": engine.BOOT,
        "cognition": {"target": target, "move_type": "deepen"},
        "discourse_id": f"d-{speaker}-{key}",
    }


def statement(speaker: str, key: str) -> dict:
    return {
        "id": f"{speaker}-{key}",
        "speaker": speaker,
        "text": "I was talking about something else.",
        "runtime": engine.VERSION,
        "boot_id": engine.BOOT,
        "cognition": {"target": "jules", "move_type": "deepen"},
        "discourse_id": f"d-{speaker}-{key}",
    }


def fake_minds() -> dict:
    people = {person: relationship() for person in ("mara", "owen", "jules", "allen")}
    return {"entities": {"sarah": {"people": people}}}


def run_case(base_event: dict, prior: list[dict], partner: str, key: str) -> tuple[dict, dict]:
    core = getattr(engine, "_core", engine)
    captured: dict = {}
    original_model_run = core.model_run
    original_prior = core.prior_expression_messages
    original_minds = core.minds
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    try:
        os.environ["ROOM_EXPRESSION_RANK"] = "2"
        core.prior_expression_messages = lambda _node: list(prior)
        core.minds = fake_minds

        def fake_model_run(role, payload):
            if role != "expression":
                return None
            captured["payload"] = payload
            intent = payload.get("deliberation") if isinstance(payload.get("deliberation"), dict) else {}
            answering = str(intent.get("action") or "").upper() == "ANSWER" and not payload.get("conversation_job")
            target = str(payload.get("partner") or "mara")
            return {
                "decision": "SPEAK",
                "target": target,
                "move": "answer" if answering else "deepen",
                "utterance": "Yes, because the evidence points that way." if answering else "Anyway, I want to talk about my own idea.",
                "semantic_terms": ["evidence" if answering else "idea"],
            }

        core.model_run = fake_model_run
        result = engine.recurrent(2, key, make_bus(base_event, partner))
        expression = (result.get("private") or {}).get("expression") or {}
        return captured.get("payload") or {}, expression
    finally:
        core.model_run = original_model_run
        core.prior_expression_messages = original_prior
        core.minds = original_minds
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank


def assert_answer_obligation(label: str, payload: dict, expression: dict, asker: str) -> None:
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    deliberation = payload.get("deliberation") if isinstance(payload.get("deliberation"), dict) else {}
    require(f"{label}: active event remains the question", event.get("speaker") == asker and str(event.get("text") or "").rstrip().endswith("?"), event)
    require(f"{label}: partner is the asker", payload.get("partner") == asker, payload.get("partner"))
    require(f"{label}: deliberation is ANSWER", str(deliberation.get("action") or "").upper() == "ANSWER", deliberation)
    require(f"{label}: no competing new-angle job", not payload.get("conversation_job"), payload.get("conversation_job"))
    require(f"{label}: expression targets asker", expression.get("target") == asker, expression)
    require(f"{label}: expression move is answer", str(expression.get("move") or "").lower() == "answer", expression)


def main() -> int:
    # Previous-beat direct question: the addressee must answer before wandering.
    previous_q = question("mara", "sarah", "Sarah, would you actually choose the train?", "previous")
    payload, expression = run_case(previous_q, [], "mara", "question-previous-beat")
    assert_answer_obligation("previous-beat direct question", payload, expression, "mara")

    # Same-beat direct question: a fresh question must override an older partner/thread.
    old_event = statement("owen", "old")
    same_beat_q = {
        "speaker": "mara",
        "text": "Sarah, do you think Owen is right?",
        "cognition": {"target": "sarah"},
    }
    payload, expression = run_case(old_event, [same_beat_q], "owen", "question-same-beat")
    assert_answer_obligation("same-beat direct question", payload, expression, "mara")

    # A question aimed at somebody else must not hijack Sarah's turn.
    other_q = {
        "speaker": "mara",
        "text": "Owen, would you go with that plan?",
        "cognition": {"target": "owen"},
    }
    payload, expression = run_case(old_event, [other_q], "owen", "question-for-someone-else")
    deliberation = payload.get("deliberation") if isinstance(payload.get("deliberation"), dict) else {}
    require("question for someone else does not force Sarah to answer", str(deliberation.get("action") or "").upper() != "ANSWER" or payload.get("partner") != "mara", {"partner": payload.get("partner"), "deliberation": deliberation})

    print("PASS: entity question-answering boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
