#!/usr/bin/env python3
from __future__ import annotations

import room_private_commit as publish


def row(entity: str, text: str) -> tuple[str, str, str, str, list[str]]:
    target = next(name for name in ("sarah", "mara", "owen", "jules") if name != entity)
    return (entity, "answer", target, text, ["conversation"])


def assert_blocked(staged: list[tuple[str, str, str, str, list[str]]], label: str) -> None:
    try:
        publish.validate_staged_quality(staged)
    except RuntimeError as exc:
        assert "same-beat" in str(exc).lower() or "echo" in str(exc).lower(), str(exc)
    else:
        raise AssertionError(f"{label} semantic echo would still publish")


def main() -> None:
    # Exact live cycle 4708. These are the four strings about to cross the commit
    # boundary; the final gate must not depend on prompt context or temporary parts.
    live_4708 = [
        row("owen", "Sarah mentions figuring things out in a past conversation with jules."),
        row("jules", "SARA is not the only one having a past conversation with you. I know of the other people in the group. They are all having conversations with someone."),
        row("sarah", "The dialogue between Sarah and Owen was a bit different from the first conversation, especially with the mention of 'SARA'. Owen is not the only one having a past conversation with you. I know of the other people in the group. They are all having conversations with someone. I have heard that they are not the only people in the group."),
        row("mara", "Sarah is not the only one having a past conversation with you."),
    ]

    assert hasattr(publish, "validate_staged_quality"), "publish boundary has no same-beat semantic quality gate"
    assert_blocked(live_4708, "live cycle 4708")

    # Exact first beat from the replacement runner after PR #124. It proved the
    # final boundary was wired correctly but still counted conversational garnish
    # as semantic novelty, allowing one chart/test-bed/diverse-sound proposition to
    # be repackaged across the four voices.
    live_4777 = [
        row("mara", "In the past few weeks, we've been exploring the power of our music together and how it can be a powerful addition. To start, let's use different sound effects and cultural backgrounds to create a unique and expressive sound that resonates with a diverse audience. One of the first charts we've created is one that represents various cultures and sound effects. Let's also start by considering this chart as a testbed, as"),
        row("owen", "Here's the latest chart we've created to reflect our diverse backgrounds and sound effects. Let's start by exploring how it can enhance the sound and resonating the diverse audience. As we integrate this testbed to understand our cultural identity and musical style, we can create a unique and expressive sound that resonates with a diverse audience. What do you think this chart can do for our music and audience?"),
        row("jules", "Hey, you know how diverse music can sound interesting and fresh? Let's try incorporating a test bed with different sound effects and backgrounds to create something truly special and unique. That's exactly what we've been exploring together! What do you think a chart like that could do for our music and audience, Owen?"),
        row("sarah", "Hey, it’s been a while since we last talked about how diverse music sounds interesting and fresh! Let’s take a step closer and explore how it could enhance the sound and resonate with a diverse audience. To get started, let’s integrate a test bed with different sound effects and cultural backgrounds to create a unique and expressive sound that resonates with a diverse audience. The first chart we’ve created is one of"),
    ]
    assert_blocked(live_4777, "live cycle 4777")

    fresh = [
        row("mara", "The group keeps using vague labels, so I would choose one concrete event to discuss."),
        row("owen", "A useful test is whether everyone describes that event the same way before drawing conclusions."),
        row("jules", "I'd compare what each person actually observed, because disagreement about facts is different from disagreement about meaning."),
        row("sarah", "If the observations match, then the interesting question becomes why the same event mattered differently to each person."),
    ]
    publish.validate_staged_quality(fresh)
    print("ROOM PUBLISH QUALITY SIM: GREEN")


if __name__ == "__main__":
    main()
