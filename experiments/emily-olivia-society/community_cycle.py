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

import stanford_native_cycle as _native

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
