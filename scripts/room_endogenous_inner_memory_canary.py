#!/usr/bin/env python3
"""Real 3B endogenous self-reflection -> idle goal -> optional speech.

The only external event is a synthetic old observation. First the real
model privately revises its own belief using that observation. Then no new
public message or goal is supplied: from its own earlier validated reflection,
the SAME character may spontaneously propose a personal aim, or choose none.
A future model call may speak from the resulting owned goal. None of these
changes are written to the real Room or its relay.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from room_endogenous_goal_journal import new_journal, active_goals
from room_endogenous_private_growth import messages_for, accept_private_revision
from room_endogenous_inner_tick import propose_inner_goal
from room_endogenous_reflection import authenticated_reflection_ids
from room_endogenous_speech_option import build_request, parse
from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL

HISTORY=[
  {"speaker":"owen","id":"memory-fixture-1",
   "text":"The lamp flickered twice, but the wall voltage remained stable."},
  {"speaker":"allen","id":"memory-fixture-2",
   "text":"Sarah, what would cause you to reconsider your earlier voltage-drop explanation?"}
]
SEED={
  "what_i_currently_believe":"The lamp flickered because the power voltage dropped.",
  "belief_confidence":.55,
  "what_just_changed":"An observation contradicted my voltage-drop assumption.",
  "last_updated_cycle":0
}


def evaluate(config, revision_model, goal_model, speech_model):
    profile=(config.get("p") or {}).get("sarah")
    if not isinstance(profile,dict):
        raise ValueError("missing owner")
    state=dict(SEED)
    journal=new_journal("sarah")
    try:
        reflection_text=revision_model(
            messages_for(kind="revision",agent="sarah",profile=profile,
                         private_state=state,journal=journal,public_history=HISTORY),
            MAX_SECONDS_PER_CALL)
    except Exception:
        reflection_text=None
    revision=accept_private_revision(
        owner="sarah",cycle=19001,private_state=state,journal=journal,
        public_history=HISTORY,response=reflection_text)
    if revision["ok"]:
        state=revision["private_state"]
    ids=authenticated_reflection_ids(owner="sarah",private_state=state)

    # **No fresh public history**, no pre-seeded goal, no externally supplied
    # next conversation, and no forced model-generated statement.
    outcome=propose_inner_goal(
        owner="sarah",cycle=19002,profile=profile,
        private_state=state,journal=journal,model_request=goal_model)
    if outcome["ok"]:
        journal=outcome["journal"]

    speech={"valid":False,"speaks":False,"no_new_public_input":True}
    if active_goals(journal,owner="sarah"):
        try:
            raw=speech_model(
                build_request(agent="sarah",profile=profile,
                              private_state=state,journal=journal,
                              public_history=[]),MAX_SECONDS_PER_CALL)
        except Exception:
            raw=None
        attempt=parse(
            agent="sarah",cycle=19003,raw=raw,
            journal=journal,private_state=state,
            public_history=[],consumed_ids=set())
        speech={"valid":attempt["ok"],
                "speaks":bool(attempt["utterance"]),
                "no_new_public_input":True,
                "synthetic_utterance":attempt["utterance"][:240] if attempt["ok"] else None}

    return {
        "experiment":"room_real3b_endogenous_idle_memory",
        "model":"Llama-3.2-3B-Instruct",
        "mode":"research_synthetic_no_new_input",
        "private_revision":{"valid":revision["ok"],"changed":revision["changed"],
                            "authenticated_owner_memory":bool(ids)},
        "idle_goal":{"eligible":outcome["eligible"],"valid":outcome["ok"],
                     "changed":outcome["changed"],"reason":outcome["reason"],
                     "model_calls":outcome["calls"]},
        "later_self_initiated_speech":speech,
        "summary":{
            "authored_reflection_to_self_goal":bool(
                revision["changed"] and ids and outcome["changed"]),
            "self_goal_allows_unprompted_speech":speech["speaks"],
            "proof_of_subjective_desire":False,
            "ready_for_live":False},
        "published_live_dialogue":False,
        "modified_live_room":False,
        "wrote_live_memory":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model-url",required=True)
    p.add_argument("--config",default="room/config.json")
    p.add_argument("--out",default="room-real3b-inner-memory.json")
    args=p.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
    model=local_model_request(endpoint=args.model_url,max_tokens=110)
    result=evaluate(cfg,model,model,model)
    Path(args.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
