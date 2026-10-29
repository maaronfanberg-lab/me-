#!/usr/bin/env python3
"""Executable affordances versus passive conversation: isolated 1B/3B ablation.

The Room's participants are *not* involved. Four fictional test speakers
investigate a simulated greenhouse. The world changes only via recognized
utterance-initiated checks and repairs; the model writes every spoken word.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

PEOPLE=("sarah","jules","owen","mara")
ROLES={
    "sarah":"an evidence-oriented scientist",
    "mara":"an attentive anthropologist",
    "owen":"a skeptical mechanical engineer",
    "jules":"a practical naturalist",
}
# All four record the same world, but each has a different initial observation.
WITNESSED={
    "sarah":"The west-window thermometer fell from 24 C to 16 C in ten minutes.",
    "mara":"The greenhouse east door was left open before the plants wilted.",
    "owen":"The heater breaker has a red warning light.",
    "jules":"There is a wet footprint near the potting bench.",
}
CHECKS={
    "thermometer":"A verified reading shows 16 C at 09:20 and 24 C at 09:10.",
    "door":"The east door is propped open and cold outdoor air is entering.",
    "breaker":"The heater breaker is tripped, cutting power to the heater.",
    "soil":"The seedlings' soil moisture is within the expected range, not flooded.",
    "footprint":"The wet shoe print goes from the potting bench toward the west window.",
}
REPAIR_EFFECTS={
    "door":"Mara closed the open east door. The cold airflow immediately lessened.",
    "breaker":"The breaker reset successfully; the heater started warming the air.",
}
OBJECT_ALIASES={
    "thermometer":r"\b(?:thermometer|temperature\s+(?:gauge|sensor|reading))\b",
    "door":r"\b(?:east\s+door|door|ventilation)\b",
    "breaker":r"\b(?:breaker|heater|electrical\s+circuit)\b",
    "soil":r"\b(?:soil|moisture|irrigation)\b",
    "footprint":r"\b(?:footprint|shoe\s+print|potting\s+bench)\b",
}
ACTIVATORS=re.compile(r"\b(?:check|inspect|look at|measure|test|examine|read|investigate|verify|take a look)\b",re.I)
FIXERS=re.compile(r"\b(?:close|shut|reset|repair|fix)\b",re.I)
NEGATION=re.compile(r"\b(?:don't|do not|shouldn't|cannot|can't)\s+(?:check|inspect|look|close|reset|repair)\b",re.I)

@dataclass
class World:
    record:list[dict]=field(default_factory=list)
    checked:set[str]=field(default_factory=set)
    repaired:set[str]=field(default_factory=set)
    step:int=0
    def enact(self,speaker:str,utterance:str)->dict|None:
        text=str(utterance or "")
        if NEGATION.search(text):
            return None
        action=None
        if FIXERS.search(text):
            targets=[name for name in ("door","breaker") if re.search(OBJECT_ALIASES[name],text,re.I)]
            action=("repair",targets[0]) if targets else None
        if action is None and ACTIVATORS.search(text):
            targets=[name for name,regex in OBJECT_ALIASES.items() if re.search(regex,text,re.I)]
            action=("inspect",targets[0]) if targets else None
        if action is None:
            return None
        kind,target=action
        if kind=="inspect":
            if target in self.checked:
                detail=f"The {target} was already inspected; the recorded finding remains unchanged."
            else:
                self.checked.add(target)
                detail=CHECKS[target]
        elif target not in self.checked:
            detail=f"Repair of {target} cannot be confirmed before an inspection."
        elif target in self.repaired:
            detail=f"The {target} repair has already been completed."
        else:
            self.repaired.add(target)
            detail=REPAIR_EFFECTS[target]
        event={"actor":speaker,"action":kind,"target":target,
               "detail":detail,"world_step":self.step}
        self.record.append(event)
        return event
    def observe(self,speaker:str)->str:
        recent=self.record[-4:]
        history="\n".join(
            f"After {r['actor'].capitalize()} {r['action']}ed {r['target']}: {r['detail']}"
            for r in recent
        )
        return (f"Your observation: {WITNESSED[speaker]}\n"
                "Verified shared-world findings from performed operations:\n"
                +(history if history else "(None yet.)")
                +"\nAlready inspected: "+(", ".join(sorted(self.checked)) or "(none)")
                +"\nCompleted repairs: "+(", ".join(sorted(self.repaired)) or "(none)"))

def prompt(speaker:str,spoken:list[dict],world:World|None)->list[dict]:
    system=(
        f"You are {speaker.capitalize()}, {ROLES[speaker]}. "
        "This is a fictional greenhouse simulation. Speak as yourself. "
        "Do not invent witnessed measurements, repairs, or previous conversations. "
        "Make your own choices and react to what others actually say. "
        "One or two plain spoken sentences, not stage directions. "
        "You can offer a concrete inspection or repair and the environment "
        "may provide an independently computed outcome. "
        "When someone asks something, respond if you know; otherwise ask."
    )
    if world is None:
        evidence="Your witnessed information: "+WITNESSED[speaker]
    else:
        evidence=world.observe(speaker)
    context="\n".join(
        f"{turn['speaker'].capitalize()}: {turn['text'][:280]}"
        for turn in spoken[-6:]
    )
    user=(
        "Situation: Four colleagues are investigating sudden seedling wilt.\n"
        + evidence +"\nRecent publicly spoken turns:\n"
        +(context if context else "(No one has spoken yet.)")
        +f"\nWhat does {speaker.capitalize()} say to the others next?"
    )
    return [{"role":"system","content":system},{"role":"user","content":user}]

def speak(url:str,model:str,who:str,spoken:list[dict],world:World|None,index:int)->str|None:
    messages=prompt(who,spoken,world)
    seed=int(hashlib.sha256(f"causal-world-seed:{index}:{who}".encode()).hexdigest()[:8],16)
    body={"model":model,"messages":messages,"temperature":0.68,
          "top_p":0.9,"max_tokens":110,"stream":False,"seed":seed}
    req=urllib.request.Request(url.rstrip("/")+"/v1/chat/completions",
            data=json.dumps(body).encode(),headers={"Content-Type":"application/json"},
            method="POST")
    with urllib.request.urlopen(req,timeout=50) as response:
        result=json.loads(response.read())
    text=str(((result.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not text or text.upper()=="SILENCE":
        return None
    prefix=re.match(r"^(Sarah|Mara|Owen|Jules):\s*",text,re.I)
    if prefix:
        if prefix.group(1).lower()!=who:
            return None
        text=text[prefix.end():].strip()
    if len(text)>700 or re.search(r"\n\s*(?:Sarah|Mara|Owen|Jules):",text,re.I):
        return None
    return text

def evaluate(talk:list[dict],world:World|None)->dict:
    norm=[set(re.findall(r"[a-z]{5,}",x["text"].lower())) for x in talk]
    duplicate=sum(
        len(a & b)/max(1,len(a|b))>.67
        for a,b in zip(norm,norm[1:])
    )
    realized=world.record if world else []
    distinct=[(e["action"],e["target"]) for e in realized]
    return {
        "utterances":len(talk),
        "distinct_speakers":len({r["speaker"] for r in talk}),
        "questions":sum("?" in x["text"] for x in talk),
        "near_duplicated_adjacent":duplicate,
        "world_actions":len(realized),
        "distinct_world_actions":len(set(distinct)),
        "distinct_inspections":len(world.checked) if world else 0,
        "repairs_confirmed":len(world.repaired) if world else 0,
        "invented_actions_claims":sum(bool(re.search(
            r"\b(?:i\s+checked|i\s+measured|i\s+found|i\s+repaired)\b",
            x["text"],re.I)) for x in talk),
    }

def run(url:str,model:str,turns:int,causal:bool)->dict:
    world=World() if causal else None
    spoken=[]
    failures=[]
    for i in range(turns):
        who=PEOPLE[(i*3+i//4)%4]
        if world:
            world.step=i
        try:
            utterance=speak(url,model,who,spoken,world,i)
        except Exception as exc:
            failures.append({"turn":i,"type":type(exc).__name__})
            continue
        if utterance:
            spoken.append({"index":i,"speaker":who,"text":utterance})
            if world:
                world.enact(who,utterance)
    return {"mode":"causal" if causal else "passive",
            "metrics":evaluate(spoken,world),
            "utterances":spoken,"world_log":world.record if world else [],
            "model_errors":failures}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--url",default="http://127.0.0.1:18080")
    p.add_argument("--model",default="Llama-3.2-1B-Instruct")
    p.add_argument("--turns",type=int,default=16)
    p.add_argument("--out",default="causal-world-result.json")
    args=p.parse_args()
    if not 1<=args.turns<=100:
        p.error("turns must be 1..100")
    cases=[run(args.url,args.model,args.turns,x) for x in (False,True)]
    Path(args.out).write_text(json.dumps({"protocol":"causal_world_vs_passive_v1",
        "isolated":True,"cases":cases},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps([{"mode":x["mode"],**x["metrics"],"errors":len(x["model_errors"])}
       for x in cases],indent=2))

if __name__=="__main__":
    main()
