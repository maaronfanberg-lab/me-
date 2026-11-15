"""A purely owner-originated private goal opportunity during public silence.

This is the missing endogenous internal path: when an agent has NO public
message and NO active goal, a previous, source-authenticated, model-authored
private reflection may give that same agent a reason to consider a new goal.

The scheduler may offer a bounded model call but cannot invent a goal,
intention, external event, or public utterance. Only a valid model-authored
first-person goal yields a candidate private transition. No public speech
can be generated or published by this module.
"""
from __future__ import annotations

from collections.abc import Mapping

from room_endogenous_preflight import AGENTS
from room_endogenous_private_growth import messages_for, accept_private_goal
from room_endogenous_reflection import authenticated_reflection_ids
from room_endogenous_goal_journal import VERSION, active_goals


def propose_inner_goal(*, owner: str, cycle: int, profile: dict,
                       private_state: dict, journal: dict, model_request,
                       max_seconds: float = 28.0) -> dict:
    safe = {"eligible": False, "ok": False, "changed": False,
            "calls": 0, "journal": journal, "private_state": private_state,
            "reason": "no_owned_self_reflection"}
    if (owner not in AGENTS or type(cycle) is not int or cycle < 0
            or not isinstance(profile, Mapping) or not isinstance(private_state, dict)
            or not isinstance(journal, Mapping) or journal.get("owner") != owner
            or journal.get("schema") != VERSION
            or not callable(model_request)
            or type(max_seconds) not in (int,float) or not 0 < max_seconds <= 28):
        return {**safe, "reason": "invalid_private_owner_or_budget"}
    if active_goals(journal, owner=owner):
        return {**safe, "reason": "already_has_own_active_goal"}
    authenticated = authenticated_reflection_ids(
        owner=owner, private_state=private_state)
    if not authenticated:
        return safe
    try:
        messages = messages_for(
            kind="goal", agent=owner, profile=profile,
            private_state=private_state, journal=journal,
            public_history=[])
        raw = model_request(messages, max_seconds)
    except Exception:
        return {**safe, "eligible": True, "calls": 1, "reason": "model_unavailable"}
    result = accept_private_goal(
        owner=owner, cycle=cycle, journal=journal,
        private_state=private_state, public_history=[],
        response=raw)
    return {"eligible":True,"ok":result["ok"],
            "changed":result["changed"],"calls":1,
            "journal":result["journal"],
            "private_state":private_state,
            "reason":result["issue"] if not result["ok"] else
                     "self_goal_emerged" if result["changed"] else "self_chose_no_goal"}
