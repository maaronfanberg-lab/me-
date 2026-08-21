#!/usr/bin/env python3
from __future__ import annotations

import room_engine_v5 as engine


def main() -> None:
    recurrent = engine._core.recurrent
    prior = engine._core.prior_expression_messages
    assert getattr(recurrent, "_room_ai_adjacency", False), (
        "production room_engine_v5 import did not install the AI adjacency recurrent wrapper"
    )
    assert getattr(prior, "__module__", "") == "room_ai_adjacency", (
        "production room_engine_v5 import did not install generation-rank same-beat chronology"
    )
    print("ROOM AI ADJACENCY WIRING SIM: GREEN")


if __name__ == "__main__":
    main()
