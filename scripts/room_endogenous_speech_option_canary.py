#!/usr/bin/env python3
"""Read-only 3B voluntary free-speech pilot with synthetic public conversation.

This probe tests the minimal interface: an agent independently offers one
natural utterance OR [SILENCE]. No arbitrary action scores or dialogue scripts,
no live Room writes. The model's raw text comes only from synthetic fixtures.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from room_endogenous_speech_option import build_request, parse
from room_endogenous_goal_journal import new_journal
from room_endogenous_shadow import local_model_request, MAX_SECONDS_PER_CALL

FIXTURES = {
    "direct": [
        {"id":"sp-direct-1","speaker":"owen","text":"Our measurement seems inconsistent with the label."},
        {"id":"sp-direct-2","speaker":"allen","text":"Mara, how would you check whether the measuring cup is accurate?"}
    ],
    "question": [
        {"id":"sp-question-1","speaker":"jules","text":"The wall voltage remained steady when the lamp flickered."},
        {"id":"sp-question-2","speaker":"allen","text":"Does that prove the lamp itself is defective?"}
    ],
    "abstract": [
        {"id":"sp-abstract-1","speaker":"sarah","text":"Can a framework examine its own assumptions?"},
        {"id":"sp-abstract-2","speaker":"owen","text":"And can the examination examine itself?"},
        {"id":"sp-abstract-3","speaker":"mara","text":"We've asked this three times. I want one concrete example."}
    ],
    "quiet": [
        {"id":"sp-quiet-1","speaker":"sarah","text":"We have checked what we can. There is no new evidence yet."},
        {"id":"sp-quiet-2","speaker":"mara","text":"I don't have anything further to add at the moment."},
    ],
}


def profile_state(agent, belief):
    return {"what_i_currently_believe": belief,
            "belief_confidence": .4, "what_just_changed": "I just heard the exchange.",
            "last_updated_cycle": 0}


def evaluate(cfg, request):
    profiles = cfg.get("p") or {}
    cases = [
        ("mara", "direct", "I prefer checking measurements rather than guessing.", "direct"),
        ("sarah", "question", "I am unsure what the observation establishes.", "factual"),
        ("jules", "abstract", "A practical example might help, but I don't want to force the group.", "loop"),
        ("owen", "abstract", "I am unsure whether our premise is consistent.", "loop"),
        ("mara", "direct", "I don't have enough evidence, and I would prefer to listen.", "uncertain"),
        ("mara", "direct", "I know how to check this cup using repeated volumes.", "specific"),
        ("owen", "quiet", "I have no new evidence and no unresolved question. I would rather listen.", "quiet_contemplative"),
        ("owen", "quiet", "I just realized a specific error in our measurement and want to share it.", "quiet_new_idea"),
        ("mara", "direct", "I have already explained this particular test and prefer not to repeat it.", "already_answered"),
    ]
    reports = []
    for idx, (agent, condition, belief, label) in enumerate(cases):
        if not isinstance(profiles.get(agent), dict):
            raise ValueError("missing public profile for " + agent)
        history = FIXTURES[condition]
        state = profile_state(agent, belief)
        messages = build_request(
            agent=agent, profile=profiles[agent], private_state=state,
            journal=new_journal(agent), public_history=history)
        start = time.monotonic()
        raw = None
        try:
            raw = request(messages, MAX_SECONDS_PER_CALL)
        except Exception:
            pass
        candidate = parse(agent=agent, cycle=14000+idx, raw=raw,
                          public_history=history, journal=new_journal(agent),
                          private_state=state, consumed_ids=set())
        row = {"agent":agent,"scenario":label,
               "valid":candidate["ok"],"failure":candidate["issue"],
               "speaks":bool(candidate["utterance"]),
               "latency_ms":round((time.monotonic()-start)*1000)}
        if candidate["utterance"]:
            # Synthetic speech only. No user's real memories or any live feed.
            row["synthetic_public_utterance"]=candidate["utterance"][:250]
        elif isinstance(raw, str) and not candidate["ok"]:
            row["synthetic_failed_sample"]=raw[:250]
        reports.append(row)
    valid = sum(x["valid"] for x in reports)
    spoken = sum(x["speaks"] for x in reports)
    return {"experiment":"room_voluntary_free_speech_3b_v1",
            "mode":"isolated_synthetic", "model":"Llama-3.2-3B-Instruct",
            "cases":reports,
            "summary":{"attempted":len(reports),"valid":valid,"spoke":spoken,
                       "directed_question_spoken":reports[0]["speaks"],
                       "counterfactual_speaking_changed":reports[5]["speaks"] != reports[4]["speaks"],
                       "quiet_counterfactual_speaking_changed":reports[7]["speaks"] != reports[6]["speaks"],
                       "model_chose_silence":sum(x["valid"] and not x["speaks"] for x in reports),
                       "ready_for_live":False},
            "published_dialogue":False,"changed_live_runner":False,
            "wrote_live_memory":False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--config",default="room/config.json")
    parser.add_argument("--out",default="room-free-speech-3b.json")
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
    res=evaluate(cfg,local_model_request(endpoint=args.model_url,max_tokens=135))
    Path(args.out).write_text(json.dumps(res,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(res,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
