#!/usr/bin/env python3
from __future__ import annotations

import room_engine_v5 as engine


def main() -> None:
    underlay = engine._original_recurrent
    prior = engine._core.prior_expression_messages
    model_run = engine._core.model_run
    assert getattr(underlay, "_room_ai_adjacency", False), (
        "production room_engine_v5 participant wrapper did not capture the AI adjacency recurrent underlay"
    )
    assert getattr(prior, "__module__", "") == "room_ai_adjacency", (
        "production room_engine_v5 import did not install generation-rank same-beat chronology"
    )
    assert getattr(model_run, "__module__", "") == "room_ai_adjacency", (
        "Room core still holds an import-time model runner instead of the late-bound validated proxy"
    )
    print("ROOM AI ADJACENCY WIRING SIM: GREEN")


if __name__ == "__main__":
    main()
