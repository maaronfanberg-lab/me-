#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import room_engine_v5 as engine


SARAH = "I understand, but why should the group be different from the group?"
MARA = (
    "Understood, the group believes it views itself differently. "
    "It views itself differently from the group because of various factors, including personal views, "
    "a sense of belonging to the group, and a desire to maintain their identity and perspective."
)
MARA_EXACT = "Understood, the group believes it views itself differently."
FRESH = "One distinction is whether individual members disagree privately even when the group sounds unified in public."


def _part(node: int, entity: str, rank: int, text: str) -> dict:
    return {
        "phase": "recurrent",
        "node": node,
        "entity": entity,
        "role": "expression",
        "private": {
            "intent": {"generation_rank": rank, "readiness": 0.8, "latency": 0.1},
            "expression": {
                "target": "owen",
                "move": "deepen",
                "utterance": text,
                "semantic_terms": ["group", "views"],
            },
        },
        "public": {"readiness": 0.8},
    }


def _bus() -> dict:
    history = [
        {"speaker": "jules", "text": "We have been discussing whether the group has a shared view.", "cognition": {"target": "owen"}},
    ]
    expression_private = {
        "event": history[-1],
        "context": history,
        "topic": {
            "root": "group",
            "current_facet": "views",
            "facets": ["views", "perspective"],
            "shared_references": [],
            "unresolved": [],
        },
        "partner": "jules",
        "relationship": {"trust": 0.4, "respect": 0.5},
    }
    return {
        "private": {
            "owen": [
                {
                    "role": "comprehension",
                    "private": {"social_observation": {"grounding": "understood"}},
                    "public": {"readiness": 0.5},
                },
                {
                    "role": "expression",
                    "private": expression_private,
                    "public": {"readiness": 0.8},
                },
            ]
        },
        "recurrent": {
            "owen": {
                "thought": {
                    "private": {
                        "deliberation": {
                            "action": "DEEPEN",
                            "preferred_partner": "jules",
                            "focus": "group views",
                            "new_information_goal": "say something about the group",
                        }
                    }
                }
            }
        },
    }


def _model(text: str) -> str:
    return json.dumps({
        "target": "mara",
        "move": "answer",
        "utterance": text,
        "semantic_terms": ["group", "views"],
    })


def main() -> None:
    original_parts = engine._core.PARTS
    original_request = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    prompts: list[str] = []
    replies = [_model(MARA_EXACT), _model(FRESH)]

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, _attempt=0):
        prompts.append(prompt)
        return replies[min(len(prompts) - 1, len(replies) - 1)]

    with tempfile.TemporaryDirectory() as tmp:
        parts = Path(tmp)
        engine._core.PARTS = parts
        (parts / "recurrent-02.json").write_text(json.dumps(_part(2, "sarah", 0, SARAH)))
        (parts / "recurrent-05.json").write_text(json.dumps(_part(5, "mara", 1, MARA)))
        engine._private_model._request = fake_request
        os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
        os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
        os.environ["ROOM_EXPRESSION_RANK"] = "2"
        try:
            result = engine._participant_recurrent(8, "live-4697-pipeline", _bus())
        finally:
            engine._core.PARTS = original_parts
            engine._private_model._request = original_request
            if old_prompt is None:
                os.environ.pop("ROOM_NODE_PROMPT", None)
            else:
                os.environ["ROOM_NODE_PROMPT"] = old_prompt
            if old_url is None:
                os.environ.pop("ROOM_MODEL_URL", None)
            else:
                os.environ["ROOM_MODEL_URL"] = old_url
            if old_rank is None:
                os.environ.pop("ROOM_EXPRESSION_RANK", None)
            else:
                os.environ["ROOM_EXPRESSION_RANK"] = old_rank

    expression = (result.get("private") or {}).get("expression") or {}
    assert MARA in prompts[0], "live 4697 pipeline: Mara's same-beat words never reached the expression prompt"
    assert len(prompts) >= 2, "live 4697 pipeline: exact Mara same-beat echo was accepted on the first attempt"
    assert expression.get("utterance") == FRESH, "live 4697 pipeline: retry did not select the fresh contribution"
    print("ROOM LIVE ECHO PIPELINE SIM: GREEN")


if __name__ == "__main__":
    main()
