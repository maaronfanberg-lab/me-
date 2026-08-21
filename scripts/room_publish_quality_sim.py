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

    # Exact first two beats from the replacement runner after PR #125
    # (cycle_key 32498763751:1:*). 4783 still let later voices elaborate the same
    # collaboration/systemic-change proposition; 4784 then made the failure
    # unmistakable by repeating the individual-differences/collective-effort idea
    # through every voice with rhetorical padding counted as novelty.
    live_4783 = [
        row("mara", "I'm sorry, but I can't agree with everything you're saying. Sometimes it's the whole 'it is' thing that matters."),
        row("owen", "Let's move deeper into how we can use collaboration and support to drive systemic change, not just focusing on individual differences."),
        row("jules", "Hi, Mara. It's good to be pursuing deeper conversations in your world, but how about we step a little deeper into a more individualistic perspective. Let's focus on the impact of collaboration in driving systemic change, but in a way that isn't just about individual differences. Let’s be more concrete about the collective effort and how it can lead to significant change. Instead of focusing on specific individuals, I"),
        row("sarah", "Let's begin by breaking down the importance of collaboration in driving systemic change, emphasizing the collective effort and its potential impact on significant change. In contrast to individual differences, we should focus on how our actions can lead to systemic change, starting with a broad perspective and concrete examples."),
    ]
    assert_blocked(live_4783, "live cycle 4783")

    live_4784 = [
        row("owen", "Hello, Jules! Let's discuss how individual differences might clash with the idea of collective effort and how the collective power of a collective effort can lead to significant change. In contrast to individual differences, we can be more confident that our actions can lead to systemic change and have a collective impact. Let's not be afraid to ask questions and share our perspectives."),
        row("jules", "Let's take a step back and reflect on the idea of collective effort and its potential to drive systemic change. Instead of focusing on individual differences, I would suggest that we focus on how our actions can lead to systemic change and have a collective impact. In contrast to individual differences, I would feel more confident that we can impact the collective effort and bring about significant change. Let's not."),
        row("sarah", "Let's break down the importance of collaboration in driving systemic change, emphasizing the collective effort and its potential impact on significant change. In contrast to individual differences, we should focus on how our actions can lead to systemic change, starting with a broad perspective and concrete examples."),
        row("mara", "In our next conversation, we can dive deeper into how our actions can drive significant systemic change, starting with a broad perspective and concrete examples. I believe that embracing collective effort can lead to impactful solutions, and I would be more confident that we can drive positive change through our collective efforts. Let's not let the individual differences overshadow our collective impact, but instead"),
    ]
    assert_blocked(live_4784, "live cycle 4784")

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
