"""One model-authored private decision can include an optional own-goal update.

RESEARCH ONLY. Pure transition; no model calls, no file writes, no live speech.
The caller must bind the model response to the correct character before use.
An invalid bid or unsupported goal update rejects the entire private step.
Private goal evolution is allowed even when the chosen action is silence.
"""
from __future__ import annotations

import json
from collections.abc import Mapping

from room_endogenous_shadow import model_bid
from room_endogenous_goal_journal import active_goals, apply_proposal, VERSION

REQUIRED = frozenset({"action", "motivation", "cost", "basis"})
OPTIONAL = frozenset({"goal_proposal"})
MAX_RAW = 4096


def interpret_private_step(*, agent: str, cycle: int, raw: object,
                           journal: dict, public_history: list[dict],
                           consumed_ids: set[str]) -> dict:
    """Return a validated private bid and a candidate updated journal.

    Caller is responsible for atomically committing the validated private
    journal after normal privacy and persistence gates. No public speech is
    emitted here. Never retry by fabricating an intention.
    """
    safe = {"ok": False, "reason": "invalid_output", "bid": None,
            "journal": journal, "goal_changed": False}
    if (not isinstance(raw, str) or len(raw) > MAX_RAW
            or not isinstance(journal, Mapping)
            or journal.get("schema") != VERSION or journal.get("owner") != agent):
        return safe
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return safe
    if not isinstance(value, dict) or not REQUIRED.issubset(value) or set(value) - (REQUIRED | OPTIONAL):
        return safe
    if not isinstance(public_history, list) or not isinstance(consumed_ids, set):
        return safe
    goals = active_goals(journal, owner=agent)
    private_bid = model_bid(agent=agent, cycle=cycle,
                            response=json.dumps({key: value[key] for key in REQUIRED}),
                            public_history=public_history,
                            goals=goals, consumed_ids=consumed_ids)
    if private_bid is None:
        return {**safe, "reason": "invalid_or_unwitnessed_bid"}
    next_journal = journal
    if "goal_proposal" in value:
        try:
            next_journal = apply_proposal(
                journal, owner=agent,
                expected_revision=journal["revision"],
                cycle=cycle, proposal=value["goal_proposal"],
                public_history=public_history)
        except (ValueError, TypeError, KeyError, IndexError):
            return {**safe, "reason": "invalid_or_unwitnessed_goal"}
    return {"ok": True, "reason": "validated_private_step",
            "bid": private_bid, "journal": next_journal,
            "goal_changed": next_journal != journal}
