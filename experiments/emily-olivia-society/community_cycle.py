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

import dialogue_boundary_guard as _boundary
import paper_act_adapter as _paper
import stanford_native_cycle as _native

# The pinned Stanford conversation path accepts the model's next conversational
# line and only ends when the conversation logic says to end. Keep hard boundary
# checks for malformed/control output, identity drift, and unsupported external
# claims, but do not let local conversational-style heuristics veto harmless
# references, greetings, or short echoes until the same 10B sample is exhausted.
_paper._is_ungrounded_short_reference = lambda text, inbound: False
_paper._is_recent_echo = lambda text, dialogue_history: False
_paper._is_private_plan_echo = lambda text, cognitive_context: False
_paper._is_retrieved_memory_echo = lambda text, cognitive_context: False
_boundary._is_mid_conversation_greeting_reset = lambda text, dialogue_history: False
_boundary._has_mid_turn_greeting_reset = lambda text, dialogue_history: False
_boundary._is_short_recent_echo = lambda text, dialogue_history: False

# Keep the Stanford/paper act path intact, but fail closed and resample the same
# stochastic generator when the live replay proves identity or grounding drift.
_native.generate_spoken_action = _boundary.install_spoken_action_guard(_native.generate_spoken_action)

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
