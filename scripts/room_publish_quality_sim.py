#!/usr/bin/env python3
from __future__ import annotations

import room_private_commit as publish


def row(entity: str, text: str) -> tuple[str, str, str, str, list[str]]:
    target = next(name for name in ("sarah", "mara", "owen", "jules") if name != entity)
    return (entity, "answer", target, text, ["conversation"])


def main() -> None:
    # Exact live cycle 4708. These are the four strings about to cross the commit
    # boundary; the final gate must not depend on prompt context or temporary parts.
    live = [
        row("owen", "Sarah mentions figuring things out in a past conversation with jules."),
        row("jules", "SARA is not the only one having a past conversation with you. I know of the other people in the group. They are all having conversations with someone."),
        row("sarah", "The dialogue between Sarah and Owen was a bit different from the first conversation, especially with the mention of 'SARA'. Owen is not the only one having a past conversation with you. I know of the other people in the group. They are all having conversations with someone. I have heard that they are not the only people in the group."),
        row("mara", "Sarah is not the only one having a past conversation with you."),
    ]

    assert hasattr(publish, "validate_staged_quality"), "publish boundary has no same-beat semantic quality gate"
    try:
        publish.validate_staged_quality(live)
    except RuntimeError as exc:
        assert "same-beat" in str(exc).lower() or "echo" in str(exc).lower(), str(exc)
    else:
        raise AssertionError("live cycle 4708 semantic echo would still publish")

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
