#!/usr/bin/env python3
from __future__ import annotations

import os

import room_engine_v5 as engine


def main() -> None:
    # RED from live cycle 4642. Production had authoritative same-beat parts,
    # while the compact expression context could still lose those lines.
    jules = {
        "speaker": "jules",
        "text": "Owen asks why we're focused on the team and the collective focus is important, and mara answers by quoting jules about her idea and then explaining the importance of data analysis.",
        "cognition": {"target": "sarah"},
    }
    sarah_echo = "Owen asks why we're focused on the team and the collective focus is important, and I answer by quoting a different partner about the importance of data analysis, then explaining why that is important."

    compact = {
        "event": {"speaker": "mara", "text": "Older compact event", "target": "sarah"},
        "context": [{"speaker": "mara", "text": "Older compact event", "target": "sarah"}],
    }

    original = engine._core.prior_expression_messages
    old_node = os.environ.get("ROOM_NODE_ID")
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    engine._core.prior_expression_messages = lambda _node: [jules]
    os.environ["ROOM_NODE_ID"] = "2"
    os.environ["ROOM_EXPRESSION_RANK"] = "3"
    try:
        issue = engine._expression_quality.quality_issue(
            sarah_echo,
            compact,
            "sarah",
            engine._private_model._utterance_similarity,
        )
    finally:
        engine._core.prior_expression_messages = original
        if old_node is None:
            os.environ.pop("ROOM_NODE_ID", None)
        else:
            os.environ["ROOM_NODE_ID"] = old_node
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank

    assert issue in {
        "same_beat_sentence_copy",
        "same_beat_short_echo",
        "same_beat_restatement_sentence",
        "same_beat_low_novelty",
    }, f"live-parts echo escaped quality gate: {issue!r}"
    print("ROOM LIVE PARTS ECHO SIM: GREEN")


if __name__ == "__main__":
    main()
