#!/usr/bin/env python3
"""Emily + Olivia research-style cycle.

This module intentionally exposes a very small compatibility surface while the
actual speech decision is delegated to Stanford HCI genagents in
stanford_native_cycle.py.  Earlier local prompt/retry/recovery machinery is no
longer on the live choose_action path.
"""
from __future__ import annotations

import asyncio

import stanford_native_cycle as _native

CommunityAgent = _native.CommunityAgent
load_agents = _native.load_agents
observation_text = _native.observation_text
choose_action = _native.choose_action
next_community_time_step = _native.next_community_time_step
latest_community_time_step = _native.latest_community_time_step
_is_usable_utterance = _native._is_usable_utterance
_grounding_words = _native._grounding_words


def __getattr__(name: str):
    return getattr(_native, name)


if __name__ == "__main__":
    asyncio.run(_native.run_one_cycle())
