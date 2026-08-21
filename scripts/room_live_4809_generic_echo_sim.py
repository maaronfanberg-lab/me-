#!/usr/bin/env python3
from __future__ import annotations

import room_expression_quality as quality


def turn(speaker: str, text: str) -> dict:
    return {"speaker": speaker, "text": text, "cognition": {"target": "allen"}}


def no_similarity(_left: str, _right: str) -> float:
    return 0.0


def main() -> None:
    # Exact accepted live cycle 4809 after Allen explicitly complained about the
    # Room's brainstorm reflex. The later voices still converge on the same generic
    # collaboration/ideation process instead of contributing distinct content.
    mara = (
        "Allen, Hi, sarah. I'm trying to brainstorm some ideas for a new project. "
        "We've been working on something for a while now, but I think we're missing "
        "something in the process. Let's take a break and see what's actually working "
        "for us. Maybe we can come back to the project later and share what we come up "
        "with. I think we can work together to make this project successful."
    )
    owen = "We"
    jules = (
        "Come on, let's brainstorm a few ideas! Why haven't you been brainstorming "
        "about something? Any good thoughts on this?"
    )
    sarah = (
        "Hey, jules, let's take a step back and brainstorm some ideas. We can start by "
        "gathering more data and ideas from each other, and we can also talk about how "
        "we can use our collective knowledge to come up with the best strategy."
    )

    # A one-word pronoun fragment must never become a public Room turn.
    issue = quality.quality_issue(
        owen,
        {"context": [turn("mara", mara)], "event": turn("mara", mara)},
        "owen",
        no_similarity,
    )
    assert issue == "trivial_expression", f"live 4809 Owen fragment escaped: {issue!r}"

    # Repeating the same generic process proposal with minor wording changes is an
    # echo even when lexical overlap is too small for the phrase-shingle rules.
    issue = quality.same_beat_issue(jules, [turn("mara", mara), turn("owen", owen)])
    assert issue == "same_beat_generic_process_echo", f"live 4809 Jules echo escaped: {issue!r}"

    issue = quality.same_beat_issue(
        sarah,
        [turn("mara", mara), turn("owen", owen), turn("jules", jules)],
    )
    assert issue == "same_beat_generic_process_echo", f"live 4809 Sarah echo escaped: {issue!r}"

    # Negative control: sharing a process word is fine when the later speaker adds
    # a concrete, independently useful fact rather than another generic chorus.
    concrete = (
        "Brainstorming is fine, but the 1820 parish map labels the creek crossing "
        "Korpvad, so I'd use that as the village's working name and verify it against "
        "the tax register."
    )
    assert quality.same_beat_issue(concrete, [turn("mara", mara)]) is None, (
        "concrete new evidence was overblocked"
    )

    print("ROOM LIVE 4809 GENERIC ECHO SIM: GREEN")


if __name__ == "__main__":
    main()
