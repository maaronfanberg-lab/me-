#!/usr/bin/env python3
from __future__ import annotations

import room_private_commit as publish


def row(entity: str, text: str) -> tuple[str, str, str, str, list[str]]:
    target = next(name for name in ("sarah", "mara", "owen", "jules") if name != entity)
    return (entity, "answer", target, text, ["conversation"])


def main() -> None:
    live_4784 = [
        row("owen", "Hello, Jules! Let's discuss how individual differences might clash with the idea of collective effort and how the collective power of a collective effort can lead to significant change. In contrast to individual differences, we can be more confident that our actions can lead to systemic change and have a collective impact. Let's not be afraid to ask questions and share our perspectives."),
        row("jules", "Let's take a step back and reflect on the idea of collective effort and its potential to drive systemic change. Instead of focusing on individual differences, I would suggest that we focus on how our actions can lead to systemic change and have a collective impact. In contrast to individual differences, I would feel more confident that we can impact the collective effort and bring about significant change. Let's not."),
        row("sarah", "Let's break down the importance of collaboration in driving systemic change, emphasizing the collective effort and its potential impact on significant change. In contrast to individual differences, we should focus on how our actions can lead to systemic change, starting with a broad perspective and concrete examples."),
        row("mara", "In our next conversation, we can dive deeper into how our actions can drive significant systemic change, starting with a broad perspective and concrete examples. I believe that embracing collective effort can lead to impactful solutions, and I would be more confident that we can drive positive change through our collective efforts. Let's not let the individual differences overshadow our collective impact, but instead"),
    ]
    try:
        publish.validate_staged_quality(live_4784)
    except RuntimeError:
        print("ROOM PUBLISH PHRASE SIM: GREEN")
        return
    raise AssertionError("fresh replacement-runner cycle 4784 semantic phrase echo still publishes")


if __name__ == "__main__":
    main()
