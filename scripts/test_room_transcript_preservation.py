#!/usr/bin/env python3
"""The selected-floor model must hear complete observed conversational acts."""
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def _source_prompt():
    data = {
        "entity": "sarah",
        "event": {"speaker": "mara", "target": "sarah",
                  "text": "Sarah, why did you leave before I finished?"},
        "context": [
            {"speaker": "jules", "target": "mara",
             "text": "Mara, I couldn't hear your question."},
            {"speaker": "mara", "target": "sarah",
             "text": "Sarah, why did you leave before I finished?"},
        ],
        "discussion": {"subject": None, "focus": None, "related": []},
    }
    return "PERSONALITY\nSITUATION_DATA\n" + json.dumps(data) + "\nRETURN_STRUCTURED_DATA_ONLY\n"


def _body(prompt):
    return json.loads(prompt.split("\nSITUATION_DATA\n", 1)[1].split("\nRETURN_STRUCTURED_DATA_ONLY\n", 1)[0])


def test_complete_public_actions_in_selected_floor():
    source = _source_prompt()
    previous = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
    try:
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
        for role in ("thought", "comprehension", "expression"):
            prompt = engine._prepare_conversation_prompt(source, role)
            visible = _body(prompt)
            assert visible["context"][0]["text"] == "Mara, I couldn't hear your question."
            assert visible["context"][-1]["text"].endswith("before I finished?")
            assert visible["event"]["text"].startswith("Sarah, why")
            assert visible["discussion"]["subject"] is None
            assert prompt == source, "the selected mode must not rewrite public turns as word lists"
    finally:
        if previous is None:
            os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        else:
            os.environ["ROOM_CONVERSATIONAL_FLOOR"] = previous


def test_legacy_cue_masking_still_available():
    source = _source_prompt()
    previous = os.environ.get("ROOM_CONVERSATIONAL_FLOOR")
    try:
        os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "0"
        for role in ("thought", "expression"):
            transformed = _body(engine._prepare_conversation_prompt(source, role))
            assert "text" not in transformed["context"][0]
            assert transformed["context"][0]["cues"]
    finally:
        if previous is None:
            os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)
        else:
            os.environ["ROOM_CONVERSATIONAL_FLOOR"] = previous


if __name__ == "__main__":
    test_complete_public_actions_in_selected_floor()
    test_legacy_cue_masking_still_available()
    print("PASS: full public speech actions survive selected-floor model preparation")
