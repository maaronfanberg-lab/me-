#!/usr/bin/env python3
"""Real local-model + real Room preflight A/B, strictly shadow-only."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import room_chat_speech as chat
from room_conversational_candidate import validate_candidate
from room_conversational_floor import NODE,choose_next

NAMES=("sarah","mara","owen","jules")
PHRASES=(
    ("What if species didn't change into one shape", "owen"),
    ("What about an experiment on how the local forest ecosystem responds", "mara"),
    ("I think that I'm not going to get what I want", "sarah"),
    ("It was actually a mistake that my latest hypothesis", "jules"),
)


def source(history, phrase):
    for x in reversed(history):
        if x.get("id") and x.get("speaker") in NAMES and phrase.casefold() in str(x.get("text") or "").casefold():
            return {"id":x["id"],"speaker":x["speaker"],"text":str(x["text"])}
    raise RuntimeError("Public source not found: "+phrase)


def generate(history, speaker, cfg, key):
    os.environ["ROOM_CYCLE_KEY"]=key
    psych=((cfg.get("p") or {}).get(speaker) or {}).get("psychology_v2") or {}
    profile=(cfg.get("p") or {}).get(speaker) or {}
    payload={"entity":speaker,"profile":profile,
             "event":history[-1],"context":history[-3:],
             "private_self_state":{"who_i_am":str(psych.get("core_identity") or ""),
                                   "what_i_want":"Contribute to what matters."},
             "partner":history[-1]["speaker"],"topic":{},"relationship":{},
             "room_presence":{"present":[*NAMES,"allen"],"absent":[]}}
    out=chat.run(payload,timeout=60)
    if not out:
        return {"valid":False,"error":"no_candidate"}
    part={"entity":speaker,"node":NODE[speaker],"role":"expression",
          "private":{"intent":{"readiness":.8},"expression":out}}
    try:
        validated=validate_candidate(part,speaker,history,{})
        return {"valid":True,"utterance":validated,"expression":out}
    except (RuntimeError,ValueError) as exc:
        return {"valid":False,"utterance":out.get("utterance"),
                "expression":out,"error":str(exc)[:180]}


def main():
    if not os.environ.get("ROOM_MODEL_URL"):
        raise RuntimeError("A real local model is required")
    os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
    past=json.loads((ROOT/"room/conversation.json").read_text())
    config=json.loads((ROOT/"room/config.json").read_text())
    cases=[]
    for i,(phrase,person) in enumerate(PHRASES):
        source_msg=source(past,phrase)
        generated=generate([source_msg],person,config,f"adapter-shadow-case:{i}:{person}")
        cases.append({"source":source_msg,"speaker":person,"result":generated})
        print(f"CASE {i+1}/4 {source_msg['speaker']}->{person}: {generated}",flush=True)
    chain=[cases[0]["source"]]
    failures=[]
    for i in range(6):
        selected=choose_next(chain,{"recurrent":{}},{"p":config.get("p") or {}},
                    {"entities":{p:{"people":{}} for p in NAMES}})
        person=selected["speaker"]
        generated=generate(chain,person,config,f"adapter-shadow-chain:{i}:{person}")
        if not generated.get("valid"):
            failures.append({"step":i,"speaker":person,"response":generated})
            print("CHAIN FAILED",failures[-1],flush=True)
            break
        chain.append({"id":f"shadow-adapter-{i}","speaker":person,
                      "text":generated["utterance"]})
        print("CHAIN",i+1,person,generated["utterance"],flush=True)
    summary={"valid_cases":sum(bool(x["result"].get("valid")) for x in cases),
             "chain_turns":len(chain)-1,
             "failures":len(failures),
             "backend":"native_chat_v1",
             "publication":"shadow-only"}
    out={"summary":summary,"cases":cases,"chain":chain,"chain_failures":failures,
         "limitations":"Production preflight passed ≠ natural dialogue; manually inspect consecutive acts and unsupported claims."}
    report=ROOT/"docs/research/room-chat-speech-integrity-20261029.json"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    print("SUMMARY",json.dumps(summary),flush=True)
    if summary["valid_cases"]<3 or summary["chain_turns"]<4:
        raise SystemExit("Native speech adapter has insufficient publication-safe examples")

if __name__=="__main__":main()
