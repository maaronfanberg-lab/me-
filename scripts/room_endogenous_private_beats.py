"""At most two bounded, owner-generated private cognition opportunities.

Research-only adapter used AFTER an agent has already generated its own public
speech bid or valid silence. Both cognitive operations are voluntary, and a
model-produced [NO_GOAL]/[NO_CHANGE] is a first-class no-op. It does not choose
speakers, write public turns, or assign goals. Private state is returned as a
candidate for the existing atomic research store.
"""
from __future__ import annotations

import copy
import time
from collections.abc import Mapping

from room_endogenous_private_growth import (
    messages_for, accept_private_goal, accept_private_revision,
)
from room_endogenous_goal_journal import VERSION
from room_endogenous_preflight import AGENTS

MAX_PRIVATE_CALLS = 2
MAX_SECONDS = 34.0


def optional_private_growth(*, owner: str, cycle: int,
                            candidate: dict, profile: dict,
                            public_history: list[dict],
                            goal_model, revision_model,
                            budget_seconds: float = 72.0) -> tuple[dict, dict]:
    """Return a proposed candidate, never mutate the caller's state.

    A failed model call may not produce a synthetic private state. A valid
    goal can still persist when the later self-revision is unavailable.
    """
    if (owner not in AGENTS or type(cycle) is not int or cycle < 0
            or not isinstance(candidate, dict) or not candidate.get("ok")
            or candidate.get("bid", {}).get("speaker") != owner
            or candidate.get("bid", {}).get("cycle") != cycle
            or not isinstance(profile, dict)
            or not isinstance(public_history, list)
            or not callable(goal_model) or not callable(revision_model)
            or type(budget_seconds) not in (int, float)
            or not 0 < budget_seconds <= 72.0):
        raise ValueError("invalid private-growth owner or budget")
    initial = copy.deepcopy(candidate)
    journal = initial.get("journal")
    state = initial.get("private_state")
    if (not isinstance(journal, dict) or journal.get("owner") != owner
            or journal.get("schema") != VERSION or not isinstance(state, dict)):
        raise ValueError("owner state unavailable")
    start = time.monotonic()
    report = {"goal": "not_attempted", "revision": "not_attempted",
              "model_calls": 0, "private_state_changed": False,
              "goal_state_changed": False}
    # Independently chosen NO_GOAL/NO_CHANGE do not mutate persistent state.
    try:
        prompt = messages_for(kind="goal", agent=owner, profile=profile,
                              private_state=state, journal=journal,
                              public_history=public_history)
        raw = goal_model(prompt, min(MAX_SECONDS, budget_seconds))
        report["model_calls"] += 1
        outcome = accept_private_goal(
            owner=owner, cycle=cycle, journal=journal,
            public_history=public_history, response=raw)
        report["goal"] = "changed" if outcome["changed"] else "unchanged" if outcome["ok"] else outcome["issue"]
        if outcome["ok"]:
            journal = outcome["journal"]
    except Exception:
        report["goal"] = "model_unavailable"
    remaining = budget_seconds - (time.monotonic()-start)
    if remaining > 0:
        try:
            prompt = messages_for(kind="revision", agent=owner,
                                  profile=profile, private_state=state,
                                  journal=journal, public_history=public_history)
            raw = revision_model(prompt, min(MAX_SECONDS, remaining))
            report["model_calls"] += 1
            outcome = accept_private_revision(
                owner=owner, cycle=cycle, journal=journal,
                private_state=state, public_history=public_history,
                response=raw)
            report["revision"] = "changed" if outcome["changed"] else "unchanged" if outcome["ok"] else outcome["issue"]
            if outcome["ok"]:
                state = outcome["private_state"]
        except Exception:
            report["revision"] = "model_unavailable"
    else:
        report["revision"] = "time_budget_exhausted"
    initial["journal"] = journal
    initial["private_state"] = state
    initial["goal_changed"] = journal != candidate["journal"]
    initial["belief_changed"] = state != candidate["private_state"]
    report["goal_state_changed"] = initial["goal_changed"]
    report["private_state_changed"] = initial["belief_changed"]
    return initial, report
