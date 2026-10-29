#!/usr/bin/env python3
"""Isolated model comparison using the real Room speech adapter prompt."""
import argparse,hashlib,json,re,sys,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from room_chat_speech import messages
people=("sarah","mara","jules","owen")
roles={
"sarah":"A thoughtful scientist who enjoys precise questions.",
"mara":"A practical anthropologist attentive to human decisions.",
"jules":"A naturalist who notices small concrete details.",
"owen":"A skeptical engineer who prefers testable explanations."}
meta=re.compile(r"conversat|dialogue|interact|communication|patterns?|feedback|weav|tapestry|emergen",re.I)
seed=[
{"speaker":"jules","text":"Our exchanges seem like an endless tapestry of patterns.","id":"fixture-1"},
{"speaker":"mara","text":"That's interesting. Every conversation is a web of interpretations.","id":"fixture-2"},
{"speaker":"sarah","text":"Perhaps our interactions form a self-referential feedback loop.","id":"fixture-3"}]
def run(model,url,n):
 h=list(seed); errors=[]
 for i in range(n):
  who=people[(i*3+i//4)%4]
  inp={"profile":{"psychology_v2":{"core_identity":roles[who],"motives":["Curiosity about concrete matters."]}},
       "event":h[-1],"context":h[-3:],
       "room_presence":{"present":[*people,"allen"],"absent":[]}}
  payload={"model":model,"messages":messages(inp,who),"temperature":0.73,
           "top_p":0.9,"max_tokens":110,"stream":False,
           "seed":int(hashlib.sha256(f"room-model-test:{i}:{who}".encode()).hexdigest()[:8],16)}
  req=urllib.request.Request(url.rstrip("/")+"/v1/chat/completions",
      data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
  try:
   with urllib.request.urlopen(req,timeout=70) as response:
    obj=json.loads(response.read())
   said=str(((obj.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
  except Exception as exc:
   errors.append(type(exc).__name__);continue
  if not said or len(said)>600 or said.upper()=="SILENCE":continue
  match=re.match(r'^(Sarah|Mara|Jules|Owen|Allen):\s*',said,re.I)
  if match:
   if match.group(1).lower()!=who:continue
   said=said[match.end():].strip()
  if re.search(r"\n\s*(Sarah|Mara|Jules|Owen|Allen):",said,re.I):continue
  h.append({"speaker":who,"text":said,"id":f"model-{i}"})
 turns=h[3:]
 return {"model":model,"metrics":{"actual":len(turns),"meta_related":sum(bool(meta.search(t["text"])) for t in turns),
 "questions":sum("?" in t["text"] for t in turns),"errors":errors},
 "seed":seed,"speech":turns}
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--model",required=True);p.add_argument("--url",default="http://127.0.0.1:18080")
 p.add_argument("--turns",type=int,default=16);p.add_argument("--out",required=True)
 a=p.parse_args()
 result=run(a.model,a.url,a.turns)
 Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result["metrics"]))
