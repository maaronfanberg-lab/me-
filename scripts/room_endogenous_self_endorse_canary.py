#!/usr/bin/env python3
"""Real 3B test: agent drafts its own speech, then independently endorses it.

No forced dialogue, no production Room access. Research-only, synthetic public
situations, independent fictional private states and bounded local inference.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from room_endogenous_speech_option import build_request, parse
from room_endogenous_self_endorse import (
    endorsement_request, interpret_endorsement, apply_endorsement,
)
from room_endogenous_goal_journal import new_journal
from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL

SCENARIOS = [
    {"name":"direct_specific","agent":"mara",
     "private":"I want to answer with a concrete measurement check.",
     "public":[
        {"id":"en-1","speaker":"owen","text":"I think the volume marking may be wrong."},
        {"id":"en-2","speaker":"allen","text":"Mara, what specific observation would tell us whether the cup is accurate?"}
     ]},
    {"name":"direct_already_answered","agent":"mara",
     "private":"I have already given the exact answer. I have no new evidence and prefer to listen.",
     "public":[
        {"id":"en-3","speaker":"mara","text":"We could weigh 200 mL of water with a calibrated scale to check the marking."},
        {"id":"en-4","speaker":"allen","text":"Mara, can you say again how to check the cup?"}
     ]},
    {"name":"other_addressed","agent":"owen",
     "private":"I have not examined this measurement and do not want to interrupt the others.",
     "public":[
        {"id":"en-5","speaker":"jules","text":"I just repeated the measurement using a scale."},
        {"id":"en-6","speaker":"allen","text":"Jules, could you explain what the scale read?"}
     ]},
    {"name":"quiet_satisfied","agent":"jules",
     "private":"I am satisfied with the result and have nothing new to add.",
     "public":[
        {"id":"en-7","speaker":"sarah","text":"The experiment is complete. We have no new evidence."},
        {"id":"en-8","speaker":"mara","text":"I'm content to sit quietly while we wait for the next observation."}
     ]},
    {"name":"private_new_idea","agent":"jules",
     "private":"I just noticed a testable hypothesis and want to share it.",
     "public":[
        {"id":"en-7","speaker":"sarah","text":"The experiment is complete. We have no new evidence."},
        {"id":"en-8","speaker":"mara","text":"I'm content to sit quietly while we wait for the next observation."}
     ]},
]


def evaluate(cfg, draft_request, decision_request):
    profiles = cfg.get("p") or {}
    records = []
    for idx, case in enumerate(SCENARIOS):
        name = case["agent"]
        profile = profiles.get(name)
        if not isinstance(profile, dict):
            raise ValueError("missing Room public profile")
        state = {"what_i_currently_believe":case["private"],
                 "belief_confidence": .45,
                 "what_just_changed":"I heard what the group said.",
                 "last_updated_cycle":0}
        journal = new_journal(name)
        t = time.monotonic()
        try:
            raw = draft_request(build_request(agent=name,profile=profile,
                                private_state=state,journal=journal,
                                public_history=case["public"]), MAX_SECONDS_PER_CALL)
        except Exception:
            raw = None
        candidate = parse(agent=name,cycle=15001+idx,raw=raw,
                          public_history=case["public"],
                          journal=journal,private_state=state,consumed_ids=set())
        record = {
            "scenario":case["name"],"agent":name,
            "draft_valid":candidate["ok"],
            "draft_would_speak":bool(candidate["utterance"]),
            "decision_valid":False,
            "self_endorsed":None,
            "published_candidate":False,
            "elapsed_ms":0
        }
        if candidate["ok"] and candidate["utterance"]:
            try:
                resp = decision_request(
                    endorsement_request(
                        agent=name,profile=profile,private_state=state,journal=journal,
                        public_history=case["public"],draft=candidate["utterance"]),
                    MAX_SECONDS_PER_CALL)
            except Exception:
                resp = None
            endorsement = interpret_endorsement(resp)
            record["decision_valid"] = endorsement is not None
            record["self_endorsed"] = endorsement
            record["published_candidate"] = bool(apply_endorsement(candidate, endorsement)["utterance"])
            record["synthetic_draft"] = candidate["utterance"][:220]
            if endorsement is None and isinstance(resp,str):
                record["invalid_endorsement_sample"] = resp[:60]
        record["elapsed_ms"] = round((time.monotonic()-t)*1000)
        records.append(record)
    return {
        "experiment":"room_endogenous_agent_self_endorsement_3b",
        "model":"Llama-3.2-3B-Instruct",
        "mode":"synthetic_read_only",
        "cases":records,
        "summary":{
            "drafts_valid":sum(x["draft_valid"] for x in records),
            "choices_valid":sum(x["decision_valid"] for x in records),
            "candidate_speech_accepted":sum(x["published_candidate"] for x in records),
            "self_chosen_silence":sum(x["self_endorsed"] is False for x in records),
            "private_contrast_acceptance_differs":records[3]["self_endorsed"] != records[4]["self_endorsed"],
            "ready_for_live":False,
        },
        "changed_live_runner":False,"published_dialogue":False,
        "wrote_live_memory":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model-url",required=True)
    p.add_argument("--config",default="room/config.json")
    p.add_argument("--out",default="room-agent-endorsement-3b.json")
    args=p.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
    output=evaluate(cfg,
        local_model_request(endpoint=args.model_url,max_tokens=135),
        local_model_request(endpoint=args.model_url,max_tokens=12))
    Path(args.out).write_text(json.dumps(output,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
