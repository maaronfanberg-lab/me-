#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import room_social_v5 as social
import room_engine_v5 as engine
import room_private_model as private_model

GENERATORS = ("sarah", "mara", "owen", "jules")
PARTICIPANTS = (*GENERATORS, "allen")


def require(name: str, ok: bool, detail: object = "") -> None:
    if not ok:
        raise AssertionError(f"{name}: {detail}")
    print(f"PASS: {name}")


def main() -> int:
    generators = tuple(engine.ORDER)
    require("autonomous generator iteration remains exactly four entities", generators == GENERATORS, generators)
    require("Allen is not generated as an autonomous entity", "allen" not in generators, generators)
    require("engine participant set contains Allen", tuple(engine.PARTICIPANTS) == PARTICIPANTS, engine.PARTICIPANTS)

    social_participants = tuple(getattr(social, "PARTICIPANTS", ()))
    require("social participant set contains Allen", social_participants == PARTICIPANTS, social_participants)
    require("social generator order remains exactly four", tuple(social.ORDER) == GENERATORS, social.ORDER)

    mind = {"entities": {entity: {"people": {}} for entity in GENERATORS}}
    social.migrate_minds(mind)
    require(
        "relationship migration creates Allen for every autonomous entity",
        all("allen" in mind["entities"][entity]["people"] for entity in GENERATORS),
        {entity: sorted(mind["entities"][entity]["people"]) for entity in GENERATORS},
    )

    allen_turn = {
        "id": "sim-allen",
        "speaker": "allen",
        "text": "Sarah, do you actually agree with that?",
        "cognition": {"target": "sarah", "move_type": "follow_up", "topic_terms": ["agreement"]},
        "discourse_id": "d-sim-allen",
        "parent_discourse_id": None,
    }
    event = social.classify_event("sarah", allen_turn, {"d-sim-allen": allen_turn})
    require(
        "social event classifier recognizes Allen as Sarah's direct addressee partner",
        isinstance(event, dict) and event.get("speaker") == "allen" and event.get("direct") is True,
        event,
    )

    topic = social.topic_template(1)
    require("topic participant state contains Allen", tuple(topic.get("participants", ())) == PARTICIPANTS, topic.get("participants"))

    social.observe_message(mind, allen_turn, 1, {"d-sim-allen": allen_turn})
    allen_rel = mind["entities"]["sarah"]["people"].get("allen", {})
    require(
        "direct Allen turn updates Sarah-to-Allen relationship state",
        int(allen_rel.get("direct_turns", 0)) >= 1 and int(allen_rel.get("observed_turns", 0)) >= 1,
        allen_rel,
    )

    expression_schema = private_model._schema("expression", "sarah")
    expression_targets = expression_schema["properties"]["target"].get("enum", [])
    require("expression schema can target Allen", "allen" in expression_targets, expression_targets)

    thought_schema = private_model._schema("thought", None)
    thought_targets = thought_schema["properties"]["preferred_partner"].get("enum", [])
    require("thought schema can choose Allen", "allen" in thought_targets, thought_targets)

    # room_engine_v5 is a compatibility wrapper; sense() remains bound to the
    # preserved core module. Patch the bindings that sense() actually resolves,
    # otherwise this simulator would accidentally read the live Room conversation.
    core = getattr(engine, "_core", engine)
    owners = (engine,) if core is engine else (engine, core)
    originals = {
        owner: (owner.conv, owner.minds, owner.state, owner.choose_partner)
        for owner in owners
    }
    try:
        current_state = engine.fresh_state()
        current_state["cycle"] = 41
        engine_mind = engine.fresh_minds()
        simulated_history = [{
            "id": "sim-allen-engine",
            "at": "2026-08-19T22:40:00Z",
            "speaker": "allen",
            "text": "Sarah, do you actually agree with that?",
            "runtime": engine.VERSION,
            "boot_id": engine.BOOT,
            "cognition": {"target": "sarah", "move_type": "follow_up"},
        }]
        for owner in owners:
            owner.conv = lambda history=simulated_history: history
            owner.minds = lambda value=engine_mind: value
            owner.state = lambda value=current_state: value
            owner.choose_partner = lambda *args, **kwargs: "mara"
        sensed = engine.sense(1, "allen-response-sim")
        private = sensed.get("private") or {}
        require("latest Allen turn remains active engine partner", private.get("partner") == "allen", private.get("partner"))
        relationship = private.get("relationship")
        require(
            "Allen engine partner has a usable relationship view",
            isinstance(relationship, dict) and "trust" in relationship and "tension" in relationship,
            relationship,
        )
    finally:
        for owner, values in originals.items():
            owner.conv, owner.minds, owner.state, owner.choose_partner = values

    # Behavioral regression: live history showed Allen turns followed by four AI
    # turns with zero Allen targets. Reproduce that exact routing failure without a
    # model by making rank 0 return an otherwise-valid turn aimed at another AI.
    captured: dict = {}
    original_model_run = core.model_run
    original_prior = core.prior_expression_messages
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    try:
        os.environ["ROOM_EXPRESSION_RANK"] = "0"
        core.prior_expression_messages = lambda node: []

        def fake_model_run(role, payload):
            if role != "expression":
                return None
            captured["payload"] = payload
            return {
                "decision": "SPEAK",
                "target": "mara",
                "move": "deepen",
                "utterance": "I was going to tell Mara something else.",
                "semantic_terms": ["elsewhere"],
            }

        core.model_run = fake_model_run
        latest_allen = {
            "id": "sim-allen-hi",
            "speaker": "allen",
            "text": "Will one of you please just say hi to me?",
            "runtime": engine.VERSION,
            "boot_id": engine.BOOT,
            "cognition": {"target": None, "move_type": "follow_up"},
            "discourse_id": "d-sim-allen-hi",
        }
        base = {
            "event": latest_allen,
            "context": [latest_allen],
            "keywords": ["please", "say", "hi"],
            "topic": {"id": "topic-sim", "root": "conversation", "current_facet": "greeting", "facets": [], "visited_facets": [], "status": "active", "shared_references": [], "unresolved": []},
            "partner": "allen",
            "relationship": {"exposure": .3, "direct_familiarity": .1, "trust": .1, "predictability": .1, "reciprocity": .1, "warmth": .1, "respect": .1, "disclosure_depth": 0, "tension": 0},
        }
        bus_data = {
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
                                "action": "DEEPEN",
                                "preferred_partner": "mara",
                                "focus": "greeting",
                                "new_information_goal": "change the subject",
                            }
                        }
                    }
                }
            },
        }
        routed = core.recurrent(2, "allen-direct-reply-sim", bus_data)
        expr = (routed.get("private") or {}).get("expression") or {}
        payload = captured.get("payload") or {}
        require("rank-0 expression still sees Allen as the newest event", ((payload.get("event") or {}).get("speaker") == "allen"), payload.get("event"))
        require("rank-0 Allen interruption is routed back to Allen", expr.get("target") == "allen", expr)
        require("rank-0 Allen interruption becomes an answer", str(expr.get("move") or "").lower() == "answer", expr)
        require("rank-0 Allen interruption does not inject a competing conversation job", not payload.get("conversation_job"), payload.get("conversation_job"))
        require("rank-0 Allen interruption deliberation is answer-oriented", str(((payload.get("deliberation") or {}).get("action") or "")).upper() == "ANSWER", payload.get("deliberation"))
        require(
            "rank-0 direct Allen reply says Allen in the spoken sentence",
            bool(re.search(r"\ballen\b", str(expr.get("utterance") or ""), re.I)),
            expr.get("utterance"),
        )
    finally:
        core.model_run = original_model_run
        core.prior_expression_messages = original_prior
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank

    print("PASS: Allen social participation and direct-reply boundary is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
