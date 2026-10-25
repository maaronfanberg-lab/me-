#!/usr/bin/env python3
"""Test an open conversational opportunity and personal agency at model input."""
from __future__ import annotations

import os

import room_private_model_autonomy_legacy as autonomy


MOTIVES = [
    "Understand who is being excluded.",
    "Explore strange biological possibilities.",
]


def scenario(text: str, *, speaker="jules", target=None) -> dict:
    return {
        "entity": "mara",
        "profile": {"name": "Mara", "psychology_v2": {
            "core_identity": "A cultural anthropologist who studies social rituals.",
            "motives": MOTIVES, "values": ["recognition", "dignity"],
            "attention_magnets": ["relationships", "social dynamics"],
            "cognitive_style": "Observe people before theorizing.",
        }},
        "event": {"id": "public-12", "speaker": speaker,
                  "text": text, "cognition": {"target": target}},
        "context": [{"id": "public-12", "speaker": speaker,
                     "text": text, "cognition": {"target": target}}],
        "topic": {},
        "deliberation": None,
        "relationship": {"trust": 0.7},
    }


def test_open_floor_motives_are_accessible():
    old = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
    try:
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        payload = autonomy._autonomy_compact(
            scenario("I wonder whether that story makes any sense."), "expression", "mara"
        )
        own = payload["self"]
        assert own["motives"] == MOTIVES
        assert own["values"] == ["recognition", "dignity"]
        assert own["cognitive_style"] == "Observe people before theorizing."
        social = payload["social_opportunity"]
        assert social["action_due"] == "open_floor_response_or_initiative"
        assert social["source_id"] == "public-12"
        assert social["prior_speaker"] == "jules"
        assert not social["question_visible"]
        assert payload["event"]["text"] == "I wonder whether that story makes any sense."
        assert payload["discussion"]["subject"] is None
        assert "change the subject" not in str(payload).lower()
    finally:
        if old is None:
            os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        else:
            os.environ["ROOM_CONVERSATIONAL_FLOOR"] = old


def test_direct_question_is_an_actual_response_opportunity():
    old = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
    try:
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        payload = autonomy._autonomy_compact(
            scenario("Mara, what do you think?", speaker="allen"), "expression", "mara"
        )
        assert payload["social_opportunity"]["action_due"] == "directed_response_or_repair"
        assert payload["social_opportunity"]["question_visible"] is True
        assert payload["event"]["speaker"] == "allen"
    finally:
        if old is None:
            os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        else:
            os.environ["ROOM_CONVERSATIONAL_FLOOR"] = old


if __name__ == "__main__":
    test_open_floor_motives_are_accessible()
    test_direct_question_is_an_actual_response_opportunity()
    print("PASS: character's own motives and witnessed conversational action shape expression")
