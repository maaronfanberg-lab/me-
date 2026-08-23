#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def expression(text: str) -> str:
    return json.dumps({
        "target": "allen",
        "move": "answer",
        "utterance": text,
        "semantic_terms": ["platypus", "electroreception"],
    })


def main() -> None:
    truncated = (
        "I think we could explore different themes and use Harper Lee's writing as a foundation for a different genre. "
        "What themes do you have in mind for your next books or what"
    )
    repaired = engine._expression_quality.repair_expression(truncated, "sarah")
    assert repaired != truncated, "RED: mid-sentence truncation survived repair"
    assert not repaired.lower().endswith("or what"), "RED: dangling final clause survived repair"
    assert repaired[-1:] in ".!?", "repaired expression is not grammatically closed"
    assert engine._expression_quality.repair_expression("Guess what?", "sarah") == "Guess what?"
    assert engine._expression_quality.repair_expression("I think the ending matters.", "sarah") == "I think the ending matters."

    allen_words = "Why do platypuses have bills?"
    payload = {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": {"speaker": "allen", "text": allen_words, "cognition": {"target": "sarah"}},
        "context": [{"speaker": "allen", "text": allen_words, "cognition": {"target": "sarah"}}],
        "topic": {"root": "platypuses", "current_facet": "electroreception", "facets": ["electroreception"]},
        "partner": "allen",
        "relationship": {"warmth": 0.2, "respect": 0.2},
        "deliberation": {"action": "ANSWER", "focus": "electroreception"},
    }

    prompts: list[str] = []
    quality = engine._expression_quality
    wrapped_request = engine._private_model._request
    assert getattr(wrapped_request, "_room_retry_boundary", False), "production retry boundary is not installed"
    original_underlying = quality._original_request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, attempt=0):
        # Capture what crosses the expression transport boundary. Retry guidance
        # may change the private system/control message, but it must never enter
        # the conversational situation supplied as user data.
        prompts.append(prompt)
        if attempt == 0:
            return expression(allen_words)
        return expression("Allen, their bills contain electroreceptors that help them locate prey underwater.")

    quality._original_request = fake_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    try:
        result = engine._private_run("expression", payload, timeout=1)
    finally:
        quality._original_request = original_underlying
        if old_prompt is None:
            os.environ.pop("ROOM_NODE_PROMPT", None)
        else:
            os.environ["ROOM_NODE_PROMPT"] = old_prompt
        if old_url is None:
            os.environ.pop("ROOM_MODEL_URL", None)
        else:
            os.environ["ROOM_MODEL_URL"] = old_url

    assert result.get("utterance")
    assert len(prompts) >= 2, "retry probe did not force a second expression attempt"
    first_control, first_situation = engine._private_model._split_expression_prompt(prompts[0])
    second_control, second_situation = engine._private_model._split_expression_prompt(prompts[1])
    assert first_control != second_control, "retry did not change the private control instruction"
    assert first_situation == second_situation, "retry control contaminated conversational situation data"
    assert "use a different idea" not in second_situation.lower(), "retry instruction leaked into dialogue situation"
    assert "keep the reply concise" not in second_situation.lower(), "retry quality instruction leaked into dialogue situation"
    assert allen_words in second_situation, "Allen's newest words were lost during retry recovery"

    # Production runs 3870 and 3906 both stopped after consecutive malformed
    # comprehension JSON. Comprehension is observational support, not public
    # language, so exhausted parse retries must degrade to an explicit unknown
    # rather than killing the warm runner or inventing replacement cognition.
    comprehension_payload = {
        "entity": "sarah",
        "profile": {"traits": {"social_sensitivity": 0.9, "curiosity": 0.8}},
        "event": {
            "speaker": "allen",
            "text": "What do you make of the way people show care?",
            "cognition": {"target": "sarah"},
        },
        "context": [
            {
                "speaker": "allen",
                "text": "What do you make of the way people show care?",
                "cognition": {"target": "sarah"},
            }
        ],
        "topic": {"root": "themes", "current_facet": "care", "facets": ["care"]},
        "partner": "allen",
        "relationship": {"warmth": 0.2, "respect": 0.2},
        "conversation_job": "Add one concrete example or specific observation that has not already been stated.",
    }
    malformed_attempts: list[tuple[str, int]] = []
    original_request = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")

    def malformed_request(_url, _prompt, role, _temperature, _timeout, _self_entity=None, attempt=0):
        malformed_attempts.append((role, attempt))
        return (
            '{"participation":"DIRECT_ADDRESSEE","partner":"allen","move":"answer",'
            '"grounding":"understood","focus":"care","new_details":["unfinished'
        )

    engine._private_model._request = malformed_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    try:
        observation = engine._private_run("comprehension", comprehension_payload, timeout=1)
        try:
            engine._private_run("thought", comprehension_payload, timeout=1)
        except RuntimeError as exc:
            assert "private model output rejected for thought" in str(exc), "thought unexpectedly failed soft"
        else:
            raise AssertionError("thought must remain fail-closed after malformed structured output")
    finally:
        engine._private_model._request = original_request
        if old_prompt is None:
            os.environ.pop("ROOM_NODE_PROMPT", None)
        else:
            os.environ["ROOM_NODE_PROMPT"] = old_prompt
        if old_url is None:
            os.environ.pop("ROOM_MODEL_URL", None)
        else:
            os.environ["ROOM_MODEL_URL"] = old_url

    assert malformed_attempts[:2] == [("comprehension", 0), ("comprehension", 1)], (
        "comprehension did not exhaust its normal retry budget before fail-soft"
    )
    assert observation == {
        "participation": "DIRECT_ADDRESSEE",
        "partner": "allen",
        "move": "other",
        "grounding": "ambiguous",
        "focus": None,
        "new_details": [],
        "bids": [],
        "relationship_events": [],
        "shared_references": [],
        "confidence": 0.0,
    }, "fail-soft comprehension invented or retained unsupported cognition"

    serialized = json.dumps(observation, sort_keys=True).lower()
    for forbidden in (
        "unterminated",
        "retry",
        "conversation_job",
        "add one concrete example",
        "system prompt",
        "developer message",
    ):
        assert forbidden not in serialized, f"private failure/orchestration text leaked into cognition: {forbidden}"

    print("ROOM RETRY/TRUNCATION + COMPREHENSION FAIL-SOFT SIM: GREEN")


if __name__ == "__main__":
    main()
