#!/usr/bin/env python3
"""Real local 3B self-originated goal/belief and downstream speech experiment.

All events, private states and initial beliefs here are synthetic. Real model
is used to choose optional personal goal, optional belief change, and speech.
No public Room message or production memory is ever modified.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from room_endogenous_private_growth import (
    messages_for, accept_private_goal, accept_private_revision,
)
from room_endogenous_speech_option import build_request, parse
from room_endogenous_goal_journal import new_journal, active_goals
from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL

PUBLIC = [
    {"id":"cg-1","speaker":"owen",
     "text":"I had assumed a voltage drop made the projector dim."},
    {"id":"cg-2","speaker":"mara",
     "text":"I checked the power outlet, and the measured voltage remained steady as the projector dimmed."},
    {"id":"cg-3","speaker":"allen",
     "text":"Sarah, what does that observation change about your earlier explanation?"},
]


def evaluate(cfg, private_model, speech_model):
    profile=(cfg.get("p") or {}).get("sarah")
    if not isinstance(profile,dict):
        raise ValueError("missing Room profile")
    state={"what_i_currently_believe":"The projector dimmed because the outlet voltage fell.",
           "belief_confidence":.65,
           "what_just_changed":"A new measurement contradicts my expected voltage drop.",
           "last_updated_cycle":0}
    journal=new_journal("sarah")
    reports={}
    def query(kind, cycle, profile_state, goal_state):
        started=time.monotonic()
        try:
            raw=private_model(messages_for(
                kind=kind,agent="sarah",profile=profile,
                private_state=profile_state,journal=goal_state,
                public_history=PUBLIC),MAX_SECONDS_PER_CALL)
            return raw,round((time.monotonic()-started)*1000)
        except Exception:
            return None,round((time.monotonic()-started)*1000)
    raw_goal,gtime=query("goal",16001,state,journal)
    goal=accept_private_goal(owner="sarah",cycle=16001,
        journal=journal,public_history=PUBLIC,response=raw_goal)
    reports["goal"]={"valid":goal["ok"],"changed":goal["changed"],"latency_ms":gtime,
                     "reason":goal["issue"]}
    if not goal["ok"] and isinstance(raw_goal, str):
        reports["goal"]["synthetic_response_sample"] = raw_goal[:200]
    if goal["ok"]:
        journal=goal["journal"]

    raw_revision,rtime=query("revision",16002,state,journal)
    revision=accept_private_revision(owner="sarah",cycle=16002,
        private_state=state,journal=journal,public_history=PUBLIC,response=raw_revision)
    reports["revision"]={"valid":revision["ok"],"changed":revision["changed"],
                         "latency_ms":rtime,"reason":revision["issue"]}
    if not revision["ok"] and isinstance(raw_revision, str):
        # The entire scenario is synthetic, so a bounded diagnostic cannot
        # expose real Room or visitor information.
        reports["revision"]["synthetic_response_sample"] = raw_revision[:200]
    if revision["ok"]:
        state=revision["private_state"]

    def speech_case(label, beliefs, goals, context, cycle):
        msg=build_request(
            agent="sarah",profile=profile,private_state=beliefs,
            journal=goals,public_history=context)
        before=time.monotonic()
        try:
            raw=speech_model(msg,MAX_SECONDS_PER_CALL)
        except Exception:
            raw=None
        candidate=parse(agent="sarah",cycle=cycle,raw=raw,
                        journal=goals,private_state=beliefs,
                        public_history=context,consumed_ids=set())
        output={"valid":candidate["ok"],"speaks":bool(candidate["utterance"]),
                "latency_ms":round((time.monotonic()-before)*1000)}
        if candidate["utterance"]:
            output["synthetic_public_speech"]=candidate["utterance"][:220]
        return output

    control={"what_i_currently_believe":"The projector dimmed because the outlet voltage fell.",
             "belief_confidence":.65,
             "what_just_changed":"A new measurement contradicts my expected voltage drop.",
             "last_updated_cycle":0}
    reports["before"]=speech_case("before",control,new_journal("sarah"),PUBLIC,16003)
    reports["after"]=speech_case("after",state,journal,PUBLIC,16004)

    if active_goals(journal,owner="sarah"):
        reports["self_initiated_no_new_public_turn"]=speech_case(
            "own-goal",state,journal,[],16005)
    else:
        reports["self_initiated_no_new_public_turn"]={
            "valid":True,"speaks":False,"reason":"no_active_own_goal_no_inference"}
    return {
        "experiment":"room_independent_goal_and_belief_growth_3b",
        "mode":"read_only_synthetic",
        "model":"Llama-3.2-3B-Instruct",
        "conditions":reports,
        "summary":{
            "model_authored_personal_goal":reports["goal"]["changed"],
            "model_authored_private_belief_revision":reports["revision"]["changed"],
            "next_speech_changed_after_private_update":(
                bool(reports["goal"]["changed"] or reports["revision"]["changed"])
                and reports["before"].get("synthetic_public_speech") !=
                reports["after"].get("synthetic_public_speech")),
            "self_derived_goal_can_initiate_without_new_public_input":
                reports["self_initiated_no_new_public_turn"]["speaks"],
            "ready_for_live":False,
        },
        "published_dialogue":False,"wrote_live_memory":False,
        "changed_live_runner":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model-url",required=True)
    p.add_argument("--config",default="room/config.json")
    p.add_argument("--out",default="room-private-growth-3b.json")
    args=p.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
    res=evaluate(
        cfg,local_model_request(endpoint=args.model_url,max_tokens=110),
        local_model_request(endpoint=args.model_url,max_tokens=140))
    Path(args.out).write_text(json.dumps(res,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(res,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
