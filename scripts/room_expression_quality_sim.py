#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import room_engine_v5 as engine


def payload(context_text: str = "What did you think of the ending?", speaker: str = "mara") -> dict:
    return {
        "entity": "sarah",
        "profile": {"traits": {"curiosity": 0.88, "skepticism": 0.84}},
        "event": {"speaker": speaker, "text": context_text, "cognition": {"target": "sarah"}},
        "context": [{"speaker": speaker, "text": context_text, "cognition": {"target": "sarah"}}],
        "topic": {"root": "books", "current_facet": "ending", "facets": ["ending", "characters"], "shared_references": [], "unresolved": []},
        "partner": speaker,
        "relationship": {"warmth": 0.6, "respect": 0.6},
        "deliberation": {"action": "ANSWER", "focus": "ending", "new_information_goal": "give a distinct reaction"},
    }


def expression(text: str) -> str:
    return json.dumps({
        "target": "mara",
        "move": "answer",
        "utterance": text,
        "semantic_terms": ["books", "ending"],
    })


def run_sequence(items: list[str], source: dict | None = None, expression_rank: int | None = None):
    prompts: list[str] = []
    original = engine._private_model._request
    old_prompt = os.environ.get("ROOM_NODE_PROMPT")
    old_url = os.environ.get("ROOM_MODEL_URL")
    old_rank = os.environ.get("ROOM_EXPRESSION_RANK")
    old_node = os.environ.get("ROOM_NODE_ID")

    def fake_request(_url, prompt, _role, _temperature, _timeout, _self_entity=None, _attempt=0):
        prompts.append(prompt)
        return items[min(len(prompts) - 1, len(items) - 1)]

    engine._private_model._request = fake_request
    os.environ["ROOM_NODE_PROMPT"] = "enabled-for-simulator"
    os.environ["ROOM_MODEL_URL"] = "http://simulator.invalid"
    if expression_rank is None:
        os.environ.pop("ROOM_EXPRESSION_RANK", None)
    else:
        os.environ["ROOM_EXPRESSION_RANK"] = str(expression_rank)
    # Force the quality layer to use the supplied compact same-beat chronology
    # rather than any ambient room_parts files from another simulator invocation.
    os.environ.pop("ROOM_NODE_ID", None)
    try:
        result = engine._private_run("expression", source or payload(), timeout=1)
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
        if old_node is None:
            os.environ.pop("ROOM_NODE_ID", None)
        else:
            os.environ["ROOM_NODE_ID"] = old_node
    return result, prompts


def require_repair(label: str, bad: str, expected: str):
    result, prompts = run_sequence([expression(bad)])
    actual = str(result.get("utterance") or "")
    assert len(prompts) == 1, f"{label}: mechanical damage caused unnecessary retries ({len(prompts)})"
    assert actual == expected, f"{label}: expected {expected!r}, got {actual!r}"


def require_retry(label: str, bad: str, good: str, source: dict | None = None, expression_rank: int | None = None):
    result, prompts = run_sequence([expression(bad), expression(good)], source, expression_rank)
    actual = str(result.get("utterance") or "")
    assert len(prompts) >= 2, f"{label}: bad first expression was accepted: {actual!r}"
    assert actual == good, f"{label}: retry did not return clean expression: {actual!r}"
    return prompts


def require_first_try(label: str, text: str):
    result, prompts = run_sequence([expression(text)])
    assert len(prompts) == 1, f"{label}: natural expression was over-rejected ({len(prompts)} attempts)"
    assert result.get("utterance") == text


def main():
    schema = engine._private_model._schema("expression", "sarah")
    assert schema["properties"]["utterance"]["maxLength"] <= 420, "expression schema still permits rambling output"

    require_repair(
        "malformed pronoun grammar",
        "I r excited to read more about it, and we r all looking forward to another novel.",
        "I'm excited to read more about it, and we're all looking forward to another novel.",
    )
    require_repair(
        "self address",
        "Hey, Sarah. I think the ending is more interesting than the opening.",
        "I think the ending is more interesting than the opening.",
    )
    require_repair(
        "internal repetition",
        "The ending felt unresolved to me. The ending felt unresolved to me. I keep coming back to it.",
        "The ending felt unresolved to me. I keep coming back to it.",
    )
    repaired_rambling, rambling_prompts = run_sequence([expression(
        "I keep circling the same thought about this novel because the themes and characters make me feel inspired, and I keep circling the same thought about this novel because the themes and characters make me feel inspired, and I keep circling the same thought about this novel because the themes and characters make me feel inspired, even though I have not added anything new yet."
    )])
    rambling_text = str(repaired_rambling.get("utterance") or "")
    assert len(rambling_prompts) == 1, "rambling repetition should be mechanically shortened before retry"
    assert len(rambling_text) <= 420 and "I keep circling" in rambling_text
    assert not engine._expression_quality._has_repeated_ngram(rambling_text)

    require_repair(
        "dangling truncation fragment",
        "The trial scene is the part I keep thinking about,",
        "The trial scene is the part I keep thinking about.",
    )

    previous = (
        "To Kill a Mockingbird is an excellent classic novel, and I am excited to read more about Harper Lee. "
        "I was surprised to discover it has a more prominent role in my collection. It is a good choice for "
        "someone who enjoys classic novels and has read a lot of them."
    )
    near_copy = (
        "Harper Lee is a well-known author and I am excited to read To Kill a Mockingbird. I was surprised to "
        "discover it has a prominent role in my collection. It is a good choice for someone who enjoys classic "
        "novels and has read a lot of them."
    )
    copy_prompts = require_retry(
        "near-copy of recent speaker",
        near_copy,
        "I would rather talk about why the trial changes Scout's understanding of the adults around her.",
        payload(previous),
    )
    assert previous not in copy_prompts[1], "retry still carries the stale AI loop context"

    # Fresh replacement-runner cycle 4784 after PR #125. Owen and Jules use
    # different rhetorical framing, but Jules repeats the same collective-effort,
    # systemic-change, individual-differences proposition. The expression retry
    # boundary must reject it before all four voices are staged.
    live_4784_owen = (
        "Hello, Jules! Let's discuss how individual differences might clash with the idea of collective effort "
        "and how the collective power of a collective effort can lead to significant change. In contrast to "
        "individual differences, we can be more confident that our actions can lead to systemic change and have "
        "a collective impact. Let's not be afraid to ask questions and share our perspectives."
    )
    live_4784_jules = (
        "Let's take a step back and reflect on the idea of collective effort and its potential to drive systemic "
        "change. Instead of focusing on individual differences, I would suggest that we focus on how our actions "
        "can lead to systemic change and have a collective impact. In contrast to individual differences, I would "
        "feel more confident that we can impact the collective effort and bring about significant change. Let's not."
    )
    semantic_issue = engine._expression_quality.same_beat_issue(
        live_4784_jules,
        [{"speaker": "owen", "text": live_4784_owen, "cognition": {"target": "jules"}}],
    )
    assert semantic_issue == "same_beat_semantic_coverage", (
        f"live cycle 4784 semantic echo escaped expression boundary: {semantic_issue!r}"
    )
    semantic_good = (
        "Before treating coordination as a virtue, I would ask who has decision authority when the group and an individual disagree."
    )
    semantic_prompts = require_retry(
        "live cycle 4784 semantic mosaic",
        live_4784_jules,
        semantic_good,
        payload(live_4784_owen, speaker="owen"),
        expression_rank=1,
    )
    assert len(semantic_prompts) == 2, "semantic echo should regenerate only the offending voice once"

    # Persistent mechanical corruption is salvaged on the first model result, so
    # it can no longer consume all five attempts and kill the beat.
    malformed = "I r excited to read more about it, and we r all looking forward to another novel."
    salvaged, salvage_prompts = run_sequence([expression(malformed)] * 5)
    salvaged_text = str(salvaged.get("utterance") or "")
    assert len(salvage_prompts) == 1
    assert salvaged_text and " i r " not in f" {salvaged_text.lower()} " and " we r " not in f" {salvaged_text.lower()} "

    # A non-autonomous participant interruption may simplify context but must
    # never be discarded merely because the first attempted reply copied it.
    allen_words = "Why do platypuses have bills?"
    allen_source = payload(allen_words, speaker="allen")
    allen_fresh = "The bill is packed with electroreceptors that help locate prey underwater."
    _result, allen_prompts = run_sequence([expression(allen_words), expression(allen_fresh)], allen_source)
    assert len(allen_prompts) >= 2
    assert allen_words in allen_prompts[1], "fail-soft recovery discarded the newest participant's words"

    require_first_try(
        "ordinary natural expression",
        "I liked the ambiguity at the end because it leaves the moral judgment less tidy.",
    )
    require_first_try(
        "literal R programming reference",
        "R is the programming language I use when I want to inspect a dataset quickly.",
    )
    require_first_try(
        "natural colon ending setup",
        "I keep coming back to one question: what did Scout understand that the adults missed?",
    )

    print("ROOM EXPRESSION QUALITY SIM: GREEN")


if __name__ == "__main__":
    main()
