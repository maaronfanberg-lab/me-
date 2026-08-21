#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


MARA_QUESTION = (
    "I was wondering about some books of the year and having a few sets of the releases. "
    "Can we explore a range of genres and start with a few books of the year?"
)
OWEN_ECHO = (
    "I heard that you were wondering about some books of the year and having a few sets of the releases. "
    "Can we explore a range of genres and start with a few books of the year?"
)
GENRE_ANSWER = (
    "Mystery, science fiction, and historical fiction would give us three very different places to start."
)
VACUOUS = "Let's give some genres to start with."
OLD_THREAD = "I agree that there are a lot of books of the year to explore. Let's start with a few of your closest friends."
OLD_CONTEXT = "We could use a few of your closest friends to look through the books of the year."
JULES_BID = "Let's give some genres to start with."


def expression(text: str, target: str = "mara") -> str:
    return json.dumps({
        "target": target,
        "move": "answer",
        "utterance": text,
        "semantic_terms": [],
    })


def payload(event_text: str, *, speaker: str = "mara", older: list[dict] | None = None) -> dict:
    event = {"speaker": speaker, "text": event_text, "cognition": {"target": "sarah"}}
    context = [*(older or []), event]
    return {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": event,
        "context": context,
        "topic": {"root": "books", "current_facet": "genres", "facets": ["genres", "books"]},
        "partner": speaker,
        "relationship": {"warmth": 0.5, "respect": 0.5},
        "deliberation": {"action": "ANSWER", "focus": "genres"},
    }


def run_sequence(items: list[str], source: dict, rank: int = 1):
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
    os.environ["ROOM_EXPRESSION_RANK"] = str(rank)
    try:
        result = engine._private_run("expression", source, timeout=1)
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


def check_retry_keeps_previous_speaker_visible() -> None:
    result, prompts = run_sequence(
        [expression(OWEN_ECHO), expression(GENRE_ANSWER)],
        payload(MARA_QUESTION),
        rank=1,
    )
    assert result.get("utterance") == GENRE_ANSWER, "clean second response did not survive retry"
    assert len(prompts) >= 2, "live question echo was accepted without retry"
    assert MARA_QUESTION in prompts[0], "first generation did not see Mara's actual question"
    assert MARA_QUESTION in prompts[1], (
        "semantic retry discarded the immediately previous AI turn instead of staying in the conversation"
    )


def check_echo_stays_rejected_across_retries() -> None:
    result, prompts = run_sequence(
        [expression(OWEN_ECHO), expression(OWEN_ECHO), expression(GENRE_ANSWER)],
        payload(MARA_QUESTION),
        rank=1,
    )
    assert len(prompts) >= 3, "the same echo became acceptable after validation context was mutated"
    assert result.get("utterance") == GENRE_ANSWER, "persistent echo escaped the quality boundary"


def check_question_needs_a_contribution() -> None:
    result, prompts = run_sequence(
        [expression(VACUOUS), expression(GENRE_ANSWER)],
        payload(MARA_QUESTION),
        rank=1,
    )
    assert len(prompts) >= 2, "question was answered only with a restated intention, not a contribution"
    assert result.get("utterance") == GENRE_ANSWER


def check_latest_turn_beats_stale_thread() -> None:
    older = [{"speaker": "owen", "text": OLD_CONTEXT, "cognition": {"target": "jules"}}]
    result, prompts = run_sequence(
        [expression(OLD_THREAD, "jules"), expression(GENRE_ANSWER, "jules")],
        payload(JULES_BID, speaker="jules", older=older),
        rank=2,
    )
    assert len(prompts) >= 2, "reply fell back to an older thread while ignoring Jules's newest genre bid"
    assert result.get("utterance") == GENRE_ANSWER


def check_personality_can_still_make_a_tangent() -> None:
    source = payload(
        "That meeting felt endless.",
        speaker="owen",
        older=[{"speaker": "mara", "text": "The projector kept failing.", "cognition": {"target": "owen"}}],
    )
    playful = "At least the coffee achieved immortality before the meeting did."
    result, prompts = run_sequence([expression(playful, "owen")], source, rank=1)
    assert len(prompts) == 1, "ordinary personality-shaped association was over-constrained"
    assert result.get("utterance") == playful


def main() -> None:
    check_retry_keeps_previous_speaker_visible()
    check_echo_stays_rejected_across_retries()
    check_question_needs_a_contribution()
    check_latest_turn_beats_stale_thread()
    check_personality_can_still_make_a_tangent()
    print("ROOM SEMANTIC UPTAKE SIM: GREEN")


if __name__ == "__main__":
    main()
