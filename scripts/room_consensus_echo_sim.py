#!/usr/bin/env python3
from __future__ import annotations

import room_expression_quality as quality
import room_expression_quality_sim as expression_sim


def turn(speaker: str, text: str) -> dict:
    return {"speaker": speaker, "text": text, "cognition": {"target": "allen"}}


def require_issue(label: str, expected: str, text: str, prior: list[dict]) -> None:
    issue = quality.same_beat_issue(text, prior)
    assert issue == expected, f"{label} escaped {expected}: {issue!r}"


def main() -> None:
    # Exact first true post-PR127 runner beat. The fourth voice did not copy one
    # contiguous phrase; it assembled a consensus mosaic from the three earlier
    # Room voices: characters/story plus list/potential/team.
    live_4791_mara = (
        "Allen, Here's the starting point. Let's dive into the idea of a project that can be customized to reflect our storytelling goals. "
        "What kind of characters do you like to see in the project, and how can we incorporate that into the story you want to tell?"
    )
    live_4791_owen = (
        "I can see why you might be interested in this idea. It's about a project where someone funds a remote village in Sweden where the village still live an iron or Bronze Age live style. "
        "In our next discussion, we'll explore how we can use the various characters to make the story more engaging and authentic. Is that something you think we could do?"
    )
    live_4791_jules = (
        "So we decided we need to start with a list of potential characters, right? what are some of the characteristics of a good team? what would we do to make our team work well?"
    )
    live_4791_sarah = (
        "I can't wait to see how this gets realized. Let's create a list of potential characters to start with. How do you think we can use them to help us tell our story better? "
        "That's a great start! Let's also explore how teams can be involved. Teams could help us tell our story by bringing in more people with their own unique backgrounds and perspectives. "
        "That's a great approach! We can also talk about a plot where someone"
    )
    prior_4791 = [
        turn("mara", live_4791_mara),
        turn("owen", live_4791_owen),
        turn("jules", live_4791_jules),
    ]
    require_issue("live cycle 4791 Sarah", "same_beat_consensus_echo", live_4791_sarah, prior_4791)

    # The same gap remained visible one beat later: Mara rebuilt the characters /
    # story / team / potential consensus already established by Owen, Jules, Sarah.
    live_4792_owen = (
        "Allen, I understand that we can use the potential characters to make the story more engaging and authentic. Would it be possible to include a team or a plot that incorporates them?"
    )
    live_4792_jules = (
        "You’ve got me talking, Mara. We have a great opportunity to start with a list of potential characters for our project. Let’s pick our team and how we can connect their unique background to help make the story more engaging. "
        "The project idea is really inspiring and has a lot of potential. That’s exciting, right? So let's get started on the characters and maybe create a team for our project. What do you think? Let’s do"
    )
    live_4792_sarah = (
        "Alright, let's start by defining what kind of project we're making and how we want to tell our story. What kind of characters do you think we should include in the story, and how would we incorporate them into the story?"
    )
    live_4792_mara = (
        "I believe we can start by researching potential teams that have a proven track record and can connect us to a remote village in Sweden. These teams can help us tell our story in a different perspective, "
        "giving our characters and the setting a unique voice. How does this approach sound to you?"
    )
    prior_4792 = [
        turn("owen", live_4792_owen),
        turn("jules", live_4792_jules),
        turn("sarah", live_4792_sarah),
    ]
    require_issue("live cycle 4792 Mara", "same_beat_consensus_echo", live_4792_mara, prior_4792)

    # Exact first post-PR129 beat. Owen rebuilt Mara's research -> planning ->
    # testing proposition in two separated phrase clusters. This is only the
    # second autonomous voice, so a multi-speaker consensus detector cannot see it.
    live_4793_mara = (
        "Allen, I apologize for the misunderstanding. I think it would be more efficient to start with the research and planning phase. "
        "Let's ensure all the research is done first, and then we'll move on to the planning and testing phases."
    )
    live_4793_owen = (
        "I understand the importance of starting with the research and planning phase, but we also need to ensure we cover all the research points. "
        "We can't forget to mention the testing phase as well, so I'll add it to the list. Let’s start with the research and testing phases. Good point!"
    )
    prior_4793 = [turn("mara", live_4793_mara)]
    require_issue("live cycle 4793 Owen", "same_beat_phrase_echo", live_4793_owen, prior_4793)

    # Prove the shared predicate regenerates the offending second voice rather
    # than relying on the final publication backstop.
    source_4793 = expression_sim.payload(live_4793_mara, speaker="mara")
    source_4793["context"] = [dict(item) for item in prior_4793]
    source_4793["event"] = dict(prior_4793[-1])
    clean_4793_retry = (
        "If the story should begin immediately, I would open on the one-eyed hunter returning from the forest with his raven while the villagers argue over whether he is Odin."
    )
    result_4793, prompts_4793 = expression_sim.run_sequence(
        [expression_sim.expression(live_4793_owen), expression_sim.expression(clean_4793_retry)],
        source_4793,
        expression_rank=1,
    )
    assert len(prompts_4793) == 2, f"cycle 4793 should regenerate Owen, got {len(prompts_4793)} attempts"
    assert result_4793.get("utterance") == clean_4793_retry, result_4793

    # Prove the shared consensus predicate also regenerates a later offending voice.
    source = expression_sim.payload(live_4791_jules, speaker="jules")
    source["context"] = [dict(item) for item in prior_4791]
    source["event"] = dict(prior_4791[-1])
    clean_retry = (
        "The unusual constraint is consent: I would decide whether residents can leave, invite visitors, and change the experiment before choosing any characters."
    )
    result, prompts = expression_sim.run_sequence(
        [expression_sim.expression(live_4791_sarah), expression_sim.expression(clean_retry)],
        source,
        expression_rank=3,
    )
    assert len(prompts) == 2, f"cycle 4791 should regenerate one offending voice, got {len(prompts)} attempts"
    assert result.get("utterance") == clean_retry, result

    # Negative control: one quoted/established clause followed by genuinely new
    # evidence and a new route is ordinary continuation, not a phrase mosaic.
    extension_prior = "The north bridge is closed because the river rose after the storm."
    legitimate_extension = (
        "The north bridge is closed because the river rose after the storm. I checked the transit map, and the east ferry is still operating, "
        "so I would reroute everyone through the market square and cross there before dusk."
    )
    assert quality.same_beat_issue(
        legitimate_extension,
        [turn("mara", extension_prior)],
    ) is None, "single-clause legitimate extension was overblocked"

    # Combining two distinct established facts into a genuinely new causal/route
    # proposal is synthesis, not a consensus echo.
    fact_a = "The creek rose overnight after heavy rain."
    fact_b = "The north footbridge is closed until inspectors arrive."
    synthesis = (
        "The creek rose overnight, and the north footbridge is closed; I’ll map a dry detour through the library courtyard because both facts change the safest route."
    )
    assert quality.same_beat_issue(
        synthesis,
        [turn("mara", fact_a), turn("owen", fact_b)],
    ) is None, "legitimate two-source synthesis was overblocked"

    fresh = (
        "Before choosing a setting, I would ask whether the villagers are volunteers or descendants, because that changes the ethics of the premise."
    )
    assert quality.same_beat_issue(fresh, prior_4791) is None, "genuinely new idea was overblocked"

    print("ROOM CONSENSUS ECHO SIM: GREEN")


if __name__ == "__main__":
    main()
