#!/usr/bin/env python3
"""Regression: neither model wrapper may override chosen conversational intent."""
from __future__ import annotations

import os
import room_engine_v5 as engine
import room_engine_v5_legacy as legacy


def test_bypass():
    os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
    original = getattr(engine, "_LLAMA_ORIGINAL_RECURRENT", None)
    original_legacy = legacy._original_recurrent
    evidence = {
        "private": {"sarah": [{"role": "expression", "private": {"event": {
            "speaker": "mara", "text": "Mara's unrelated thought.",
            "cognition": {"target": "sarah"}}}}]},
        "recurrent": {"sarah": {"thought": {"private": {"deliberation": {
            "action": "DISAGREE",
            "preferred_partner": "owen",
            "new_information_goal": "Disagree with Owen specifically."
        }}}}}
    }
    observed = []
    def fake(node, key, bus):
        observed.append((node, key, bus))
        return {"observed": bus["recurrent"]["sarah"]["thought"]["private"]["deliberation"].copy()}
    engine._LLAMA_ORIGINAL_RECURRENT = fake
    legacy._original_recurrent = fake
    try:
        out = engine._coherent_recurrent(2, "floor-test", evidence)
        assert out["observed"]["action"] == "DISAGREE"
        assert out["observed"]["preferred_partner"] == "owen"
        assert observed[-1][2] is evidence
        observed.clear()
        out = legacy._participant_recurrent(2, "floor-test", evidence)
        assert out["observed"]["action"] == "DISAGREE"
        assert out["observed"]["preferred_partner"] == "owen"
        assert observed[-1][2] is evidence
    finally:
        if original is None:
            del engine._LLAMA_ORIGINAL_RECURRENT
        else:
            engine._LLAMA_ORIGINAL_RECURRENT = original
        legacy._original_recurrent = original_legacy
        os.environ.pop("ROOM_CONVERSATIONAL_FLOOR", None)


if __name__ == "__main__":
    test_bypass()
    print("PASS: selected-floor wrapper preserves independently chosen disagreement")
