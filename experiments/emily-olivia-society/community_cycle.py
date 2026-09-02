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

# The pinned Stanford conversation path accepts the model's next conversational
# line and only ends when the conversation logic says to end. Keep local style
# heuristics from vetoing harmless references, greetings, or short echoes, while
# retaining the paper adapter's private-plan and retrieved-memory leak guards.
# Private cognition may influence a spoken act, but must never be read aloud as
# serialized plan/memory text.
_paper._is_ungrounded_short_reference = lambda text, inbound: False
_paper._is_recent_echo = lambda text, dialogue_history: False
_boundary._is_mid_conversation_greeting_reset = lambda text, dialogue_history: False
_boundary._has_mid_turn_greeting_reset = lambda text, dialogue_history: False
_boundary._is_short_recent_echo = lambda text, dialogue_history: False

# Keep the Stanford/paper act path intact, but fail closed and resample the same
# stochastic generator when the live replay proves identity or grounding drift.
_native.generate_spoken_action = _boundary.install_spoken_action_guard(_native.generate_spoken_action)

# The generic boundary guard catches self-address and role drift, but a live
# replay proved that the model can still emit a direct peer-identity self-claim
# (for example Emily saying "my name's Olivia"). This is an integrity failure,
# not a style preference. Resample the same Stanford generator; never substitute
# authored dialogue. A generous retry budget keeps this hard identity boundary
# from becoming an ordinary liveness bottleneck.
_identity_base_generate = _native.generate_spoken_action
_IDENTITY_ATTEMPTS = 8


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


def _identity_guarded_spoken_action(agent, other, dialogue_history=None, inbound: str = "", cognitive_context: str = ""):
    rejected: list[str] = []
    for _ in range(_IDENTITY_ATTEMPTS):
        text = _identity_base_generate(
            agent,
            other,
            dialogue_history=dialogue_history,
            inbound=inbound,
            cognitive_context=cognitive_context,
        )
        if not _claims_peer_identity(text, getattr(agent, "name", ""), getattr(other, "name", "")):
            return text
        rejected.append(str(text)[:180])
    raise RuntimeError(
        "paper-derived Stanford act repeatedly crossed the live dialogue grounding boundary: "
        "peer-identity self-claim: " + " | ".join(rejected[-4:])
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
