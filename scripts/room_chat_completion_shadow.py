#!/usr/bin/env python3
"""Isolated Room 1B chat-template ablation, never alters the live Room."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from room_conversational_floor import choose_next
from room_research_architecture import autonomous_text_issue

NAMES=("sarah","mara","owen","jules")
PHRASES=(
    ("What if species didn't change into one shape", "owen"),
    ("What about an experiment on how the local forest ecosystem responds", "mara"),
    ("I think that I'm not going to get what I want", "sarah"),
    ("It was actually a mistake that my latest hypothesis", "jules"),
)


def source(conversation, phrase):
    for m in reversed(conversation):
        if (m.get("speaker") in NAMES and m.get("id")
            and phrase.casefold() in str(m.get("text") or "").casefold()):
            return {"id":str(m["id"]),"speaker":m["speaker"],
                    "text":str(m["text"])}
    raise RuntimeError("Public source unavailable: "+phrase)


def words(text):
    return re.findall(r"[a-z0-9']+",str(text or "").casefold())


def generate(history, person, cfg, key):
    psych=((cfg.get("p") or {}).get(person) or {}).get("psychology_v2") or {}
    persona=str(psych.get("core_identity") or "A curious and independent participant.")[:300]
    interests=[str(x)[:100] for x in (psych.get("motives") or [])[:2]]
    rules=(
        f"You are {person.capitalize()}, a distinct person in a four-person conversation "
        f"with Sarah, Mara, Jules, and Owen. Identity: {persona}. "
        f"Your personal interests: {'; '.join(interests)}. "
        "Speak directly to the other people, naturally and in your own words. "
        "Respond to what the last person actually meant where useful. "
        "You can agree, disagree, clarify, add a concrete example, or introduce your own relevant idea. "
        "Do not simply repeat their words or invent previous events or relationships. "
        "Your response is one or two complete spoken sentences, not an explanation of your job."
    )
    messages=[{"role":"system","content":rules}]
    conversation="\n".join(
        f"{str(m.get('speaker') or '').capitalize()}: {str(m.get('text') or '')[:520]}"
        for m in history[-3:])
    messages.append({"role":"user","content":
        "Latest public Room turns:\n"+conversation+
        f"\n\nNow speak as {person.capitalize()}. Say only your own next conversational turn."})
    seed=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)
    payload={"model":"Llama-3.2-1B-Instruct","messages":messages,
             "temperature":.78,"top_p":.93,"max_tokens":145,
             "seed":seed,"stream":False}
    req=urllib.request.Request(
        "http://127.0.0.1:18086/v1/chat/completions",
        data=json.dumps(payload,ensure_ascii=False).encode(),
        headers={"Content-Type":"application/json"},method="POST")
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=75) as response:
            obj=json.loads(response.read().decode())
        raw=str(obj["choices"][0]["message"].get("content") or "").strip()
        spoken=re.sub(r"^(?:Sarah|Mara|Owen|Jules):\s*","",raw,flags=re.I)
        issue=autonomous_text_issue({"speaker":person,"text":spoken})
        return {"spoken":spoken,"raw":raw,"quality_issue":issue,
                "seconds":round(time.monotonic()-start,2),
                "word_count":len(words(spoken))}
    except Exception as exc:
        return {"spoken":"","raw":"","error":type(exc).__name__,
                "seconds":round(time.monotonic()-start,2)}


def main():
    cfg=json.loads((ROOT/"room/config.json").read_text())
    conversation=json.loads((ROOT/"room/conversation.json").read_text())
    cases=[]
    for i,(phrase,person) in enumerate(PHRASES):
        src=source(conversation,phrase)
        response=generate([src],person,cfg,f"chat-case:{i}:{person}")
        cases.append({"source":src,"speaker":person,"response":response})
        print(f"CASE {i+1}/4 {src['speaker']}->{person}: {response['spoken'][:240]}",flush=True)
    chain=[cases[0]["source"]]
    for i in range(6):
        selected=choose_next(chain,{"recurrent":{}},{"p":cfg.get("p") or {}},
                         {"entities":{n:{"people":{}} for n in NAMES}})
        person=selected["speaker"]
        produced=generate(chain,person,cfg,f"chat-chain:{i}:{person}")
        if not produced["spoken"]:
            print("CHAIN FAILED",i,produced.get("error"),flush=True)
            break
        chain.append({"id":f"shadow-chat-{i}","speaker":person,"text":produced["spoken"],
                      "issue":produced.get("quality_issue"),"seconds":produced["seconds"]})
        print(f"CHAIN {i+1} {person}: {produced['spoken'][:240]}",flush=True)
    result={"purpose":"direct-chat-completions-vs-existing-1b-structured-wrapper-shadow",
            "source":"public room/conversation.json",
            "model":"production-class Llama-3.2-1B Q4_K_M, chat template",
            "cases":cases,"chain":chain,
            "summary":{"valid_responses":sum(bool(c["response"]["spoken"]) for c in cases),
                       "whole_source_copies":sum(
                           words(c["source"]["text"])==words(c["response"]["spoken"])
                           for c in cases),
                       "generated_chain_turns":len(chain)-1,
                       "model_seconds":round(sum(c["response"]["seconds"] for c in cases)
                                           +sum(x.get("seconds",0) for x in chain),2)},
            "limitations":"Prompt and output format change together, so this is a capacity/prompt viability probe, not a causal isolated format effect; human semantic assessment required.",
            "publication":"none"}
    path=ROOT/"docs/research/room-chat-completions-20261029.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("SUMMARY",json.dumps(result["summary"]),flush=True)

if __name__=="__main__":
    main()
