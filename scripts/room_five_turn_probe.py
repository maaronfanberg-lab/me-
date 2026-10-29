#!/usr/bin/env python3
"""Matched-seed three-turn versus five-turn Room native-chat A/B, shadow-only and publication-safe.

Only witnessed public autonomous dialogue; the output goes to a research
artifact on this experiment branch and never mutates the live Room.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import room_chat_speech as chat
from room_conversational_floor import NODE,choose_next
from room_conversational_candidate import validate_candidate

NAMES=("sarah","mara","owen","jules")
PHRASES=(
    ("You seem to be pondering the concept of", "owen"),
    ("I'm intrigued by your curiosity about hidden patterns", "mara"),
    ("The way mathematical and evolutionary concepts can intersect", "jules"),
    ("Mathematical models can help us grasp", "owen"),
    ("We can apply the principles of fractal geometry", "sarah"),
    ("I'd love to delve into the realm of fungal networks", "mara"),
    ("what if mycelium could be used to create symbiotic", "owen"),
    ("I've been fascinated by the potential for fungal networks", "sarah"),
)


def find_window(messages: list, phrase: str) -> list[dict]:
    for i in range(len(messages)-1,-1,-1):
        item=messages[i]
        if (item.get("speaker") in NAMES and item.get("id")
                and phrase.casefold() in str(item.get("text") or "").casefold()):
            prior=[
                {"id":t["id"],"speaker":t["speaker"],"text":t["text"]}
                for t in messages[max(0,i-4):i+1]
                if isinstance(t,dict) and t.get("speaker") in NAMES
                and t.get("id") and t.get("text")
            ]
            if not prior or prior[-1]["id"]!=item["id"]:
                raise RuntimeError("source provenance missing in window")
            return prior
    raise RuntimeError(f"Witnessed public source not found: {phrase}")


def produce(history:list[dict],person:str,cfg:dict,key:str,variant:str)->dict:
    if variant not in {"three","five"}: raise ValueError("unknown variant")
    os.environ["ROOM_CHAT_ACTION_FOCUS"]="0"
    os.environ["ROOM_CHAT_CONTEXT_WINDOW"]="5" if variant=="five" else "3"
    os.environ["ROOM_CYCLE_KEY"]=key  # identical sampler seed in both arms
    os.environ["ROOM_CONVERSATIONAL_FLOOR"]="1"
    os.environ["ROOM_CHAT_SPEECH_MODE"]="1"
    profile=dict((cfg.get("p") or {}).get(person) or {})
    payload={
        "entity":person,"profile":profile,"event":history[-1],
        "context":history[-5:] if variant=="five" else history[-3:],
        "partner":history[-1]["speaker"],
        "topic":{},"private_self_state":{},
        "room_presence":{"present":[*NAMES,"allen"],"absent":[]},
    }
    started=time.monotonic()
    try:
        result=chat.run(payload,timeout=55)
        elapsed=round(time.monotonic()-started,2)
        if not isinstance(result,dict):
            return {"valid":False,"reason":"all_model_attempts_quarantined",
                    "elapsed_seconds":elapsed}
        part={"entity":person,"node":NODE[person],"role":"expression",
              "private":{"intent":{"readiness":.8},"expression":result}}
        valid=validate_candidate(part,person,history,{})
        return {"valid":True,"utterance":valid,"move":result.get("move"),
                "target":result.get("target"),"elapsed_seconds":elapsed}
    except (RuntimeError,ValueError) as exc:
        return {"valid":False,"reason":type(exc).__name__+":"+str(exc)[:80],
                "elapsed_seconds":round(time.monotonic()-started,2)}


def generate_arm(variant:str,sources:list[tuple],cfg:dict)->dict:
    cases=[]
    for i,(history,person) in enumerate(sources):
        r=produce(history,person,cfg,f"room-next-action:case:{i}:{person}",variant)
        cases.append({
            "source_ids":[t["id"] for t in history],
            "source_turns":history,
            "speaker":person,"result":r,
        })
        print(f"CASE {variant} {i+1}/{len(sources)} valid={r['valid']}"
              f" {str(r.get('utterance') or r.get('reason'))[:180]}",flush=True)

    # Six-turn autonomous continuation, same exact initial three witnessed
    # utterances and same deterministic floor decisions in both branches.
    chain=[dict(x) for x in sources[0][0]]
    failures=[]
    for i in range(6):
        selection=choose_next(chain,{"recurrent":{}},{"p":cfg.get("p") or {}},
                              {"entities":{p:{"people":{}} for p in NAMES}})
        person=selection["speaker"]
        result=produce(chain,person,cfg,f"room-next-action:chain:{i}:{person}",variant)
        if not result["valid"]:
            failures.append({"step":i,"speaker":person,"result":result})
            print(f"CHAIN {variant} step {i+1} rejected",flush=True)
            break
        chain.append({"id":f"shadow-{variant}-{i}",
                      "speaker":person,"text":result["utterance"]})
        print(f"CHAIN {variant} {i+1} {person}: {result['utterance'][:180]}",flush=True)
    return {"cases":cases,"chain":chain,"chain_failures":failures,"summary":{
        "valid_cases":sum(int(c["result"]["valid"]) for c in cases),
        "total_cases":len(cases),"generated_chain_turns":len(chain)-len(sources[0][0]),
        "generation_seconds":round(sum(c["result"]["elapsed_seconds"] for c in cases),2),
    }}


def main():
    if not os.environ.get("ROOM_MODEL_URL") or not os.environ.get("ROOM_CHAT_SPEECH_MODE"):
        raise RuntimeError("real local native Room model required")
    history=json.loads((ROOT/"room/conversation.json").read_text(encoding="utf-8"))
    cfg=json.loads((ROOT/"room/config.json").read_text(encoding="utf-8"))
    sources=[(find_window(history,phrase),speaker) for phrase,speaker in PHRASES]
    results={variant:generate_arm(variant,sources,cfg) for variant in
             ("three","five")}
    artifact={
        "purpose":"Same local model, same source, same sampler seed, public context window 3-vs-5 A/B",
        "backend":"native_chat_v1",
        "deployment":"none",
        "sources_from":"public room/conversation.json at fixed branch revision",
        "results":results,
        "caveats":"No algorithmic metric establishes genuine response. Blindly inspect content, sources and chains, particularly direct answers, new detail, unjustified history, and failed turns.",
    }
    output=ROOT/"docs/research/room-five-turn-shadow-20261029.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(artifact,indent=2,ensure_ascii=False)+"\n",
                      encoding="utf-8")
    print("RESULTS",json.dumps({k:v["summary"] for k,v in results.items()}),flush=True)


if __name__=="__main__":
    main()
