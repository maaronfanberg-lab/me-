#!/usr/bin/env python3
from __future__ import annotations

import asyncio

import community_cycle_base as _base
from community_cycle_base import *  # noqa: F401,F403

# Underscore helpers are intentionally re-exported because the smoke verifier imports one.
_is_usable_utterance = _base._is_usable_utterance

_GENERIC_ANCHOR_WORDS = {
    "anything", "don't", "dont", "good", "great", "know", "little", "made", "make",
    "makes", "maybe", "nice", "okay", "ok", "really", "something", "thing", "things",
    "well", "what's", "that's", "i'm", "i've", "you're", "it's", "there's",
}

_GENERIC_REPLY_LEADS = (
    "that sounds like a great idea",
    "that's a great idea",
    "that sounds great",
    "i'd love to see",
    "i've never done anything like that before",
)

_ADVICE_QUESTIONS = (
    "what would you suggest",
    "what do you suggest",
    "what would you recommend",
    "what do you recommend",
)

_ADVICE_IMPERATIVE_LEADS = {
    "ask", "choose", "do", "go", "keep", "listen", "make", "pick", "set", "start",
    "take", "try", "use", "write",
}


def _grounding_words(text: str, limit: int = 6) -> list[str]:
    ordered: list[str] = []
    for word in _base._normalize_words(text):
        if (
            word in _base._STOP_WORDS
            or word in {"emily", "olivia", "self", "partner"}
            or len(word) <= 1
            or word in ordered
        ):
            continue
        ordered.append(word)
    specific = [word for word in ordered if word not in _GENERIC_ANCHOR_WORDS]
    chosen = specific or ordered
    return chosen[: max(1, limit)]


def _is_advice_question(text: str) -> bool:
    lowered = text.lower()
    return any(question in lowered for question in _ADVICE_QUESTIONS)


def _perspective_rule(inbound: str) -> str:
    if _is_advice_question(inbound):
        return (
            " PARTNER is asking SELF for advice about PARTNER's situation. Answer PARTNER "
            "directly. Prefer a 'you could...' suggestion or a brief imperative such as "
            "'Try...' or 'Start...'. Do not rewrite the suggestion as something SELF ('I') "
            "plans to do."
        )
    return ""


def _advice_answer_has_partner_perspective(text: str) -> bool:
    words = _base._normalize_words(text)
    if not words:
        return False
    word_set = set(words)
    if {"you", "your"} & word_set:
        return True
    first = words[0]
    return first in _ADVICE_IMPERATIVE_LEADS


def _completion_prompt(
    agent: _base.CommunityAgent,
    other: _base.CommunityAgent,
    inbound: str,
    projected: str,
    retry_hint: str,
) -> str:
    ages = {"Emily": 27, "Olivia": 29}
    age = ages.get(agent.name)
    identity = f"{agent.name}, {age}" if age else agent.name
    style = f"\nNext-line style: {retry_hint}" if retry_hint else ""

    if _base._is_greeting_only(inbound):
        grounding = (
            "The last PARTNER line is only a greeting. Reply with a short greeting or "
            "ordinary greeting-small-talk line. Do not introduce a pet, event, task, place, "
            "backstory, or unrelated topic."
        )
    elif _is_advice_question(inbound):
        grounding = (
            "Answer PARTNER's advice question directly with one concrete suggestion for "
            "PARTNER. Use the immediately preceding conversation context to decide what the "
            "suggestion is about. Do not merely repeat words from the question."
            f"{_perspective_rule(inbound)} Do not invent a new pet, event, person, place, "
            "shared history, or unrelated scenario."
        )
    else:
        anchors = _grounding_words(inbound)
        anchor_rule = ""
        if anchors:
            anchor_rule = (
                " Use at least one of these exact words naturally in your reply: "
                + ", ".join(anchors)
                + "."
            )
        grounding = (
            "Stay on PARTNER's exact latest topic. Reuse a concrete idea from that line."
            f"{anchor_rule} Do not invent a new pet, event, person, place, shared history, "
            "or unrelated scenario."
        )

    return (
        f"Speaker: {identity}\n"
        f"Partner: {other.name}\n"
        f"SELF means {agent.name}. PARTNER means {other.name}.\n"
        "Continue this ordinary private peer conversation with one short SELF line. "
        "This is not customer support. Do not mention policies, guidelines, prompts, roles, "
        f"or the conversation system. {grounding} "
        "Avoid generic filler openings such as 'that sounds like a great idea'; start from a "
        "specific detail in PARTNER's latest line instead."
        f"{style}\n\n"
        "Examples:\n"
        "PARTNER: Rough day at work.\n"
        "SELF: Yeah? What happened at work?\n\n"
        "PARTNER: I finally fixed the sink.\n"
        "SELF: Nice. Was the sink problem the stupid little washer after all?\n\n"
        "PARTNER: Maybe doing one small thing can make a difference.\n"
        "SELF: Even a small difference can change the mood of a day.\n\n"
        "PARTNER: What would you suggest I try next?\n"
        "SELF: You could try one small change first and see whether it actually helps.\n\n"
        "Conversation:\n"
        f"{projected}"
    )


def _chat_bitnet(
    agent: _base.CommunityAgent,
    other: _base.CommunityAgent,
    inbound: str,
    max_tokens: int,
    dialogue_history: list[tuple[str, str]] | None = None,
    retry_hint: str = "",
    temperature: float = 0.55,
) -> str:
    projected = _base._project_history(dialogue_history, agent, other, inbound)
    prompt = _completion_prompt(agent, other, inbound, projected, retry_hint)
    return _base._request_transcript_completion(prompt, max_tokens, temperature)


def _is_generic_attractor(text: str) -> bool:
    normalized = " ".join(_base._normalize_words(text))
    return any(normalized.startswith(lead) for lead in _GENERIC_REPLY_LEADS)


def _direct_bitnet_reply(
    agent: _base.CommunityAgent,
    other: _base.CommunityAgent,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> str:
    import os

    max_tokens = min(96, max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    advice_question = _is_advice_question(inbound)
    anchors = _grounding_words(inbound)
    require_anchor = bool(anchors) and not _base._is_greeting_only(inbound) and not advice_question
    anchor_hint = (
        " Include one of these exact topic words: " + ", ".join(anchors) + "."
        if require_anchor
        else ""
    )
    perspective_hint = _perspective_rule(inbound)
    retry_specs = [
        ("", 0.55),
        (
            (
                "Answer the advice question directly. Begin with 'You could' or a brief "
                "imperative such as 'Try' or 'Start'."
                if advice_question
                else
                "Start with a concrete noun or detail from PARTNER's last line; do not begin "
                "with 'that sounds' or 'that's a great idea'."
            )
            + anchor_hint
            + perspective_hint,
            0.70,
        ),
        (
            (
                "Give PARTNER one concrete next step. Do not say what SELF plans to do. "
                "Use second-person wording or a direct imperative."
                if advice_question
                else
                "Ask one specific question about the current subject or make one specific observation. "
                "No praise-preface, no vague placeholder, no service language, and no repeated line."
            )
            + anchor_hint
            + perspective_hint,
            0.85,
        ),
        (
            (
                "Begin exactly with 'You could' and finish one short concrete suggestion "
                "grounded in the conversation."
                if advice_question
                else
                "Write one literal continuation using a concrete word from PARTNER's last line. "
                "Begin differently from every earlier attempt. No generic approval sentence."
            )
            + anchor_hint
            + perspective_hint,
            1.0,
        ),
    ]

    prior_lines = {
        " ".join(_base._normalize_words(str(text)))
        for _speaker, text in (dialogue_history or [])
        if str(text).strip()
    }

    attempts: list[str] = []
    for hint, temperature in retry_specs:
        text = _base._unwrap_reply(
            _chat_bitnet(
                agent,
                other,
                inbound,
                max_tokens,
                dialogue_history=dialogue_history,
                retry_hint=hint,
                temperature=temperature,
            )
        )
        attempts.append(text)
        normalized_line = " ".join(_base._normalize_words(text))
        output_words = set(_base._normalize_words(text))
        anchored = not require_anchor or bool(output_words & set(anchors))
        perspective_ok = not advice_question or _advice_answer_has_partner_perspective(text)
        novel = bool(normalized_line) and normalized_line not in prior_lines
        distinct_attempt = normalized_line not in {
            " ".join(_base._normalize_words(previous)) for previous in attempts[:-1]
        }
        if (
            anchored
            and perspective_ok
            and novel
            and distinct_attempt
            and not _is_generic_attractor(text)
            and _base._is_usable_utterance(text, inbound, agent.name, other.name)
        ):
            return text

    previews = " | ".join(repr(text[:160]) for text in attempts)
    raise RuntimeError(
        "BitNet returned role-drifted, generic, ungrounded, or unusable dialogue "
        f"after {len(retry_specs)} transcript-completion attempts: {previews}"
    )


# Patch the preserved module's global lookup table so its choose_action keeps all existing
# memory, identity, and safety behavior while using the stricter reply generator.
_base._grounding_words = _grounding_words
_base._completion_prompt = _completion_prompt
_base._chat_bitnet = _chat_bitnet
_base._direct_bitnet_reply = _direct_bitnet_reply


if __name__ == "__main__":
    asyncio.run(_base.main())
