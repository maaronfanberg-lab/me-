#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from pathlib import Path

import community_cycle_base as _base
from community_cycle_base import *  # noqa: F401,F403

# Underscore helpers are intentionally re-exported because the smoke and production
# verifiers import them.
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

_DETAIL_IGNORE = _GENERIC_ANCHOR_WORDS | {
    "better", "change", "could", "day", "difference", "found", "guess", "idea", "ordinary", "pace",
    "small", "think", "way", "would",
}

_RUT_IGNORE = _GENERIC_ANCHOR_WORDS | {
    "about", "after", "again", "before", "better", "both", "could", "day", "difference",
    "each", "emily", "found", "further", "guess", "idea", "much", "olivia", "ordinary",
    "pace", "small", "sure", "think", "though", "way", "would", "yeah",
}

_WORD_RE = re.compile(r"[a-z']+")


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


def _is_direct_information_question(text: str) -> bool:
    lowered = " ".join(text.lower().strip().split())
    if "?" not in text:
        return False
    return bool(
        re.search(r"\b(what|what's|which|where|when|who|how)\b", lowered)
        or "something" in lowered
    )


def _content_terms(text: str, *, detail: bool = False) -> set[str]:
    ignored = _DETAIL_IGNORE if detail else _RUT_IGNORE
    return {
        word
        for word in _WORD_RE.findall(text.lower())
        if len(word) >= 3
        and word not in _base._STOP_WORDS
        and word not in ignored
        and word not in {"emily", "olivia", "self", "partner"}
    }


def _answer_adds_new_detail(reply: str, inbound: str) -> bool:
    if not _is_direct_information_question(inbound) or _is_advice_question(inbound):
        return True
    reply_terms = _content_terms(reply, detail=True)
    inbound_terms = _content_terms(inbound, detail=True)
    new_terms = reply_terms - inbound_terms
    if not new_terms:
        return False
    # A terse concrete answer such as "Fresh air." can legitimately add one new idea. A
    # full sentence that merely paraphrases the question needs at least two new details.
    if len(_base._normalize_words(reply)) <= 4:
        return True
    return len(new_terms) >= 2


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
    return words[0] in _ADVICE_IMPERATIVE_LEADS


def _history_texts(dialogue_history: list[tuple[str, str]] | None) -> list[str]:
    return [str(text).strip() for _speaker, text in (dialogue_history or []) if str(text).strip()]


def _overused_recent_terms(dialogue_history: list[tuple[str, str]] | None) -> set[str]:
    recent = _history_texts(dialogue_history)[-5:]
    if len(recent) < 3:
        return set()
    counts = Counter(term for text in recent for term in _content_terms(text))
    return {term for term, count in counts.items() if count >= 3}


def _would_extend_lexical_rut(
    text: str,
    dialogue_history: list[tuple[str, str]] | None,
) -> bool:
    overused = _overused_recent_terms(dialogue_history)
    return bool(overused & _content_terms(text))


def _conversation_has_lexical_rut(lines: list[str]) -> bool:
    cleaned = [str(line).strip() for line in lines if str(line).strip()]
    if len(cleaned) < 6:
        return False
    sets = [_content_terms(line) for line in cleaned]
    counts = Counter(term for terms in sets for term in terms)
    threshold = max(4, (len(cleaned) * 3 + 3) // 4)  # ceil(75%)
    for term, count in counts.items():
        if count < threshold:
            continue
        member_sizes = [len(terms) for terms in sets if term in terms]
        terse_members = sum(size <= 4 for size in member_sizes)
        if terse_members >= 4:
            return True
    return False


_checkpoint_sanitized_this_process = False


def _sanitize_restored_checkpoint_once() -> None:
    global _checkpoint_sanitized_this_process
    if _checkpoint_sanitized_this_process:
        return
    _checkpoint_sanitized_this_process = True
    from sanitize_checkpoint import main as sanitize_checkpoint
    sanitize_checkpoint()


def load_agents() -> list[_base.CommunityAgent]:
    _sanitize_restored_checkpoint_once()
    return _base.load_agents()


def _sanitization_time_floor() -> int:
    path = Path(__file__).resolve().parent / "replay" / "checkpoint_sanitization.json"
    if not path.is_file():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(payload.get("time_floor", 0) or 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def latest_community_time_step(agents: list[_base.CommunityAgent]) -> int:
    return max(_base.latest_community_time_step(agents), _sanitization_time_floor())


def next_community_time_step(agents: list[_base.CommunityAgent]) -> int:
    return latest_community_time_step(agents) + 1


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
    elif _is_direct_information_question(inbound):
        grounding = (
            "Answer PARTNER's question directly with a concrete example, action, object, or "
            "sensory detail. Add real information that is not already in the question; do not "
            "paraphrase the question back to PARTNER. Do not invent shared history or an "
            "unrelated scenario."
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
            f"{anchor_rule}{_perspective_rule(inbound)} Do not invent a new pet, event, person, "
            "place, shared history, or unrelated scenario."
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
        "PARTNER: What's one small thing that can improve a morning?\n"
        "SELF: Opening a window for a minute can help.\n\n"
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
    direct_question = _is_direct_information_question(inbound)
    anchors = _grounding_words(inbound)
    require_anchor = (
        bool(anchors)
        and not _base._is_greeting_only(inbound)
        and not advice_question
        and not direct_question
    )
    anchor_hint = (
        " Include one of these exact topic words: " + ", ".join(anchors) + "."
        if require_anchor
        else ""
    )
    perspective_hint = _perspective_rule(inbound)
    overused = sorted(_overused_recent_terms(dialogue_history))
    rut_hint = (
        " The conversation has leaned too heavily on these words: "
        + ", ".join(overused)
        + ". Continue the idea through a new concrete detail without using those words."
        if overused
        else ""
    )
    retry_specs = [
        (rut_hint, 0.55),
        (
            (
                "Answer the advice question directly. Begin with 'You could' or a brief "
                "imperative such as 'Try' or 'Start'."
                if advice_question
                else "Answer with a concrete new detail instead of paraphrasing PARTNER."
                if direct_question
                else "Start with a concrete noun or detail from PARTNER's last line; do not begin "
                     "with 'that sounds' or 'that's a great idea'."
            )
            + anchor_hint
            + perspective_hint
            + rut_hint,
            0.70,
        ),
        (
            (
                "Give PARTNER one concrete next step. Do not say what SELF plans to do. "
                "Use second-person wording or a direct imperative."
                if advice_question
                else "Name one specific example or action that PARTNER did not already mention."
                if direct_question
                else "Ask one specific question about the current subject or make one specific observation. "
                     "No praise-preface, no vague placeholder, no service language, and no repeated line."
            )
            + anchor_hint
            + perspective_hint
            + rut_hint,
            0.85,
        ),
        (
            (
                "Begin exactly with 'You could' and finish one short concrete suggestion "
                "grounded in the conversation."
                if advice_question
                else "Give a short literal answer containing a new concrete noun or action."
                if direct_question
                else "Write one literal continuation using a concrete word from PARTNER's last line. "
                     "Begin differently from every earlier attempt. No generic approval sentence."
            )
            + anchor_hint
            + perspective_hint
            + rut_hint,
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
        detail_ok = _answer_adds_new_detail(text, inbound)
        rut_ok = not _would_extend_lexical_rut(text, dialogue_history)
        novel = bool(normalized_line) and normalized_line not in prior_lines
        distinct_attempt = normalized_line not in {
            " ".join(_base._normalize_words(previous)) for previous in attempts[:-1]
        }
        if (
            anchored
            and perspective_ok
            and detail_ok
            and rut_ok
            and novel
            and distinct_attempt
            and not _is_generic_attractor(text)
            and _base._is_usable_utterance(text, inbound, agent.name, other.name)
        ):
            return text

    previews = " | ".join(repr(text[:160]) for text in attempts)
    raise RuntimeError(
        "BitNet returned role-drifted, generic, vague, repetitive, ungrounded, or unusable "
        f"dialogue after {len(retry_specs)} transcript-completion attempts: {previews}"
    )


# Patch the preserved module's global lookup table so its choose_action keeps all existing
# memory, identity, and safety behavior while using the stricter reply generator.
_base._grounding_words = _grounding_words
_base._completion_prompt = _completion_prompt
_base._chat_bitnet = _chat_bitnet
_base._direct_bitnet_reply = _direct_bitnet_reply
_base.latest_community_time_step = latest_community_time_step
_base.next_community_time_step = next_community_time_step


if __name__ == "__main__":
    asyncio.run(_base.main())
