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
from room_endogenous_reflection import apply_private_reflection

REQUIRED = ("action", "motivation", "cost", "basis")
REQUIRED_SET = frozenset(REQUIRED)
OPTIONAL = frozenset({"goal_proposal", "reflection_update"})
MAX_RAW = 4096


def interpret_private_step(*, agent: str, cycle: int, raw: object,
                           journal: dict, public_history: list[dict],
                           consumed_ids: set[str], private_state: dict | None = None) -> dict:
    """Return a validated private bid and a candidate updated journal.

    Caller is responsible for atomically committing the validated private
    journal after normal privacy and persistence gates. No public speech is
    emitted here. Never retry by fabricating an intention.
    """
    safe = {"ok": False, "reason": "invalid_output", "bid": None,
            "journal": journal, "goal_changed": False,
            "private_state": private_state, "belief_changed": False}
    if (not isinstance(raw, str) or len(raw) > MAX_RAW
            or not isinstance(journal, Mapping)
            or journal.get("schema") != VERSION or journal.get("owner") != agent):
        return safe
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return safe
    if not isinstance(value, dict) or not REQUIRED_SET.issubset(value) or set(value) - (REQUIRED_SET | OPTIONAL):
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
    next_state = private_state
    changed = False
    if "reflection_update" in value:
        if not isinstance(private_state, dict):
            return {**safe, "reason": "missing_owner_private_state"}
        try:
            transition = apply_private_reflection(
                agent=agent, cycle=cycle, bid=private_bid,
                prior_state=private_state, update=value["reflection_update"])
        except (ValueError, TypeError, KeyError, IndexError):
            return {**safe, "reason": "invalid_reflection_update"}
        next_state, changed = transition["state"], transition["changed"]
    return {"ok": True, "reason": "validated_private_step",
            "bid": private_bid, "journal": next_journal,
            "goal_changed": next_journal != journal,
            "private_state": next_state, "belief_changed": changed}
