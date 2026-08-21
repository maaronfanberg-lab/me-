#!/usr/bin/env python3
from __future__ import annotations

import room_expression_quality as quality
import room_expression_quality_sim as expression_sim


def turn(speaker: str, text: str) -> dict:
    return {"speaker": speaker, "text": text, "cognition": {"target": "allen"}}


def require_source_echo(label: str, text: str, prior: list[dict]) -> None:
    issue = quality.same_beat_issue(text, prior)
    assert issue == "same_beat_source_echo", f"{label} escaped per-source boundary: {issue!r}"


def main() -> None:
    # Fresh post-PR130 cycle 4794. Sarah is the third autonomous voice, so two
    # earlier turns exist. She nevertheless rebuilds Jules's compact proposition
    # "explore ... villages and names" with the same anchors reordered.
    live_4794_owen = (
        "I'm sorry, I'm not sure if the information is complete or clear. Can you provide more details or ask some follow-up questions? We can work on it together."
    )
    live_4794_jules = (
        "Alright, let's start with the research and testing phases. The diversity of our team is crucial for a strong and cohesive village, and it's essential that our team functions efficiently. "
        "Let’s build some ground rules, and then move on to the exciting ideas for the villages and names. Let’s explore the possibilities for our village and see if we can make something new and innovative."
    )
    live_4794_sarah = (
        "Hey, how about we explore a few more ideas for the villages and their names? Let's see if there's anything we can't work out, or if we need to expand on a few of the names. Any ideas already?"
    )
    require_source_echo(
        "live cycle 4794 Sarah",
        live_4794_sarah,
        [turn("owen", live_4794_owen), turn("jules", live_4794_jules)],
    )

    # Cycle 4795 shows both forms of the same gap. Mara repeats Sarah's compact
    # "passionate and driven by something deeper" proposition; later Jules
    # reconstructs Owen's common-thread / passion / goal / team-efficiency frame.
    live_4795_sarah = (
        "I believe we all have a part of ourselves that is passionate and driven by something deeper than the task at hand, and that is what we call our purpose."
    )
    live_4795_mara = (
        "I understand your feelings, Jules, and I can sense that you are passionate and driven by something deeper. Let's take a step back and think about what that deeper part is. Would you like to share your thoughts or could you provide some guidance for my ideas?"
    )
    require_source_echo(
        "live cycle 4795 Mara",
        live_4795_mara,
        [turn("sarah", live_4795_sarah)],
    )

    live_4795_owen = (
        "Let's start by identifying the common thread that brings us together. I believe our shared passion for innovation and a desire to solve problems. Could we consider our goal to revolutionize our team's efficiency? "
        "Let's brainstorm a few ideas for how to achieve this, focusing on how we can use resources we have. How do we build a cohesive team?"
    )
    live_4795_jules = (
        "I can see that the topic we're talking about revolves around innovation and efficiency. We need to identify common threads that connect our passion to a goal of revolutionizing the efficiency of our team. What would you like to suggest?"
    )
    require_source_echo(
        "live cycle 4795 Jules",
        live_4795_jules,
        [
            turn("sarah", live_4795_sarah),
            turn("mara", live_4795_mara),
            turn("owen", live_4795_owen),
        ],
    )

    # The same shared predicate must regenerate the offending later voice before
    # the publication backstop sees the four-turn batch.
    source = expression_sim.payload(live_4795_owen, speaker="owen")
    prior = [
        turn("sarah", live_4795_sarah),
        turn("mara", live_4795_mara),
        turn("owen", live_4795_owen),
    ]
    source["context"] = [dict(item) for item in prior]
    source["event"] = dict(prior[-1])
    clean_retry = (
        "I would name the village after the raven's old Norse call; that gives the opening scene a clue that can later complicate the villagers' Odin theory."
    )
    result, prompts = expression_sim.run_sequence(
        [expression_sim.expression(live_4795_jules), expression_sim.expression(clean_retry)],
        source,
        expression_rank=3,
    )
    assert len(prompts) == 2, f"cycle 4795 should regenerate Jules, got {len(prompts)} attempts"
    assert result.get("utterance") == clean_retry, result

    # Negative control: reference to one established clause is legal when the
    # reply adds a genuinely new causal route rather than rebuilding its source.
    established = "The north bridge is closed after the storm."
    extension = (
        "The north bridge is closed, so I checked the ferry timetable; the east boat still runs and gives us a dry route before dusk."
    )
    assert quality.same_beat_issue(extension, [turn("mara", established)]) is None, (
        "legitimate source reference was overblocked"
    )

    print("ROOM PER-SOURCE ECHO SIM: GREEN")


if __name__ == "__main__":
    main()
