#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from collections import Counter
from difflib import SequenceMatcher

import community_cycle_base as _base
from community_cycle_base import *  # noqa: F401,F403

# Underscore helpers are intentionally re-exported because the smoke verifier imports one.
_is_usable_utterance = _base._is_usable_utterance

_GENERIC_ANCHOR_WORDS = {
    "anything", "don't", "dont", "good", "great", "hello", "hey", "hi", "know",
    "little", "made", "make", "makes", "maybe", "nice", "okay", "ok", "really",
    "small", "something", "start", "thing", "things", "thinking", "trying", "well",
    "what's", "that's", "i'm", "i've", "you're", "it's", "there's",
}

_GENERIC_REPLY_LEADS = (
    "that sounds like a great idea",
    "that's a great idea",
    "that sounds great",
    "i'd love to see",
    "i've never done anything like that before",
    "i don't know what to say",
    "i dont know what to say",
    "i'm not sure what to say",
    "im not sure what to say",
    "i'm glad it's going well now",
    "im glad its going well now",
)

# Words that can be perfectly natural once, but become low-information when a conversation
# keeps recycling them without a concrete cause, object, action, or event.
_ABSTRACT_LOOP_WORDS = {
    "change", "changed", "changes", "changing", "different", "difference", "feel",
    "feeling", "feelings", "perception", "perspective", "view", "views", "world",
    "way", "ways", "look", "looking", "see", "seeing", "sure", "unsure", "uncertain",
    "uncertainty", "think", "thinking", "thought", "thoughts", "everything",
    "energy", "energetic", "energized", "energizing", "happy", "happiness",
    "relaxed", "relaxing", "amazing", "doing", "done", "stuff",
}

_ADVICE_QUESTIONS = (
    "what would you suggest",
    "what do you suggest",
    "what would you recommend",
    "what do you recommend",
)

_DAY_CHECKINS = (
    "how's your day",
    "hows your day",
    "how is your day",
    "how are you",
    "how're you",
    "how have you been",
    # Scheduled runs can legitimately start clean after a contaminated checkpoint is refused.
    # In that case there is no earlier dialogue to continue, so treat the continuity seed as
    # ordinary small talk rather than forcing nonsensical lexical grounding to "left off".
    "let's continue naturally from where we left off",
    "lets continue naturally from where we left off",
)

_INTENT_PHRASES = (
    "thinking of",
    "thinking about",
    "trying to",
    "want to",
    "planning to",
    "plan to",
    "might try",
    "going to try",
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


def _is_day_checkin(inbound: str) -> bool:
    lowered = " ".join(inbound.lower().split())
    return any(phrase in lowered for phrase in _DAY_CHECKINS)


def _is_intent_statement(inbound: str) -> bool:
    lowered = " ".join(inbound.lower().split())
    return any(phrase in lowered for phrase in _INTENT_PHRASES)


def _is_open_question(inbound: str) -> bool:
    lowered = " ".join(inbound.lower().split())
    if _is_day_checkin(lowered):
        return True
    normalized = lowered.replace("!", ".").replace("?", ".")
    starters = (
        "what ", "what's ", "whats ", "why ", "how ", "how's ", "hows ",
        "where ", "when ", "which ", "who ",
    )
    return any(part.strip().startswith(starters) for part in normalized.split(".") if part.strip())


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


def _has_scaffold_fragment(text: str) -> bool:
    """Reject complete or truncated model-control/transcript markers before delivery."""
    lowered = str(text).lower()
    if "<|" in lowered or "|>" in lowered:
        return True
    stripped_lines = [line.strip().lower() for line in str(text).splitlines()]
    return any(
        line.startswith(("self:", "partner:", "self-reply:", "partner-reply:"))
        for line in stripped_lines
    )


def _is_stagnant_topic_loop(
    reply: str,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None,
) -> bool:
    """Reject cross-speaker low-information loops that fail to add concrete detail."""
    recent = [str(text) for _speaker, text in (dialogue_history or []) if str(text).strip()][-5:]
    if len(recent) < 4:
        return False

    signatures = [_content_signature(text) for text in recent]
    counts = Counter(word for signature in signatures for word in signature)
    repeated_theme = {word for word, count in counts.items() if count >= 2}
    if not (repeated_theme & _ABSTRACT_LOOP_WORDS):
        return False

    reply_signature = _content_signature(reply)
    if not (reply_signature & repeated_theme):
        return False

    # Long replies that repeat the same low-information state word are exactly the attractor
    # seen in run #67 ("energy / feeling / doing things"). Do not let synonym inflation count
    # as progress.
    reply_counts = Counter(_base._normalize_words(reply))
    repeated_low_info = {
        word for word, count in reply_counts.items()
        if count >= 2 and word in _ABSTRACT_LOOP_WORDS
    }
    inbound_signature = _content_signature(inbound)
    if repeated_low_info & inbound_signature and len(_base._normalize_words(reply)) > 14:
        return True

    historical_words = set().union(*signatures) if signatures else set()
    fresh_words = reply_signature - historical_words - inbound_signature
    fresh_concrete = fresh_words - _ABSTRACT_LOOP_WORDS
    # One new concrete noun is enough for a short natural line. Longer replies need at least
    # two genuinely new concrete details so a lone adjective cannot launder a repetitive loop.
    min_fresh = 1 if len(_base._normalize_words(reply)) <= 12 else 2
    return len(fresh_concrete) < min_fresh


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

    if _is_day_checkin(inbound):
        grounding = (
            "PARTNER is making ordinary greeting small talk and asking how SELF is doing. "
            "Answer naturally and briefly with an ordinary present-moment detail. SELF may ask "
            "how PARTNER is doing in return. Do not turn greeting or continuity words into "
            "abstract topics and do not invent a job, event, place, or backstory."
        )
    elif _base._is_greeting_only(inbound):
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
            "person, place, shared history, or unrelated scenario. You may add a small ordinary "
            "action, preference, or example from SELF when it directly answers the topic."
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
        "move the conversation forward with a genuinely new detail, reaction, answer, or question. "
        "If the recent exchange is circling an abstract idea, break the loop with a concrete "
        "everyday action, object, example, or specific question instead of another synonym."
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


def _recovery_reply(
    agent: _base.CommunityAgent,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None,
) -> str:
    """Return a grounded, nonfatal bridge when BitNet collapses into a bad-generation attractor."""
    if _is_day_checkin(inbound):
        candidates = [
            "Pretty good so far. How about you?",
            "Good, actually. How's your day going?",
            "Not bad. How are you doing?",
        ]
    elif _is_intent_statement(inbound):
        candidates = [
            "What made you want to try it?",
            "Have you decided how you want to start?",
            "What got you interested in that?",
        ]
    elif _is_open_question(inbound):
        anchors = _grounding_words(inbound, limit=3)
        anchor = anchors[0] if anchors else "that"
        candidates = [
            f"I'd probably keep {anchor} simple and start with one small thing.",
            f"For me, the {anchor} part matters most when it's concrete.",
            f"My first instinct would be to make {anchor} more specific.",
        ]
    else:
        candidates = [
            "What happened next?",
            "How did that go?",
            "What do you think about it now?",
        ]

    prior_lines = {
        " ".join(_base._normalize_words(str(text)))
        for _speaker, text in (dialogue_history or [])
        if str(text).strip()
    }
    for candidate in candidates:
        normalized = " ".join(_base._normalize_words(candidate))
        if normalized in prior_lines:
            continue
        if _is_generic_attractor(candidate):
            continue
        if _too_similar_to_own_history(candidate, agent.name, dialogue_history):
            continue
        if _base._is_usable_utterance(candidate, inbound):
            return candidate

    return "Tell me a little more about that."


def _direct_bitnet_reply(
    agent: _base.CommunityAgent,
    other: _base.CommunityAgent,
    inbound: str,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> str:
    import os

    max_tokens = min(96, max(16, int(os.environ.get("COMMUNITY_MAX_TOKENS", "64"))))
    anchors = _grounding_words(inbound)
    checkin = _is_day_checkin(inbound)
    require_anchor = bool(anchors) and not _base._is_greeting_only(inbound) and not checkin
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
        non_stagnant = not _is_stagnant_topic_loop(text, inbound, dialogue_history)
        if (
            anchored
            and novel
            and distinct_attempt
            and substantive
            and non_recycled
            and non_stagnant
            and not _has_scaffold_fragment(text)
            and not _is_generic_attractor(text)
            and _base._is_usable_utterance(text, inbound, agent.name, other.name)
        ):
            return text

    return _recovery_reply(agent, inbound, dialogue_history)


# Patch the preserved module's global lookup table so its choose_action keeps all existing
# memory, identity, and safety behavior while using the stricter reply generator.
_base._grounding_words = _grounding_words
_base._completion_prompt = _completion_prompt
_base._chat_bitnet = _chat_bitnet
_base._direct_bitnet_reply = _direct_bitnet_reply


if __name__ == "__main__":
    asyncio.run(_base.main())