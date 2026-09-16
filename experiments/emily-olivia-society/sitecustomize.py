#!/usr/bin/env python3
"""Emily + Olivia runtime guards for live dialogue generation.

Python imports sitecustomize automatically for this experiment's interpreter runs.
Keep this isolated to experiments/emily-olivia-society so The Room is unaffected.
"""
from __future__ import annotations

import re

import community_cycle_base as _base
import dialogue_attractor as _attractor

_TRANSCRIPT_SCAFFOLD = re.compile(
    r"(?:^|\n)\s*(?:self-reply|partner-reply)\s*:|"
    r"<\|(?:assistant|user|system)\|>|"
    r"(?:^|\n)\s*(?:SELF|PARTNER)\s*:",
    re.IGNORECASE,
)

_original_is_usable_utterance = _base._is_usable_utterance
_original_candidate_dialogue_blocker = _attractor.candidate_dialogue_blocker


def _guarded_is_usable_utterance(
    text: str,
    inbound: str = "",
    agent_name: str = "",
    other_name: str = "",
) -> bool:
    if isinstance(text, str) and _TRANSCRIPT_SCAFFOLD.search(text):
        return False
    return _original_is_usable_utterance(text, inbound, agent_name, other_name)


def _live_candidate_dialogue_blocker(
    text: str,
    dialogue_history,
    *,
    inbound: str = "",
    cognitive_context: str = "",
    agent_name: str = "",
    history_limit: int = 48,
):
    """Do not treat the live message being answered as refractory history.

    The current inbound turn is already checked directly by the paper-act boundary,
    which rejects an exact full-message copy. Refractory-history checks should
    therefore apply only to earlier turns; otherwise normal conversational uptake
    can be misclassified as a short-subset echo and stall an unconsumed message.
    """
    history_rows = list(dialogue_history or [])
    live = str(inbound or "").strip()
    if live and history_rows:
        last = history_rows[-1]
        if isinstance(last, (tuple, list)) and len(last) >= 2 and str(last[1] or "").strip() == live:
            history_rows = history_rows[:-1]

    return _original_candidate_dialogue_blocker(
        text,
        history_rows,
        inbound=inbound,
        cognitive_context=cognitive_context,
        agent_name=agent_name,
        history_limit=history_limit,
    )


_base._is_usable_utterance = _guarded_is_usable_utterance
_attractor.candidate_dialogue_blocker = _live_candidate_dialogue_blocker
