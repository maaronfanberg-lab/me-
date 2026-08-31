#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from difflib import SequenceMatcher

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
    "i don't know what to say",
    "i dont know what to say",
    "i'm glad it's going well now",
    "im glad its going well now",
)

_ADVICE_QUESTIONS = (
    "what would you suggest",
    "what do you suggest",
    "what would you recommend",
    "what do you recommend",
)


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


def _perspective_rule(inbound: str) -> str:
    lowered = inbound.lower()
    if any(question in lowered for question in _ADVICE_QUESTIONS):
        return (
            " PARTNER is asking SELF for advice about PARTNER's situation. Answer PARTNER "
            "directly. Prefer a 'you could...' suggestion or a question about PARTNER. Do not "
            "rewrite the suggestion as something SELF ('I') plans to do."
        )
    return ""


def _is_open_question(inbound: str) -> bool:
    lowered = " ".join(inbound.lower().split())
    return lowered.startswith(("what ", "what's ", "whats ", "why ", "how ", "where ", "when ", "which ", "who "))


def _has_new_content(reply: str, inbound: str) -> bool:
    inbound_words = {
        word for word in _base._normalize_words(inbound)
        if word not in _base._STOP_WORDS and word not in _GENERIC_ANCHOR_WORDS and len(word) > 2
    }
    reply_words = {
        word for word in _base._normalize_words(reply)
        if word not in _base._STOP_WORDS and word not in _GENERIC_ANCHOR_WORDS and len(word) > 2
    }
    return bool(reply_words - inbound_words)


def _content_signature(text: str) -> set[str]:
    return {
        word for word in _base._normalize_words(text)
        if word not in _base._STOP_WORDS and word not in _GENERIC_ANCHOR_WORDS and len(word) > 2
    }


def _too_similar_to_own_history(
    reply: str,
    agent_name: str,
    dialogue_history: list[tuple[str, str]] | None,
) -> bool:
    """Reject near-paraphrases of the speaker's own recent lines, not merely exact duplicates."""
    normalized = " ".join(_base._normalize_words(reply))
    signature = _content_signature(reply)
    if not normalized:
        return True

    own_lines = [
        str(text) for speaker, text in (dialogue_history or []) if speaker == agent_name
    ][-4:]
    for previous in own_lines:
        previous_normalized = " ".join(_base._normalize_words(previous))
        if not previous_normalized:
            continue
        if SequenceMatcher(None, normalized, previous_normalized).ratio() >= 0.72:
            return True
        previous_signature = _content_signature(previous)
        if len(signature) >= 3 and len(previous_signature) >= 3:
            union = signature | previous_signature
            if union and len(signature & previous_signature) / len(union) >= 0.60:
                return True
    return False


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
    style = (
        "\nFor this attempt, follow this conversational move exactly: " + retry_hint
        if retry_hint
        else ""
    )

    if _base._is_greeting_only(inbound):
        grounding = (
            "The last PARTNER line is only a greeting. Reply with a short greeting or "
            "ordinary greeting-small-talk line. Do not introduce a pet, event, task, place, "
            "backstory, or unrelated topic."
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
        question_rule = ""
        if _is_open_question(inbound):
            question_rule = (
                " PARTNER asked an open question. Give an actual answer with at least one new, "
                "specific detail that was not already in PARTNER's wording. Do not merely restate "
                "or rephrase the question."
            )
        grounding = (
            "Stay on PARTNER's exact latest topic. Reuse a concrete idea from that line."
            f"{anchor_rule}{_perspective_rule(inbound)}{question_rule} Do not invent a new pet, "
            "event, person, place, shared history, or unrelated scenario."
        )

    return (
        f"Speaker: {identity}\n"
        f"Partner: {other.name}\n"
        f"SELF means {agent.name}. PARTNER means {other.name}.\n"
        "Continue this ordinary private peer conversation with one short SELF line. "
        "This is not customer support. Do not mention policies, guidelines, prompts, roles, "
        f"or the conversation system. {grounding} "
        "Avoid generic filler openings such as 'that sounds like a great idea', 'I don't know "
        "what to say', or 'I'm glad it's going well now'. Start from a specific detail in "
        "PARTNER's latest line instead. Do not paraphrase or recycle any earlier SELF line; "
        "move the conversation forward with a genuinely new detail, reaction, answer, or question."
        f"{style}\n\n"
        "Examples:\n"
        "PARTNER: Rough day at work.\n"
        "SELF: Yeah? What happened at work?\n\n"
        "PARTNER: I finally fixed the sink.\n"
        "SELF: Was it the washer under the faucet after all?\n\n"
        "PARTNER: What's one tiny thing that makes mornings better?\n"
        "SELF: Coffee before anyone starts talking to me.\n\n"
        "PARTNER: The rain smells amazing today.\n"
        "SELF: It does. The pavement almost smells earthy after the first few drops.\n\n"
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


def _retry_specs(
    inbound: str,
    anchor_hint: str,
    perspective_hint: str,
) -> list[tuple[str, float]]:
    common = anchor_hint + perspective_hint
    if _is_open_question(inbound):
        moves = [
            "Answer PARTNER's question directly in the first clause. Give one concrete answer, not a question back.",
            "Give a different direct answer using one specific everyday detail. Do not hedge or praise PARTNER's question.",
            "Answer with a brief personal preference or example that SELF could plausibly say right now, without inventing shared history.",
            "Offer a contrasting or slightly unexpected answer while staying on the exact topic.",
            "Give one practical, specific answer and one short reason for it.",
            "Answer in under 14 words with one concrete noun from PARTNER's topic and one genuinely new detail.",
        ]
    else:
        moves = [
            "React directly to PARTNER's last line with a concrete observation or feeling. Do not ask a question.",
            "Ask one specific follow-up question about a concrete detail in PARTNER's last line. Do not praise or summarize first.",
            "Add one brief personal reaction or example from SELF that connects to PARTNER's exact topic, without inventing shared history.",
            "Offer a mild contrast, disagreement, or alternative interpretation of PARTNER's point while staying friendly.",
            "Continue the topic by naming one likely consequence, next step, or concrete detail PARTNER has not already said.",
            "Write a concise continuation under 14 words that uses a concrete topic word and advances the exchange.",
        ]
    temperatures = [0.55, 0.65, 0.72, 0.80, 0.88, 0.95]
    return [(move + common, temp) for move, temp in zip(moves, temperatures)]


def _direct_bitnet_reply(
    agent: _base.CommunityAgent,
    other: _base.CommunityAgent,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> str:
    import os

    max_tokens = min(96, max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    anchors = _grounding_words(inbound)
    require_anchor = bool(anchors) and not _base._is_greeting_only(inbound)
    require_new_content = _is_open_question(inbound)
    anchor_hint = (
        " Include one of these exact topic words: " + ", ".join(anchors) + "."
        if require_anchor
        else ""
    )
    perspective_hint = _perspective_rule(inbound)
    retry_specs = _retry_specs(inbound, anchor_hint, perspective_hint)

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
        novel = bool(normalized_line) and normalized_line not in prior_lines
        distinct_attempt = normalized_line not in {
            " ".join(_base._normalize_words(previous)) for previous in attempts[:-1]
        }
        substantive = not require_new_content or _has_new_content(text, inbound)
        non_recycled = not _too_similar_to_own_history(text, agent.name, dialogue_history)
        if (
            anchored
            and novel
            and distinct_attempt
            and substantive
            and non_recycled
            and not _is_generic_attractor(text)
            and _base._is_usable_utterance(text, inbound, agent.name, other.name)
        ):
            return text

    previews = " | ".join(repr(text[:160]) for text in attempts)
    raise RuntimeError(
        "BitNet returned role-drifted, generic, paraphrased, recycled, ungrounded, or unusable "
        f"dialogue after {len(retry_specs)} move-diverse transcript-completion attempts: {previews}"
    )


# Patch the preserved module's global lookup table so its choose_action keeps all existing
# memory, identity, and safety behavior while using the stricter reply generator.
_base._grounding_words = _grounding_words
_base._completion_prompt = _completion_prompt
_base._chat_bitnet = _chat_bitnet
_base._direct_bitnet_reply = _direct_bitnet_reply


if __name__ == "__main__":
    asyncio.run(_base.main())
