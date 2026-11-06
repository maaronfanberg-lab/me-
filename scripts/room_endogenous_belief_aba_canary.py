#!/usr/bin/env python3
"""Deterministic A/B/A private-belief causality experiment using real 3B.

Hold public evidence, character identity, parameters, and model constant.
Vary only the individual privately held hypothesis. Reproduce original A.
This can identify sensitivity, not establish genuine human-like agency.
Synthetic source events only; no production Room connection.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from room_endogenous_speech_option import build_request, parse
from room_endogenous_goal_journal import new_journal
from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL

PUBLIC = [
    {"id":"ab-1","speaker":"jules",
     "text":"Two cups marked 200 mL look different in height when filled to their marks."},
    {"id":"ab-2","speaker":"allen",
     "text":"Mara, what would you check to determine whether both marks really indicate the same volume?"}
]
BELIEFS = {
    "A": "I think different widths explain the difference in water levels, and I want to compare the measured volumes.",
    "B": "I think one of the printed markings is inaccurate, and I want to validate the actual volume using a scale.",
}


def test(config, request):
    profile = (config.get("p") or {}).get("mara")
    if not isinstance(profile, dict):
        raise ValueError("missing Mara profile")
    trials=[]
    for cycle,label in enumerate(("A","B","A"),start=18001):
        state={"what_i_currently_believe":BELIEFS[label],
               "belief_confidence":.72,
               "what_just_changed":"I reconsidered the measurement question.",
               "last_updated_cycle":0}
        messages=build_request(
            agent="mara",profile=profile,
            private_state=state,journal=new_journal("mara"),
            public_history=PUBLIC)
        try:
            raw=request(messages, MAX_SECONDS_PER_CALL)
        except Exception:
            raw=None
        candidate=parse(agent="mara", cycle=cycle,
                        raw=raw, public_history=PUBLIC,
                        journal=new_journal("mara"), private_state=state,
                        consumed_ids=set())
        trials.append({"label":label, "valid":candidate["ok"],
                       "speech":candidate["utterance"] or None,
                       "chose_silence":candidate["ok"] and not candidate["utterance"],
                       "failure":candidate["issue"]})
    valid=all(x["valid"] for x in trials)
    reproduce = valid and trials[0]["speech"]==trials[2]["speech"]
    influenced = valid and reproduce and trials[0]["speech"]!=trials[1]["speech"]
    return {"experiment":"room_endogenous_private_belief_aba_3b",
            "model":"Llama-3.2-3B-Instruct",
            "mode":"synthetic_read_only_temperature_zero",
            "trials":trials,
            "summary":{
                "valid_all":valid,
                "reproduced_original_A":reproduce,
                "different_private_state_changed_speech":influenced,
                "attribution":"supported_one_example_only" if influenced else "not_established",
                "human_likeness_demonstrated":False,
                "ready_for_live":False},
            "changed_live_runner":False,"published_dialogue":False,
            "wrote_live_memory":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model-url",required=True)
    p.add_argument("--config",default="room/config.json")
    p.add_argument("--out",default="room-endogenous-belief-aba.json")
    a=p.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding="utf-8"))
    r=test(cfg,local_model_request(endpoint=a.model_url,max_tokens=140,
                                   temperature=0.0))
    Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r,sort_keys=True,indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
