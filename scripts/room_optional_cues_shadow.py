#!/usr/bin/env python3
"""Offline paired test of *optional* public cues through real Room 1B wrapper.

The test uses public source utterances, the same seed per pair, no hidden
private prompts and no publication. Text must be reviewed by a person.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import room_engine_v5 as engine
from room_conversational_floor import choose_next

NAMES=("sarah","mara","owen","jules")
GENERIC={"the","and","this","that","they","their","with","have","what","when",
         "were","some","something","think","would","could","about","other",
         "really","still","conversation","important","idea","want","maybe"}


def words(x):
    return re.findall(r"[a-z0-9']+",str(x or "").lower())


def salient(x):
    return {w for w in words(x) if len(w)>3 and w not in GENERIC}


def fixtures(feed, count=6):
    picked=[]
    for x in reversed(feed.get("conversation") or []):
        if x.get("speaker") not in NAMES or not x.get("id"):
            continue
        s=str(x.get("text") or "").strip()
        if s.endswith("?") or not (14 <= len(words(s)) <= 65):
            continue
        if any(len(salient(s)&salient(y["text"])) /
               max(1,len(salient(s)|salient(y["text"]))) > .45 for y in picked):
            continue
        picked.append({"speaker":x["speaker"],"id":str(x["id"]),"text":s})
        if len(picked)>=count:
            break
    if len(picked)<count:
        raise RuntimeError(f"Insufficient distinct public turn fixtures: {len(picked)}")
    return picked[::-1]


def generate(history, name, cfg, cue, cycle_key):
    os.environ["ROOM_OPTIONAL_SOURCE_CUES"]="1" if cue else "0"
    os.environ["ROOM_CYCLE_KEY"]=cycle_key
    os.environ["ROOM_FLOOR_REASON"]="open_floor_uptake"
    os.environ["ROOM_FLOOR_SOURCE_ID"]=str(history[-1]["id"])
    os.environ["ROOM_FLOOR_SPEAKER"]=name
    prof=(cfg.get("p") or {}).get(name) or {}
    psych=prof.get("psychology_v2") or {}
    state={"who_i_am":str(psych.get("core_identity") or f"I am {name.capitalize()}."),
           "what_i_want":"Contribute independently and respond to real people."}
    payload={"entity":name,"profile":prof,"private_self_state":state,
             "event":history[-1],"context":history[-3:],
             "topic":{},"keywords":[],"relationship":{},
             "partner":history[-1]["speaker"],"mandatory_speech":True}
    start=time.monotonic()
    try:
        obj=engine._llama_model_run("expression",payload,timeout=55)
        text=str(obj.get("utterance") or "").strip() if isinstance(obj,dict) else ""
        return {"text":text,"move":obj.get("move") if isinstance(obj,dict) else None,
                "target":obj.get("target") if isinstance(obj,dict) else None,
                "seconds":round(time.monotonic()-start,2),
                "failure":None if text else "invalid_expression"}
    except Exception as exc:
        return {"text":"","seconds":round(time.monotonic()-start,2),
                "failure":type(exc).__name__}


def main():
    if os.environ.get("ROOM_BRAIN_ACTIVE")!="llama3.2-1b":
        raise RuntimeError("Production model wrapper must be active")
    feed=json.loads((ROOT/"room/feed.json").read_text())
    cfg=json.loads((ROOT/"room/config.json").read_text())
    sources=fixtures(feed)
    pairs=[]
    for i,source in enumerate(sources):
        peers=[x for x in NAMES if x!=source["speaker"]]
        speaker=peers[i%3]
        seed=f"source-cue-ab:{i}:{speaker}"
        base=generate([source],speaker,cfg,False,seed)
        proposed=generate([source],speaker,cfg,True,seed)
        pairs.append({"source":source,"speaker":speaker,
                      "baseline":base,"optional_cues":proposed})
        print(f"PAIR {i+1}/6 {source['speaker']}->{speaker} "
              f"base={base['text'][:80]!r} cue={proposed['text'][:80]!r}",flush=True)
    chains={}
    for cue,tag in ((False,"baseline"),(True,"optional_cues")):
        history=[sources[0]]
        for i in range(6):
            picked=choose_next(history,{"recurrent":{}},{"p":cfg.get("p") or {}},
                       {"entities":{name:{"people":{}} for name in NAMES}})
            name=picked["speaker"]
            next_reply=generate(history,name,cfg,cue,f"source-cue-chain:{i}:{name}")
            if not next_reply["text"]:
                break
            history.append({"id":f"shadow-{tag}-{i}","speaker":name,
                            "text":next_reply["text"],"elapsed":next_reply["seconds"]})
        chains[tag]=history
        print("CHAIN",tag,len(history)-1,flush=True)
    summary={}
    for tag in ("baseline","optional_cues"):
        outputs=[p[tag] for p in pairs]
        summary[tag]={
            "valid":sum(bool(x["text"]) for x in outputs),
            "whole_source_copies":sum(bool(x["text"]) and
                words(x["text"])==words(p["source"]["text"])
                for x,p in zip(outputs,pairs)),
            "mean_response_words":round(sum(len(words(x["text"])) for x in outputs)/len(outputs),2),
            "chain_turns":len(chains[tag])-1,
        }
    out={
       "kind":"optional-public-cue-1b-shadow-test-not-deployed",
       "source_cycle":(feed.get("state") or {}).get("cycle"),
       "model":"production-Llama-3.2-1B",
       "summary":summary,"pairs":pairs,"chains":chains,
       "limitations":"Small selected public sample; structural metrics do not prove semantic continuity. Review full generated text."
    }
    path=ROOT/"docs/research/room-optional-source-cues-shadow-20261029.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",json.dumps(summary),flush=True)

if __name__=="__main__":
    main()
