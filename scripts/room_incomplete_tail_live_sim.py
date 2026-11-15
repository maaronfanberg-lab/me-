#!/usr/bin/env python3
from __future__ import annotations

import room_expression_quality as quality


def check(label: str, source: str, expected: str) -> None:
    actual = quality.repair_expression(source, "jules")
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"


def main() -> None:
    check(
        "live dangling article",
        "I'm not sure if it's something to keep in the back of my mind. Could you help me find a.",
        "I'm not sure if it's something to keep in the back of my mind.",
    )
    check(
        "live dangling infinitive",
        "I know how important it is to care about others. I'm trying to figure out how to do that because I need to.",
        "I know how important it is to care about others.",
    )
    check(
        "short repeated phrase",
        "I would love to make a change and make a change, but I need a concrete place to start.",
        "I would love to make a change, but I need a concrete place to start.",
    )
    check(
        "normal article ending is not damaged",
        "I found a.",
        "I found a.",
    )
    print("ROOM LIVE INCOMPLETE-TAIL SIM: GREEN")


if __name__ == "__main__":
    main()
