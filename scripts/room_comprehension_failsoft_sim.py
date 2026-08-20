#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def main() -> None:
    payload = {
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
        # This is deliberately present to prove runner orchestration cannot be
        # copied into a fail-soft observation.
        "conversation_job": "Add one concrete example or specific observation that has not already been stated.",
    }

    attempts: list[int] = []
    original_request = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")

    def malformed(_url, _prompt, _role, _temperature, _timeout, _self_entity=None, attempt=0):
        attempts.append(attempt)
        return (
            '{"participation":"DIRECT_ADDRESSEE","partner":"allen","move":"answer",'
            '"grounding":"understood","focus":"care","new_details":["unfinished'
        )

    engine._private_model._request = malformed
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    try:
        result = engine._private_run("comprehension", payload, timeout=1)
        try:
            engine._private_run("thought", payload, timeout=1)
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

    assert attempts[:2] == [0, 1], "comprehension did not exhaust its normal retry budget before fail-soft"
    assert result == {
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

    serialized = json.dumps(result, sort_keys=True).lower()
    for forbidden in (
        "unterminated",
        "retry",
        "conversation_job",
        "add one concrete example",
        "system prompt",
        "developer message",
    ):
        assert forbidden not in serialized, f"private failure/orchestration text leaked into cognition: {forbidden}"

    print("ROOM COMPREHENSION FAIL-SOFT SIM: GREEN")


if __name__ == "__main__":
    main()
