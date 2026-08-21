#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import room_ai_adjacency as adjacency
import room_engine_v5 as engine


def _part(node: int, entity: str, rank: int, text: str) -> dict:
    return {
        "phase": "recurrent",
        "node": node,
        "entity": entity,
        "role": "expression",
        "private": {
            "intent": {"generation_rank": rank},
            "expression": {"target": "mara", "move": "deepen", "utterance": text},
        },
    }


def check_true_spoken_order() -> None:
    original_parts = engine._core.PARTS
    with tempfile.TemporaryDirectory() as tmp:
        parts = Path(tmp)
        engine._core.PARTS = parts
        try:
            # Reproduce the live 4036 rotation: Owen(node 8) -> Jules(node 11)
            # -> Sarah(node 2) -> Mara(node 5). Lexicographic filename order is
            # wrong for this rotation, so rank must be the source of truth.
            (parts / "recurrent-8.json").write_text(json.dumps(_part(8, "owen", 0, "first spoken")))
            (parts / "recurrent-11.json").write_text(json.dumps(_part(11, "jules", 1, "second spoken")))
            (parts / "recurrent-2.json").write_text(json.dumps(_part(2, "sarah", 2, "third spoken")))

            before_sarah = engine._core.prior_expression_messages(2)
            before_mara = engine._core.prior_expression_messages(5)
        finally:
            engine._core.PARTS = original_parts

    sarah_speakers = [item.get("speaker") for item in before_sarah]
    assert sarah_speakers == ["owen", "jules"], (
        "Sarah does not see the real same-beat spoken order; "
        f"got {sarah_speakers!r}"
    )
    assert before_sarah[-1]["speaker"] == "jules", "Sarah's newest same-beat event is not Jules"

    mara_speakers = [item.get("speaker") for item in before_mara]
    assert mara_speakers == ["owen", "jules", "sarah"], (
        "Mara does not see the real same-beat spoken order; "
        f"got {mara_speakers!r}"
    )
    assert before_mara[-1]["speaker"] == "sarah", "Mara's newest same-beat event is not Sarah"


def _bus() -> dict:
    stale_deliberation = {
        "action": "BRIDGE",
        "preferred_partner": "mara",
        "focus": "book collection",
        "new_information_goal": "talk about my shelf",
    }
    return {
        "private": {
            "sarah": [
                {
                    "role": "expression",
                    "private": {
                        "event": {"speaker": "mara", "text": "I bought another book.", "cognition": {"target": "sarah"}},
                        "context": [{"speaker": "mara", "text": "I bought another book.", "cognition": {"target": "sarah"}}],
                        "topic": {"root": "books", "current_facet": "collection"},
                        "partner": "mara",
                        "relationship": {"trust": 0.2},
                    },
                    "public": {"readiness": 0.8},
                }
            ]
        },
        "recurrent": {
            "sarah": {
                "thought": {"private": {"deliberation": stale_deliberation}}
            }
        },
    }


def check_fresh_reply_plan() -> None:
    newest = {
        "speaker": "owen",
        "text": "I think the ending fails because Scout never confronts Mayella's lie. What do you think?",
        "cognition": {"target": "sarah"},
    }
    captured = {}
    original_underlay = adjacency._original_recurrent
    original_prior = engine._core.prior_expression_messages
    original_minds = engine._core.minds
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")

    def fake_underlay(_node, _key, bus_data):
        captured["bus"] = bus_data
        return {
            "private": {
                "expression": {
                    "target": "jules",
                    "move": "bridge",
                    "utterance": "The collection is getting bigger.",
                }
            }
        }

    def fake_minds():
        return {
            "entities": {
                "sarah": {
                    "people": {
                        "owen": {
                            "exposure": 0.8,
                            "direct_familiarity": 0.7,
                            "trust": 0.4,
                            "predictability": 0.5,
                            "reciprocity": 0.5,
                            "warmth": 0.4,
                            "respect": 0.6,
                            "disclosure_depth": 0.1,
                            "tension": 0.1,
                        }
                    }
                }
            }
        }

    adjacency._original_recurrent = fake_underlay
    engine._core.prior_expression_messages = lambda _node: [newest]
    engine._core.minds = fake_minds
    os.environ["ROOM_EXPRESSION_RANK"] = "1"
    try:
        result = engine._participant_recurrent(2, "adjacency-sim", _bus())
    finally:
        adjacency._original_recurrent = original_underlay
        engine._core.prior_expression_messages = original_prior
        engine._core.minds = original_minds
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank

    passed = captured["bus"]
    expression_source = engine._core.rp(passed, "sarah", "expression")["private"]
    thought = passed["recurrent"]["sarah"]["thought"]["private"]["deliberation"]

    assert expression_source["partner"] == "owen", "later speaker relationship is not aligned to newest speaker"
    assert thought.get("preferred_partner") == "owen", "later speaker still plans for the old partner"
    assert thought.get("action") == "ANSWER", f"direct question did not refresh response action: {thought!r}"
    assert thought.get("focus") != "book collection", "stale pre-beat focus survived after a newer same-beat turn"
    assert not str(thought.get("new_information_goal") or "").strip(), "stale pre-beat aim survived after a newer same-beat turn"

    # RED regression for the live echo failure. The expression-quality gate can
    # only reject copying if the words just spoken in this beat are in the same
    # event/context payload that reaches expression generation.
    event = expression_source.get("event") or {}
    context = expression_source.get("context") or []
    assert event.get("speaker") == "owen" and event.get("text") == newest["text"], (
        "newest same-beat line is not the expression event; anti-echo validation is blind to it"
    )
    assert context and context[-1].get("speaker") == "owen" and context[-1].get("text") == newest["text"], (
        "newest same-beat line is missing from expression context; cross-voice novelty cannot reject echoes"
    )

    expression = (result.get("private") or {}).get("expression") or {}
    assert expression.get("target") == "owen", "published reply target is not the immediately preceding speaker"
    assert expression.get("move") == "answer", "direct question did not publish as an answer move"


def main() -> None:
    check_true_spoken_order()
    check_fresh_reply_plan()
    print("ROOM AI ADJACENCY SIM: GREEN")


if __name__ == "__main__":
    main()
