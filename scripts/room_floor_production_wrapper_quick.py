#!/usr/bin/env python3
"""Short A/B through the actual Room Llama model wrapper, never publishing speech."""
from __future__ import annotations
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import room_engine_v5 as engine
from room_conversational_floor import choose_next
from room_floor_model_shadow import diagnostic,sample_sources,simple_profile
from room_conversation_evidence import analyze
NAMES=("sarah","mara","owen","jules")


def produce(history,speaker,profile,self_state,mode,seed):
    source=history[-1]
    os.environ["ROOM_CYCLE_KEY"]=f"quick-production-wrapper:{seed}:{speaker}"
    os.environ["ROOM_FLOOR_REASON"]="open_floor_uptake" if mode=="retained" else ""
    os.environ["ROOM_FLOOR_SOURCE_ID"]=str(source["id"])
    os.environ["ROOM_FLOOR_SPEAKER"]=speaker
    payload={"entity":speaker,"profile":profile,"private_self_state":self_state,
             "event":source,"context":list(history[-3:]),"topic":{},"keywords":[],
             "relationship":{},"partner":source.get("speaker"),"mandatory_speech":True}
    try:
        result=engine._llama_model_run("expression",payload,timeout=45)
        if not isinstance(result,dict):
            return {"text":"","error":"quarantined"}
        return {"text":str(result.get("utterance") or "").strip(),
                "move":result.get("move"),"target":result.get("target")}
    except Exception as exc:
        return {"text":"","error":type(exc).__name__}


def main():
    if os.environ.get("ROOM_BRAIN_ACTIVE")!="llama3.2-1b":
        raise RuntimeError("must select the production Llama 1B path")
    feed=json.loads((ROOT/"room/feed.json").read_text())
    cfg=json.loads((ROOT/"room/config.json").read_text())
    profiles={name:simple_profile(cfg,name) for name in NAMES}
    sources=sample_sources(feed.get("conversation") or [],count=4)
    if len(sources)!=4:raise RuntimeError("missing test sources")
    pairs=[]
    for i,s in enumerate(sources):
        speaker=[n for n in NAMES if n!=s["speaker"]][i%3]
        a=produce([s],speaker,*profiles[speaker],"baseline",i)
        b=produce([s],speaker,*profiles[speaker],"retained",i)
        pairs.append({"source":s,"speaker":speaker,
                      "baseline":{**a,**diagnostic(s["text"],a["text"])},
                      "retained":{**b,**diagnostic(s["text"],b["text"])}})
        print(f"PAIR {i+1}/4: {a.get('text','')[:80]} | {b.get('text','')[:80]}",flush=True)
    traces={}
    for mode in ("baseline","retained"):
        chain=[dict(sources[0])]
        for step in range(5):
            chosen=choose_next(chain,{"recurrent":{}},{"p":cfg.get("p") or {}},
                 {"entities":{n:{"people":{}} for n in NAMES}})
            speaker=chosen["speaker"]
            out=produce(chain,speaker,*profiles[speaker],mode,100+step)
            if not out.get("text"):break
            chain.append({"id":f"{mode}-{step}","speaker":speaker,"text":out["text"]})
        traces[mode]={"turns":chain,"diagnostics":analyze(chain)}
        print("CHAIN",mode,len(chain),flush=True)
    result={"purpose":"v2 source-action retry A/B using production wrapper, never deployed",
            "model":"llama3.2-1b production wrapper",
            "source_cycle":(feed.get("state") or {}).get("cycle"),
            "pairs":pairs,"chains":traces,
            "limitations":"Small sample and structural metrics; judge semantic responsiveness and multi-turn continuity manually."}
    dst=ROOT/"docs/research/room-floor-quick-model-v2-20261028.json"
    dst.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("COMPLETE",str(dst),flush=True)

if __name__=="__main__":main()
