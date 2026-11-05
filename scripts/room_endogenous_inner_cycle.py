"""Silent research cycle where a remembered self-reflection may seed a goal.

This deliberately does NOT fabricate public speech. It is an isolated pure
research transaction binding the independently generated private goal to the
correct owner, and never runs when the owner has no authenticated previous
private reflection. Every call is bounded and may result in no change.

The research production adapter is NOT enabled; this module does not write
main, the public feed, or a viewer relay.
"""
from __future__ import annotations

import copy

from room_endogenous_preflight import AGENTS
from room_endogenous_goal_journal import VERSION
from room_endogenous_inner_tick import propose_inner_goal
from room_endogenous_reflection import authenticated_reflection_ids
from room_endogenous_transaction_store import apply_cycle, STORE_VERSION


def silent_inner_cycle(*, snapshot: dict, owner: str, cycle: int,
                       cycle_id: str, profile: dict, model_request) -> tuple[dict,dict]:
    if (not isinstance(snapshot,dict) or snapshot.get("schema") != STORE_VERSION
            or owner not in AGENTS or type(cycle) is not int or cycle < 0
            or not isinstance(cycle_id,str) or not isinstance(profile,dict)
            or not callable(model_request)):
        raise ValueError("invalid source-bound silent cycle")
    if cycle_id in snapshot.get("cycles", {}):
        # Already committed. A retry must not ask an LLM to invent another goal.
        prior=snapshot["cycles"][cycle_id]
        if prior.get("outcome") != "silent":
            raise ValueError("replayed cycle was not silent")
        return copy.deepcopy(snapshot),{
            "decision":"silent","model_calls":0,"goal_changed":False,
            "replayed":True,"published_dialogue":False}
    own=snapshot["characters"][owner]
    state=own["private_state"]
    journal=own["journal"]
    if not isinstance(state,dict) or journal.get("owner")!=owner or journal.get("schema")!=VERSION:
        raise ValueError("foreign or corrupt private mind")
    result=propose_inner_goal(
        owner=owner,cycle=cycle,profile=profile,
        private_state=state,journal=journal,
        model_request=model_request)
    candidates={}
    if result["ok"] and result["changed"]:
        active_reflections=authenticated_reflection_ids(
            owner=owner,private_state=state)
        origin=result["journal"]["goals"][-1].get("origin")
        if (not isinstance(origin,dict)
                or origin.get("kind")!="own_reflection"
                or origin.get("source_id") not in active_reflections):
            raise ValueError("forged owner-reflection origin")
        # This envelope is an internal *private* transition, not a model bid
        # to say something publicly.
        candidates[owner]={
            "ok":True,"private_only":True,"utterance":"",
            "bid":{"speaker":owner,"cycle":cycle,"action":"wait",
                   "schema":"room_private_cognition_step_v1",
                   "source_id":origin["source_id"]},
            "journal":result["journal"],"private_state":state,
        }
    next_state,_=apply_cycle(
        snapshot,expected_revision=snapshot["revision"],cycle=cycle,
        cycle_id=cycle_id,candidates=candidates,
        selected={"decision":"silent","utterance":""},
        visitor_messages=[])
    return next_state,{
        "decision":"silent","model_calls":result["calls"],
        "goal_changed":bool(candidates),"replayed":False,
        "reason":result["reason"],"published_dialogue":False,
        "public_outbox_length":len(next_state["outbox"]),
    }
