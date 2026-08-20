#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def payload(event_text: str = "What do you think about the garden?") -> dict:
    return {
        "entity": "owen",
        "profile": {"traits": {"skepticism": 0.93}},
        "event": {"speaker": "sarah", "text": event_text, "cognition": {"target": "owen"}},
        "context": [{"speaker": "sarah", "text": event_text, "cognition": {"target": "owen"}}],
        "topic": {"root": "garden", "current_facet": "plants", "facets": ["plants"]},
        "partner": "sarah",
        "relationship": {"warmth": 0.5, "respect": 0.6},
        "deliberation": {"action": "ANSWER", "focus": "plants", "new_information_goal": "add one fresh point"},
    }


def expression(text: str) -> str:
    return json.dumps({"target":"sarah","move":"answer","utterance":text,"semantic_terms":["garden"]})


def run_sequence(items: list[str], source: dict | None = None):
    calls = []
    original = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")
    def fake_request(_url, _prompt, _role, _temperature, _timeout, _self_entity=None, _attempt=0):
        calls.append(1)
        return items[min(len(calls)-1, len(items)-1)]
    engine._private_model._request = fake_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled"
    os.environ["ROOM_MODEL_URL"] = "http://sim.invalid"
    try:
        result = engine._private_run("expression", source or payload(), timeout=1)
    finally:
        engine._private_model._request = original
        if old_prompt is None: os.environ.pop("ROOM_NODE_PROMPT", None)
        else: os.environ["ROOM_NODE_PROMPT"] = old_prompt
        if old_url is None: os.environ.pop("ROOM_MODEL_URL", None)
        else: os.environ["ROOM_MODEL_URL"] = old_url
    return result, len(calls)


def require_retry(label: str, bad: str, good: str, source: dict | None = None):
    result, calls = run_sequence([expression(bad), expression(good)], source)
    assert calls >= 2, f"{label}: bad expression was accepted"
    assert result.get("utterance") == good, f"{label}: clean retry was not returned"


def main():
    require_retry(
        "cross-identity claim",
        "Hello, Sarah. I am Sarah and I think we should focus on clarity.",
        "Sarah, I think we should focus on clarity.",
    )
    require_retry(
        "instruction echo newest spoken line",
        "Let's focus on the newest spoken line and use it to drive the conversation.",
        "The garden question is more interesting if we compare shade with direct sun.",
    )
    require_retry(
        "instruction echo sentence-count rule",
        "One to three sentences would be best here.",
        "I would start with the plants that tolerate the least light.",
    )
    require_retry(
        "instruction echo concrete-example rule",
        "Add one concrete example or specific observation that has not already been stated.",
        "The basil by the window wilted faster than the mint.",
    )
    source = payload("What do you mean by a new spoken line?")
    clean = "By a new spoken line, I mean the next sentence someone says aloud."
    result, calls = run_sequence([expression(clean)], source)
    assert calls == 1, "participant-origin phrase was over-blocked"
    assert result.get("utterance") == clean
    print("ROOM EXPRESSION INTEGRITY SIM: GREEN")


if __name__ == "__main__":
    main()
