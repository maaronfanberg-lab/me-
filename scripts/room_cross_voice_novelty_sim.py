#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def expression(text: str) -> str:
    return json.dumps({
        "target": "mara",
        "move": "answer",
        "utterance": text,
        "semantic_terms": ["themes", "care"],
    })


def source(messages: list[tuple[str, str]], *, same_beat: bool = True) -> dict:
    context = [
        {"speaker": speaker, "text": text, "cognition": {"target": "sarah"}}
        for speaker, text in messages
    ]
    event = context[-1]
    return {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": event,
        "context": context,
        # Simulator-only marker used to select the same production rank semantics.
        # It is not part of the model input allowlist.
        "same_beat_prior_turns": context if same_beat else [],
        "topic": {
            "root": "themes",
            "current_facet": "care",
            "facets": ["care", "others", "important", "hard"],
            "shared_references": ["themes"],
            "unresolved": [],
        },
        "partner": str(event.get("speaker") or "mara"),
        "relationship": {"warmth": 0.6, "respect": 0.6},
        "deliberation": {"action": "ANSWER", "focus": "care"},
    }


def run(items: list[str], payload: dict):
    prompts: list[str] = []
    original = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, _attempt=0):
        prompts.append(prompt)
        return items[min(len(prompts) - 1, len(items) - 1)]

    engine._private_model._request = fake_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    os.environ["ROOM_EXPRESSION_RANK"] = str(min(3, len(payload.get("same_beat_prior_turns") or [])))
    try:
        result = engine._private_run("expression", payload, timeout=1)
    finally:
        engine._private_model._request = original
        if old_prompt is None:
            os.environ.pop("ROOM_NODE_PROMPT", None)
        else:
            os.environ["ROOM_NODE_PROMPT"] = old_prompt
        if old_url is None:
            os.environ.pop("ROOM_MODEL_URL", None)
        else:
            os.environ["ROOM_MODEL_URL"] = old_url
        if old_rank is None:
            os.environ.pop("ROOM_EXPRESSION_RANK", None)
        else:
            os.environ["ROOM_EXPRESSION_RANK"] = old_rank
    return result, prompts


def require_retry(label: str, bad: str, good: str, payload: dict):
    result, prompts = run([expression(bad), expression(good)], payload)
    assert len(prompts) >= 2, f"{label}: semantically repetitive first reply was accepted"
    assert str(result.get("utterance") or "") == good, f"{label}: retry did not produce the fresh reply"


def main():
    mara = (
        "I feel so bad, and it is so hard to express how it has been for me to care for others. "
        "I realize it is so important to me and so I should care about them, but it feels so much harder to talk about. "
        "What do you think?"
    )
    owen_echo = (
        "I understand how challenging it can be to care for others and care for them. "
        "It is so important to me and so I should care about them, but it feels so much harder to talk about. "
        "I am trying to figure out if I could explain better or if it is just a fact that I need to focus on. What do you think?"
    )
    require_retry(
        "substantial copied sentence in one beat",
        owen_echo,
        "One distinction matters to me: caring is not the same as agreeing, and boundaries can make care more sustainable.",
        source([("mara", mara)]),
    )

    # Reproduce the short paraphrase loop seen live: one speaker says the flow is
    # important to the group and the next speaker merely says the same thing with
    # tiny wording changes. Short echoes need protection too; they should not be
    # exempt merely because they contain fewer than eight distinct words.
    flow = "The flow is important to us as a group."
    flow_echo = "The flow is important for the group too."
    require_retry(
        "short live paraphrase echo",
        flow_echo,
        "What matters to me is who actually changes the direction of the conversation when the group gets stuck.",
        source([("mara", flow)]),
    )

    # Live verification after the first anti-echo restart (cycle 4623) exposed a
    # broader failure: longer paraphrases can keep the same proposition while
    # adding enough filler/modifiers to evade both exact-copy and short-echo rules.
    live_mara = (
        "I can see that incorporating the new feature in the game can be a strong option, "
        "but I also believe it will be beneficial in the long run."
    )
    live_owen_echo = (
        "The new feature, if implemented, could be a strong option. While we can see that incorporating it can be a strong option, "
        "it may not always be as effective or beneficial as incorporating it in a game like the one we've been discussing."
    )
    require_retry(
        "live rank-1 proposition paraphrase",
        live_owen_echo,
        "Before deciding, I'd want to know what problem the feature solves and what result would show that it improves play.",
        source([("mara", live_mara)]),
    )

    live_jules_echo = (
        "In the discussion we had about the new feature, it becomes clear that incorporating it can be a strong option. "
        "The game we were discussing was the one we've been on, and it is something we could have enjoyed. "
        "Now we see that the new feature can be a strong option. As we all discussed earlier, it could potentially be a great tool, "
        "but it may not be as effective or beneficial in the same way as the game we've been on."
    )
    require_retry(
        "live later-voice proposition paraphrase",
        live_jules_echo,
        "I'd test the feature in one limited round first; if players ignore it or it slows decisions, that would argue against keeping it.",
        source([("mara", live_mara), ("owen", live_owen_echo)]),
    )

    prior = [
        ("mara", mara),
        ("owen", "I think care gets harder when we confuse helping with taking responsibility for every outcome."),
        ("jules", "A small project could make this concrete: choose one person and one useful act instead of talking about care in the abstract."),
    ]
    sarah_low_novelty = (
        "I know how important it is to care about others. One of the ways I care about others is by showing care to others. "
        "I am trying to figure out how to do that and I am doing it the hard way because I need to."
    )
    require_retry(
        "low substantive novelty after three same-beat voices",
        sarah_low_novelty,
        "I would separate intention from evidence: what action actually helped, and what sign would show that it did?",
        source(prior),
    )

    fresh = "A boundary can be an act of care when it prevents resentment and makes the help sustainable."
    accepted, prompts = run([expression(fresh)], source(prior))
    assert len(prompts) == 1, "specific same-topic contribution was over-rejected"
    assert accepted.get("utterance") == fresh

    # Similarity to older conversation is continuity, not a same-beat echo.
    historical = source([("mara", mara)], same_beat=False)
    accepted, prompts = run([expression(owen_echo)], historical)
    assert len(prompts) == 1, "historical topic continuity was incorrectly treated as same-beat copying"
    assert accepted.get("utterance") == owen_echo

    participant_words = "Why do platypuses have bills?"
    participant_source = source([("allen", participant_words)], same_beat=False)
    participant_reply = "The bill contains electroreceptors that help a platypus locate prey underwater."
    accepted, prompts = run([expression(participant_reply)], participant_source)
    assert len(prompts) == 1, "grounded participant reply was over-rejected"
    assert participant_words in prompts[0], "participant words disappeared from the generation context"
    assert "same_beat_prior_turns" not in prompts[0], "internal same-beat quality metadata crossed into model cognition"

    print("ROOM CROSS-VOICE NOVELTY SIM: GREEN")


if __name__ == "__main__":
    main()
