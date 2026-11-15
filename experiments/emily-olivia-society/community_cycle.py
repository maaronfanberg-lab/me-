#!/usr/bin/env python3
"""Emily + Olivia research-style cycle.

This module intentionally exposes a very small compatibility surface while the
live chain is implemented in stanford_native_cycle.py. Stanford HCI genagents
owns persistent memory/retrieval/reflection; the pinned original Generative
Agents source supplies the map-free planning/reaction structure and spoken
next-line act boundary. Earlier local canned prompt/recovery machinery is not
on the live choose_action path.
"""
from __future__ import annotations

import asyncio
import re

import dialogue_boundary_guard as _boundary
import paper_act_adapter as _paper
import stanford_native_cycle as _native

# Keep the paper adapter's private-plan and retrieved-memory leak guards. The
# live wrapper deliberately leaves purely stylistic hard-veto checks disabled.
# Repetition itself is allowed when it functions as ordinary conversational
# acknowledgement or uptake; only structural resets remain a soft refractory
# signal below.
_paper._is_ungrounded_short_reference = lambda text, inbound: False
_paper._is_recent_echo = lambda text, dialogue_history: False
_boundary._is_mid_conversation_greeting_reset = lambda text, dialogue_history: False
_boundary._has_mid_turn_greeting_reset = lambda text, dialogue_history: False
_boundary._is_short_recent_echo = lambda text, dialogue_history: False

# Stanford's iterative conversation prompt already includes the transcript, but
# live replay showed that the small model can still treat the latest message as
# background and pivot elsewhere. Make the live inbound turn explicit at the act
# boundary without prescribing any reply content. This applies equally to
# Emily↔Olivia and Alex↔agent turns because they share the same paper-act path.
_paper_prompt_base = _paper._paper_prompt


def _uptake_focused_paper_prompt(agent, other, dialogue_history, inbound: str, cognitive_context: str) -> str:
    prompt = _paper_prompt_base(agent, other, dialogue_history, inbound, cognitive_context)
    live = str(inbound or "").strip()
    if not live:
        return prompt

    requirement = (
        "CONVERSATIONAL UPTAKE REQUIREMENT:\n"
        f"The most recent live message from {other.name} is: {live}\n"
        f"{agent.name}'s next utterance must respond to that specific message. "
        "If it contains a question, answer or address that question in this turn before changing the subject. "
        "Acknowledgement, agreement, repetition, paraphrase, disagreement, humor, and invented details are all allowed "
        "when they function as part of a response. Do not ignore the live message and pivot to an unrelated topic. "
        "After responding, the conversation may continue naturally.\n"
    )
    speaker_cue = f'{agent.name}: "'
    cue_index = prompt.rfind(speaker_cue)
    if cue_index < 0:
        return prompt + "\n\n" + requirement
    return prompt[:cue_index] + requirement + "\n" + prompt[cue_index:]


_paper._paper_prompt = _uptake_focused_paper_prompt

# Keep the Stanford/paper act path intact, but fail closed and resample the same
# stochastic generator when the live replay proves identity or grounding drift.
_native.generate_spoken_action = _boundary.install_spoken_action_guard(_native.generate_spoken_action)

# Live replay proved two distinct failure classes:
#   1) hard identity drift (Emily claiming to be Olivia, or vice versa), and
#   2) harmless but sticky social-reset attractors (Hi/Hey/Hello/How are you?).
# Identity drift must never be published. Social resets should merely trigger
# another stochastic sample. Critically, social-reset filtering is fail-open:
# if both structurally valid Stanford samples are still soft attractors, speak
# the first valid one rather than turning anti-repetition into a stall. The
# underlying paper sampler owns its own bounded stochastic work; this outer
# identity/social refractory layer gets exactly two samples total (initial plus
# one retry). Boundary, attractor, and continuous-session retry layers remain
# single-pass, so there is no restored multiplicative retry stack.
_identity_base_generate = _native.generate_spoken_action
_IDENTITY_ATTEMPTS = 2
_SOCIAL_RESET_START = re.compile(r"^\s*(?:hi|hello|hey|oh\s*,?\s*(?:hi|hello|hey))\b", re.IGNORECASE)
_SOCIAL_CHECKIN = re.compile(r"\bhow\s+are\s+you(?:\s+doing)?(?:\s+today)?\b", re.IGNORECASE)
_SERVICE_ASSISTANT = re.compile(
    r"\b(?:can\s+i\s+help\s+you|how\s+can\s+i\s+help|what\s+can\s+i\s+do\s+for\s+you|what\s+do\s+you\s+need\s+to\s+know)\b",
    re.IGNORECASE,
)
_SELF_CONVERSATION = re.compile(
    r"\b(?:talk(?:ing)?|speak(?:ing)?|chat(?:ting)?|(?:having\s+)?a\s+conversation)\s+(?:to|with)\s+myself\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _claims_peer_identity(text: object, agent_name: str, other_name: str) -> bool:
    candidate = str(text or "")
    agent = str(agent_name or "").strip()
    other = str(other_name or "").strip()
    if not agent or not other or agent.casefold() == other.casefold():
        return False
    peer = re.escape(other)
    return bool(
        re.search(
            rf"\b(?:i\s+am|i'm|my\s+name\s+is|my\s+name['’]?s)\s+{peer}\b",
            candidate,
            re.IGNORECASE,
        )
    )


def _word_list(text: object) -> list[str]:
    return [match.group(0).casefold() for match in _WORD.finditer(str(text or ""))]


def _is_social_reset(text: object, dialogue_history) -> bool:
    history = list(dialogue_history or [])
    if not history:
        return False
    candidate = str(text or "").strip()
    if not (_SOCIAL_RESET_START.search(candidate) or _SOCIAL_CHECKIN.search(candidate)):
        return False

    # A live inbound means the conversation has already started. Treat a new
    # greeting/check-in as a soft reset as soon as one prior turn occupied that
    # same basin; the autonomous opener itself is exempt because it has no inbound.
    for _speaker, prior in history[-4:]:
        prior_text = str(prior or "").strip()
        if _SOCIAL_RESET_START.search(prior_text) or _SOCIAL_CHECKIN.search(prior_text):
            return True
    return False


def _is_short_semantic_echo(text: object, dialogue_history) -> bool:
    output = _word_list(text)
    if not output or len(output) > 7:
        return False
    for _speaker, prior in list(dialogue_history or [])[-4:]:
        previous = _word_list(prior)
        if not previous or len(previous) > 7:
            continue
        out_core = [word for word in output if word not in {"emily", "olivia"}]
        prev_core = [word for word in previous if word not in {"emily", "olivia"}]
        if out_core and out_core == prev_core:
            return True
    return False


def _is_inbound_fragment_echo(text: object, inbound: object) -> bool:
    output = _word_list(text)
    source = _word_list(inbound)
    if len(output) < 3 or len(output) > 7 or len(source) < len(output):
        return False
    for start in range(0, len(source) - len(output) + 1):
        if source[start : start + len(output)] == output:
            return True
    overlap = sum(1 for word in output if word in source)
    return overlap >= max(3, len(output) - 1)


def _is_service_assistant_stance(text: object) -> bool:
    return bool(_SERVICE_ASSISTANT.search(str(text or "")))


def _claims_impossible_self_conversation(text: object, inbound: object, other) -> bool:
    return bool(str(inbound or "").strip() and getattr(other, "name", "") and _SELF_CONVERSATION.search(str(text or "")))


def _identity_guarded_spoken_action(agent, other, dialogue_history=None, inbound: str = "", cognitive_context: str = ""):
    rejected_identity: list[str] = []
    soft_fallback: str | None = None

    for _ in range(_IDENTITY_ATTEMPTS):
        text = _identity_base_generate(
            agent,
            other,
            dialogue_history=dialogue_history,
            inbound=inbound,
            cognitive_context=cognitive_context,
        )

        if _claims_peer_identity(text, getattr(agent, "name", ""), getattr(other, "name", "")):
            rejected_identity.append(str(text)[:180])
            continue

        if _claims_impossible_self_conversation(text, inbound, other):
            rejected_identity.append("self-conversation:" + str(text)[:160])
            continue

        if _is_service_assistant_stance(text):
            if soft_fallback is None:
                soft_fallback = text
            continue

        # Do not reject ordinary acknowledgement/paraphrase merely because it
        # resembles the inbound turn. The live requirement is uptake, not lexical
        # novelty. Only a repeated greeting/check-in remains a soft reset signal.
        if str(inbound or "").strip() and _is_social_reset(text, dialogue_history):
            if soft_fallback is None:
                soft_fallback = text
            continue

        return text

    if soft_fallback is not None:
        return soft_fallback

    raise RuntimeError(
        "paper-derived Stanford act repeatedly crossed the live dialogue grounding boundary: "
        "peer-identity/social-state contradiction: " + " | ".join(rejected_identity[-4:])
    )


_native.generate_spoken_action = _identity_guarded_spoken_action

CommunityAgent = _native.CommunityAgent
load_agents = _native.load_agents
observation_text = _native.observation_text
choose_action = _native.choose_action
choose_opening_action = _native.choose_opening_action
next_community_time_step = _native.next_community_time_step
latest_community_time_step = _native.latest_community_time_step
_is_usable_utterance = _native._is_usable_utterance
_grounding_words = _native._grounding_words


def __getattr__(name: str):
    return getattr(_native, name)


if __name__ == "__main__":
    asyncio.run(_native.run_one_cycle())
