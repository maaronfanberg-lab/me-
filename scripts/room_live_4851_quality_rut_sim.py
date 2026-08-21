#!/usr/bin/env python3
from __future__ import annotations

import room_expression_quality as quality
import room_topic_bounded as bounded


def turn(speaker: str, text: str) -> dict:
    return {"speaker": speaker, "text": text, "cognition": {"target": "allen"}}


def no_similarity(_left: object, _right: object) -> float:
    return 0.0


def expression_issue(text: str) -> str | None:
    return quality.quality_issue(text, {"context": []}, "mara", no_similarity)


def main() -> None:
    # Live cycle 4851: the model copied expression-instruction prose into public
    # speech, then Sarah emitted a pure orchestration placeholder. Neither is a
    # conversational contribution and both must be retried before publication.
    live_4851_mara = (
        "Speak a natural, nuanced, supportive, and relevant line to continue the conversation. "
        "Let's work together to structure the project's goals and objectives. I want a plan to "
        "create a structured approach that aligns with the project's goals and objectives. We "
        "should also include specific timelines and milestones to track progress and set goals. "
        "Let's explore potential risks and mitigation methods as a team."
    )
    live_4851_sarah = "Responding to the new speaker"
    assert expression_issue(live_4851_mara) == "instruction_residue", (
        "cycle 4851 prompt residue escaped expression boundary"
    )
    assert expression_issue(live_4851_sarah) == "meta_placeholder", (
        "cycle 4851 placeholder escaped expression boundary"
    )

    # Negative control: participants may genuinely discuss an instruction. The
    # detector is about model/orchestration-shaped output, not forbidden words.
    quoted_instruction = (
        "You asked me to 'speak naturally' yesterday; I think that instruction made the interview "
        "feel more awkward, so I'd rather begin with one concrete question."
    )
    assert expression_issue(quoted_instruction) is None, "ordinary quoted discussion was overblocked"

    # Live cycle 4852: Owen establishes a generic project-goal frame. Jules then
    # repeats the goal/team frame instead of adding substance; Mara later returns
    # to goals/team/process after Sarah has supplied a genuinely distinct angle.
    live_4852_owen = (
        "As a team, we need to align our project's goals and objectives. The structure of the "
        "project's goals and objectives should be clear and unified, ensuring that we have a shared "
        "goal to work toward. Let's ensure that all team members are on the same page and have a "
        "clear understanding of what the project aims to achieve. It's important to review and "
        "discuss these goals regularly to ensure that the project is on track."
    )
    live_4852_jules = (
        "Hey Owen, let's start by figure out what the most important goals of the project are. "
        "Let's go through those and figure out what's on the table first, as a team, in this project. "
        "I'd like to ask you to do the same with me. I'm just going to have to start thinking about "
        "that for a second, then we'll move forward. Let's go through them and figure it out in the "
        "best way we can, in the most effective way for this project."
    )
    live_4852_sarah = (
        "I've got my own process for gathering ideas for this project. I've been working on a "
        "data-driven approach with a team of engineers to ensure that we're on the right track in "
        "terms of our project objectives. We've identified several key areas that need attention, "
        "and I've been using these as a basis for decision-making. I've also been encouraging our "
        "team to brainstorm ideas and come up with potential solutions."
    )
    live_4852_mara = (
        "Now that we have the most important goals of the project in mind, I would like to help you "
        "figure out how you're going to get them all. I'd like to take a look at your team's current "
        "situation, as a group, to see how you're going to move forward. How are you going to go "
        "about the project? How are you going to prioritize it? How are you going to break it down? "
        "How are you going to figure out how to execute the project?"
    )
    assert quality.same_beat_issue(live_4852_jules, [turn("owen", live_4852_owen)]) == "same_beat_project_process_echo", (
        "cycle 4852 Jules escaped project-process chorus boundary"
    )
    assert quality.same_beat_issue(
        live_4852_mara,
        [turn("owen", live_4852_owen), turn("jules", live_4852_jules), turn("sarah", live_4852_sarah)],
    ) == "same_beat_project_process_echo", "cycle 4852 Mara escaped project-process chorus boundary"

    # A real project continuation stays legal when it contributes measurable new
    # evidence and an actionable experiment instead of merely rotating process words.
    concrete_extension = (
        "For that goal, the smart-meter log shows HVAC used sixty-two percent of yesterday's power; "
        "I'll test a two-degree setback tonight and compare the morning load."
    )
    assert quality.same_beat_issue(concrete_extension, [turn("owen", live_4852_owen)]) is None, (
        "concrete project evidence was overblocked"
    )

    # Live cycle 4860 confirms the same family after the topic drifted from goals to
    # data/strategy/focus. The later voices still repackage process rather than add
    # facts about carbon emissions.
    live_4860_jules = "Sure, I know I'm not the first time using that phrase. It's the kind of phrase we need to use more often."
    live_4860_sarah = "We're working on a way to reduce carbon emissions. Let's focus on the new data and strategy. Can you hear us?"
    live_4860_mara = (
        "Okay, you're the voice. Let's start with some data. Let's talk about the carbon footprint. "
        "Is there anything we should focus on first? Let's think about the next step, then? Let's see "
        "if we can agree on what we're trying to achieve. Is it possible to agree that we need to "
        "make a plan? Let's start with a team meeting. If we need more help, we could try a survey or "
        "a meeting with experts."
    )
    live_4860_owen = (
        "I noticed something interesting about the data that we just sent in. Let's see if it helps "
        "us in some way. Is there a particular issue or a particular problem that we should focus on "
        "now? Or maybe we can try to find some other ways to get a little bit more data on the topic."
    )
    assert quality.same_beat_issue(
        live_4860_mara,
        [turn("jules", live_4860_jules), turn("sarah", live_4860_sarah)],
    ) == "same_beat_project_process_echo", "cycle 4860 Mara escaped project-process chorus boundary"
    assert quality.same_beat_issue(
        live_4860_owen,
        [turn("jules", live_4860_jules), turn("sarah", live_4860_sarah), turn("mara", live_4860_mara)],
    ) == "same_beat_project_process_echo", "cycle 4860 Owen escaped project-process chorus boundary"

    # The current live episode reached 91 updates because any superficial new term
    # resets low_novelty_beats. Age must independently force a true topic bridge.
    limit = getattr(bounded, "MAX_EPISODE_UPDATES", None)
    assert isinstance(limit, int) and limit >= 8, "bounded topic has no hard episode-age limit"
    stale = bounded.new_topic_from_terms(["project", "goals", "strategy"], 4815)
    stale["turns"] = limit - 1
    stale["recent_terms"] = ["project", "goals", "strategy"]
    message = {
        "speaker": "sarah",
        "text": "We could add one more dashboard metric.",
        "cognition": {
            "topic_episode": stale["id"],
            "topic_terms": ["dashboard", "metric"],
        },
    }
    aged = bounded.update_topic(stale, [message], 4861)
    assert bounded.should_shift_topic(aged), "episode age did not force a topic bridge"
    assert aged.get("bridge_reason") == "episode_age", aged

    fresh = bounded.new_topic_from_terms(["garden", "soil", "rain"], 4861)
    fresh["turns"] = max(0, limit - 3)
    fresh_message = {
        "speaker": "mara",
        "text": "The north bed stayed damp after last night's rain.",
        "cognition": {
            "topic_episode": fresh["id"],
            "topic_terms": ["north bed", "damp", "rain"],
        },
    }
    still_fresh = bounded.update_topic(fresh, [fresh_message], 4862)
    assert still_fresh.get("bridge_reason") != "episode_age", "fresh episode shifted too early"

    print("ROOM LIVE 4851 QUALITY/RUT SIM: GREEN")


if __name__ == "__main__":
    main()
