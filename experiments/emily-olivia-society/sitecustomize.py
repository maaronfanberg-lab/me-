#!/usr/bin/env python3
"""Emily + Olivia runtime guard against model transcript/scaffold leakage.

Python imports sitecustomize automatically for this experiment's interpreter runs.
Keep this isolated to experiments/emily-olivia-society so The Room is unaffected.
"""
from __future__ import annotations

import re

import community_cycle_base as _base

_TRANSCRIPT_SCAFFOLD = re.compile(
    r"(?:^|\n)\s*(?:self-reply|partner-reply)\s*:|"
    r"<\|(?:assistant|user|system)\|>|"
    r"(?:^|\n)\s*(?:SELF|PARTNER)\s*:",
    re.IGNORECASE,
)

_original_is_usable_utterance = _base._is_usable_utterance


def _guarded_is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    if isinstance(text, str) and _TRANSCRIPT_SCAFFOLD.search(text):
        return False
    return _original_is_usable_utterance(text, inbound, agent_name, other_name)


_base._is_usable_utterance = _guarded_is_usable_utterance
