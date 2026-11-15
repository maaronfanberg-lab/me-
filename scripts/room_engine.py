#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,random,re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; ROOM=ROOT/"room"; PARTS=ROOT/"room_parts"; WORK=ROOT/"room_work"
CFG=json.loads((ROOM/"config.json").read_text()); A=CFG["a"]; P=CFG["p"]; BOOT=CFG.get("boot_id","room-default")
VERSION="room-cognition-v4"; ORDER=("sarah","mara","owen","jules"); N={e:P[e]["name"] for e in ORDER}
SEED={e:[{"id":r[0],"text":r[3],"tags":r[4],"sal":r[5],"emo":r[6]} for r in CFG.get("m",{}).get(e,[])] for e in ORDER}
STOP=set("the and but for not was are you your our out too did can got one once that this with from have has had just what when where there they them then than about would could should into only really some more very like because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything current".split())
SPARKS="music food places books movies work home habits humor trust quiet noise nature technology friendship risk routine curiosity sleep time luck change learning attention stories travel games art money".split()

def load(p,d): return json.loads(p.read_text()) if p.exists() else d
def save(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n")
def sd(*x): return int(hashlib.sha256(":".join(map(str,x)).encode()).hexdigest()[:16],16)&0x7fffffff
def rr(*x): return random.Random(sd(*x))
def clamp(x,a=0,b=1): return max(a,min(b,float(x)))
def toks(s):
    out=[]; names={v.lower() for v in N.values()}
    for w in re.findall(r"[a-z][a-z'-]{2,}",str(s or "").lower()):
        w=w.strip("'-")
        if w and w not in STOP and w not in names and w not in out: out.append(w)
    return out

def fresh_minds():
    return {"entities":{e:{"fast":{"activation":.2,"attention":[]},"medium":{"topics":[],"branch_interest":0},"slow":{"social_energy":.55},"noise":{"activation":0,"association":0,"inhibition":0,"social":0},"room_memories":[],"self_history":[],"last_event":None,"spoken":0,"silences":0,"people":{o:{"familiarity":.02,"reports":[]} for o in ORDER if o!=e}} for e in ORDER}}
def fresh_state(): return {"version":VERSION,"boot_id":BOOT,"cycle":0,"silence_cycles":0,"last_speaker":None,"last_run":None,"messages":0,"last_public_event":None,"last_beat_id":None,"beat_contributors":[]}
def init():
    ROOM.mkdir(exist_ok=True); st=load(ROOM/"state.json",{})
    if st.get("boot_id")!=BOOT:
        save(ROOM/"conversation.json",[]); save(ROOM/"discourse.json",{"nodes":[],"roots":[]}); save(ROOM/"cognitive_state.json",fresh_minds()); save(ROOM/"state.json",fresh_state()); return
    if not (ROOM/"conversation.json").exists(): save(ROOM/"conversation.json",[])
    if not (ROOM/"discourse.json").exists(): save(ROOM/"discourse.json",{"nodes":[],"roots":[]})
    if not (ROOM/"cognitive_state.json").exists(): save(ROOM/"cognitive_state.json",fresh_minds())
    if not (ROOM/"state.json").exists(): save(ROOM/"state.json",fresh_state())
init()

def conv(): return load(ROOM/"conversation.json",[])
def msgs(): return [m for m in conv() if str(m.get("runtime","")).startswith("room-cognition-v") and m.get("boot_id",BOOT)==BOOT]
def unit_id(m):
    if not m:return None
    return m.get("beat_id") or ("legacy-"+str(m.get("id","unknown")))
def context():
    m=msgs()
    if not m:return []
    b=unit_id(m[-1]); z=[x for x in m if unit_id(x)==b]
    return (z or m)[-4:]
def event(): c=context(); return c[-1] if c else None
def minds(): return load(ROOM/"cognitive_state.json",fresh_minds())
def tree(): return load(ROOM/"discourse.json",{"nodes":[],"roots":[]})
def state(): return load(ROOM/"state.json",fresh_state())
def trait(e,k,d=.5): return float(P[e]["traits"].get(k,d))
def ni(n): e=ORDER[n//3]; local=n%3; role,tasks=A["roles"][str(local)]; return e,local,role,tasks
def target(m): return ((m or {}).get("cognition") or {}).get("target")
def isq(m): return bool(m and m.get("text","").rstrip().endswith("?"))

def learned(e,M=None):
    M=M or minds(); out=[]
    for x in M["entities"][e].get("self_history",[]):
        if x.get("move") not in {"answer","self_disclosure","new_root"}: continue
        t=str(x.get("text","")).strip()
        if t: out.append({"id":x.get("source"),"text":t.rstrip("."),"tags":toks(t)[:8],"sal":.62,"emo":.35})
    return out[-100:]
def pool(e,M=None): return SEED[e]+learned(e,M)
def mem(e,i,M=None): return next((x for x in pool(e,M) if i and x["id"]==i),None)
def recall(e,cues,key,M=None):
    q=set(cues); p=pool(e,M)
    if p:
        p=sorted(p,key=lambda x:2*len(q&set(x["tags"]))+.5*x["sal"]+.25*x["emo"],reverse=True)
        if q and q&set(p[0]["tags"]): return p[0]
        return rr("recall",e,key).choice(p[:min(6,len(p))])
    tags=rr("spark",e,key).sample(SPARKS,3); return {"id":None,"text":None,"tags":tags,"sal":.4,"emo":.2}
def nz(e,s,key):
    r=rr("noise",e,key); old=s.get("noise",{})
    return {k:round(clamp(.82*float(old.get(k,0))+r.gauss(0,v),-.25,.25),4) for k,v in {"activation":.08,"association":.09,"inhibition":.07,"social":.08}.items()}

def depth(i,T=None):
    T=T or tree(); mp={n["id"]:n for n in T["nodes"]}; seen=set(); d=0
    while i and i in mp and i not in seen and d<20: seen.add(i); d+=1; i=mp[i].get("parent")
    return d
def anchor(m,T=None,M=None):
    if not m:return None,None
    c=m.get("cognition") or {}
    if c.get("move_type")=="question": return None,None
    if c.get("branch_memory"): return c.get("branch_owner"),c.get("branch_memory")
    if c.get("move_type") in {"answer","self_disclosure","new_root"} and c.get("memory_provenance"): return m.get("speaker"),c["memory_provenance"]
    T=T or tree(); M=M or msgs(); mp={n["id"]:n for n in T["nodes"]}; by={x.get("discourse_id"):x for x in M}; i=m.get("discourse_id"); seen=set()
    while i and i in mp and i not in seen:
        seen.add(i); n=mp[i]; h=by.get(i,{}); hc=h.get("cognition") or {}
        if n.get("branch_memory"): return n.get("branch_owner"),n.get("branch_memory")
        if hc.get("branch_memory"): return hc.get("branch_owner"),hc.get("branch_memory")
        i=n.get("parent") or n.get("derived_from")
    return None,None

def sense(n,key):
    e,local,role,tasks=ni(n); C=context(); m=C[-1] if C else None; text=" ".join(x.get("text","") for x in C); M=minds(); s=M["entities"][e]; kw=toks(text)[:12]; rc=recall(e,kw,key,M); z=nz(e,s,key); r=rr("sense",key,n); bo,bm=anchor(m)
    if role=="comprehension":
        work={tasks[0]:[{"concept":w,"activation":round(.7+.2*trait(e,"curiosity"),3)} for w in kw],tasks[1]:{"kind":"dialogue_tree","events":[x.get("id") for x in C]},tasks[2]:{"scope":"constituent","expected":None},tasks[3]:{"speaker":(m or {}).get("speaker"),"target":target(m),"branch_owner":bo,"branch_memory":bm}}; ready=.1; att=clamp(.4+.3*trait(e,"social_sensitivity")+(.15 if m else-.1)+r.gauss(0,.04)); pub=kw
    elif role=="thought":
        work={tasks[0]:{"concepts":kw+rc["tags"],"breadth":round(clamp(trait(e,"openness")+z["association"]),3)},tasks[1]:{"operation":"merge","left":kw,"right":rc["tags"]},tasks[2]:rc,tasks[3]:{"arousal":round(clamp(.15+.4*trait(e,"emotional_reactivity")+.2*rc["emo"]),3)}}; ready=.2; att=clamp(.32+.35*trait(e,"curiosity")+r.gauss(0,.05)); pub=[]
    else:
        direct=bool(m and isq(m) and target(m)==e); ready=clamp(.22+.26*trait(e,"extraversion")+.25*trait(e,"curiosity")+.18*trait(e,"self_disclosure")-.22*trait(e,"inhibition")+(.55 if direct else 0)+z["social"]-.4*z["inhibition"]+r.gauss(0,.04)); work={tasks[0]:{"direct_question":direct},tasks[1]:{"goal":"contribute_to_shared_beat"},tasks[2]:{"readiness":ready},tasks[3]:{"silence_internal":True}}; att=.4; pub=[]
    return {"phase":"sense","node":n,"entity":e,"local":local,"role":role,"tasks":tasks,"private":{"event":m,"context":C,"keywords":kw,"memory":rc,"noise":z,"work":work,"branch_owner":bo,"branch_memory":bm},"public":{"node":n,"entity":e,"role":role,"attention":round(att,3),"readiness":round(ready,3),"concepts":pub}}

def bus(parts,key):
    if {p["node"] for p in parts}!=set(range(12)): raise RuntimeError("all 12 nodes required")
    pub=[p["public"] for p in sorted(parts,key=lambda x:x["node"])]; expr=[p for p in pub if p["role"]=="expression"]; concepts=[]
    for p in pub:
        for w in p.get("concepts",[]):
            if w not in concepts: concepts.append(w)
    return {"key":key,"public":pub,"private":{e:[p for p in parts if p["entity"]==e] for e in ORDER},"network":{"mean_attention":round(sum(p["attention"] for p in pub)/12,4),"expression":{p["entity"]:p["readiness"] for p in expr},"concepts":concepts[:16]}}
def rp(B,e,role): return next(p for p in B["private"][e] if p["role"]==role)

def recurrent(n,key,B):
    e,local,role,tasks=ni(n); C=rp(B,e,"comprehension"); H=rp(B,e,"thought"); X=rp(B,e,"expression"); net=B["network"]; r=rr("recur",key,n)
    if role=="comprehension": work={tasks[0]:{"coactive":list(dict.fromkeys(C["private"]["keywords"]+net["concepts"]+H["private"]["memory"]["tags"]))[:16]},tasks[1]:C["private"]["work"][tasks[1]],tasks[2]:C["private"]["work"][tasks[2]],tasks[3]:{"network_attention":net["mean_attention"]}}; ready=0; intent=None
    elif role=="thought": work=H["private"]["work"]; ready=.2; intent=None
    else:
        ready=clamp(X["public"]["readiness"]+r.gauss(0,.025)); crowd=sum(v for k,v in net["expression"].items() if k!=e)/3; latency=max(.05,1.4-1.08*ready+.28*trait(e,"inhibition")+.12*crowd+r.uniform(0,.16)); rc=H["private"]["memory"]; intent={"readiness":round(ready,3),"latency":round(latency,4),"memory":rc.get("id"),"concepts":rc["tags"][:6]}; work={tasks[0]:{"intent":"shared_beat"},tasks[1]:intent,tasks[2]:{"readiness":ready,"latency":latency},tasks[3]:{"provenance":True}}
    return {"phase":"recurrent","node":n,"entity":e,"local":local,"role":role,"tasks":tasks,"private":{"work":work,"intent":intent},"public":{"node":n,"entity":e,"role":role,"readiness":round(ready,3)}}

STARTERS=["What kind of thing can keep your attention for hours?","Do you usually prefer quiet places or busy ones?","What makes you trust somebody?","Are you more of a planner or an improviser?","What kind of humor works on you?","What do you notice first when you meet someone?","What sort of problem do you actually enjoy solving?","Would you rather revisit somewhere familiar or go somewhere new?","What makes a day feel worthwhile to you?","What kind of conversation do you usually enjoy?"]
ANS={
"trust":{"sarah":"Consistency. I trust people more when what they do keeps matching what they say.","mara":"How they treat people when there is nothing to gain from it.","owen":"Consistency, especially when being consistent is inconvenient.","jules":"Whether I can be a little strange around them without feeling like I have to manage their reaction."},
"quiet":{"sarah":"Fairly quiet, but not dead silent. I like enough going on that I can notice things.","mara":"Busy, as long as it feels alive instead of chaotic.","owen":"Quiet. I notice more when there is not much competing for attention.","jules":"Busy enough that something unexpected can happen."},
"planner":{"sarah":"I like a loose plan and then room to change it.","mara":"I improvise. A plan is useful until something more interesting happens.","owen":"I plan first. I relax more when I know the shape of what I am doing.","jules":"Mostly improviser. Too much structure makes me want to escape the structure."},
"humor":{"sarah":"Dry humor, especially when it sneaks up on me.","mara":"Anything quick and a little shameless, as long as it is not cruel.","owen":"Dry humor. I like it when nobody has to announce the joke.","jules":"The stranger and more sideways it is, the better."},
"attention":{"sarah":"Something complicated enough that I can keep finding another layer.","mara":"A story where I start caring about the people before I realize how long I have been listening.","owen":"A problem with a clear shape that I can actually get somewhere with.","jules":"Anything that keeps producing weird connections faster than I can follow them."},
"notice":{"sarah":"Usually what they seem curious about.","mara":"Usually the mood between people.","owen":"Usually what is out of place or does not quite add up.","jules":"Usually one odd detail that probably was not supposed to be important."},
"problem":{"sarah":"The kind where the evidence is messy but there is a pattern hiding in it.","mara":"A people problem where everybody thinks they are talking about the same thing but they are not.","owen":"A problem with enough constraints that I can tell whether the solution actually works.","jules":"An open-ended one where a ridiculous idea has at least a small chance of being useful."},
"travel":{"sarah":"Somewhere new, but I want enough time there to stop feeling like a visitor.","mara":"Somewhere new. I like having to figure the place out as I go.","owen":"Somewhere familiar if I know exactly why I liked it the first time.","jules":"Somewhere new. I would rather be a little disoriented than bored."},
"worth":{"sarah":"Learning something I did not expect to care about.","mara":"Having one conversation that makes the day feel less ordinary than it started.","owen":"Getting one useful thing done and having some quiet afterward.","jules":"Finding something interesting enough that I forget I was trying to have a good day."},
"conversation":{"sarah":"One where somebody says something precise enough that it changes how I was thinking.","mara":"One where people actually reveal something instead of staying polite the whole time.","owen":"One where people answer each other instead of waiting to talk.","jules":"One that wanders into something nobody planned to talk about."}}
def category(q):
    q=q.lower()
    if "trust" in q:return "trust"
    if "quiet" in q or "busy" in q:return "quiet"
    if "planner" in q or "improviser" in q:return "planner"
    if "humor" in q:return "humor"
    if "attention" in q:return "attention"
    if "notice first" in q or "meet someone" in q:return "notice"
    if "problem" in q:return "problem"
    if "familiar" in q or "somewhere new" in q:return "travel"
    if "worthwhile" in q:return "worth"
    if "conversation" in q:return "conversation"
    return None
def blank_answer(e,q):
    c=category(q)
    return ANS[c][e] if c else {"sarah":"I would need a second to make that precise.","mara":"I usually know my reaction before I know my explanation.","owen":"I am not sure yet. I would rather be specific than invent an answer.","jules":"I have an answer forming, but it is taking the scenic route."}[e]
def follow(e,m,key):
    low=(m or {}).get("text","").lower()
    if any(w in low for w in ("conversation","talk","exchange","waiting for their turn")): qs=["What makes that kind of conversation satisfying?","Do you like disagreement in a conversation like that?"]
    elif any(w in low for w in ("problem","evidence","constraints","open-ended")): qs=["What makes that kind of problem satisfying?","How did you land on that?"]
    elif any(w in low for w in ("quiet","busy","noise","environment")): qs=["What do you like about that kind of environment?","Have you always preferred that?"]
    elif any(w in low for w in ("new","familiar","place","disoriented","visitor")): qs=["What do you like about being somewhere unfamiliar?","Has that preference changed much for you?"]
    elif any(w in low for w in ("trust","people","someone","consistent","reaction")): qs=["What makes that signal matter to you?","Has that changed much for you?"]
    else: qs=["What makes you say that?","How did you land on that?","Has that changed much for you?"]
    return rr("follow",e,key,*toks(low)).choice(qs)
def reason(e,text):
    low=text.lower()
    if any(w in low for w in ("problem","evidence","constraints","open-ended")):
        return {"sarah":"Because I like starting with incomplete evidence and gradually finding a structure.","mara":"Because I like when the real problem is that people think they agree when they do not.","owen":"Because constraints give me something I can test instead of just argue about.","jules":"Because I like when a weird possibility survives long enough to become useful."}[e]
    return {"sarah":"Because I tend to trust patterns more than first impressions.","mara":"Because I notice what people do when they stop performing for everybody else.","owen":"Because consistency is harder to fake over time than confidence is.","jules":"Because the moments when somebody stops trying to look normal usually tell me more."}[e]
def answer(e,I,q,M):
    mm=mem(e,I.get("branch_memory"),M) or mem(e,I.get("memory"),M); low=q.lower()
    if mm:
        if "what makes" in low or "how did you land" in low:return reason(e,mm["text"])
        if "changed" in low or "always preferred" in low:return {"sarah":"A little around the edges, but the basic preference is still there.","mara":"Not much. I might explain it differently now, but it still feels true.","owen":"Not substantially. I have more exceptions now, but the rule still fits.","jules":"Probably, but not in a straight line. The core still sounds like me."}[e]
        if "what do you like" in low:return reason(e,mm["text"])
        return mm["text"].rstrip(".")+"."
    return blank_answer(e,q)
def react(e,m):
    return {"sarah":"That gives me a more specific picture of how you think.","mara":"That is the kind of answer that actually tells me something about you.","owen":"There is a useful rule underneath that answer.","jules":"That answer has a shape to it. I can already imagine the exceptions being interesting."}[e]

def observe(M,msg):
    c=msg.get("cognition") or {}; move=c.get("move_type"); uid=unit_id(msg)
    for e in ORDER:
        s=M["entities"][e]
        if s.get("last_event")==msg.get("id"):continue
        s.setdefault("room_memories",[]).append({"source":msg.get("id"),"status":"observed","speaker":msg.get("speaker"),"text":str(msg.get("text",""))[:300],"discourse":msg.get("discourse_id"),"branch_owner":c.get("branch_owner"),"branch_memory":c.get("branch_memory"),"beat_id":uid}); s["room_memories"]=s["room_memories"][-180:]
        if msg.get("speaker")!=e and msg.get("speaker") in ORDER:
            p=s["people"].setdefault(msg["speaker"],{"familiarity":.02,"reports":[]}); p["familiarity"]=round(clamp(p.get("familiarity",.02)+.012),3)
            if move in {"answer","self_disclosure","new_root"}: p["reports"].append({"source":msg.get("id"),"status":"reported","text":str(msg.get("text",""))[:300],"branch_owner":c.get("branch_owner"),"branch_memory":c.get("branch_memory")}); p["reports"]=p["reports"][-90:]
        s["last_event"]=msg.get("id")
def ingest(M,V):
    ids=[x.get("id") for x in V]
    for e in ORDER:
        last=M["entities"][e].get("last_event"); start=ids.index(last)+1 if last in ids else (max(0,len(V)-8) if last else 0)
        for x in V[start:]: observe(M,x)

def order4(parts,prev,cycle):
    E={p["entity"]:p for p in parts if p["role"]=="expression" and p["private"].get("intent")}
    if set(E)!=set(ORDER): raise RuntimeError("four expression processes required")
    z=sorted((p["private"]["intent"]["latency"]-.2*p["private"]["intent"]["readiness"]+.015*((ORDER.index(e)-cycle)%4),ORDER.index(e),e) for e,p in E.items()); out=[e for _,_,e in z]
    d=target(prev) if isq(prev) else None
    if d in out: out.remove(d); out.insert(0,d)
    return out,E

def emit(e,move,target_e,parent,derived,text,beat,idx,M,T,branch=(None,None),memory_id=None):
    now=datetime.now(timezone.utc); mid=f"{now.strftime('%Y%m%dT%H%M%S%f')[:-3]}-{e}-v4"; did="d-"+mid; bo,bm=branch; prov=memory_id
    if move in {"answer","self_disclosure"} and not prov: prov=mid; bo=e; bm=mid
    if move=="question": bo=bm=None
    cog={"move_type":move,"target":target_e,"memory_provenance":prov,"branch_owner":bo,"branch_memory":bm,"externalization":"memory" if memory_id else "structured","compute_nodes":[n+1 for n in A["entities"][e]],"processes":12,"beat_id":beat,"beat_index":idx}
    msg={"id":mid,"at":now.isoformat().replace("+00:00","Z"),"speaker":e,"text":text,"runtime":VERSION,"boot_id":BOOT,"beat_id":beat,"beat_index":idx,"cognition":cog,"discourse_id":did,"parent_discourse_id":parent,"derived_from":derived}
    node={"id":did,"speaker":e,"parent":parent,"derived_from":derived,"move":move,"target":target_e,"branch_owner":bo,"branch_memory":bm,"text":text,"at":msg["at"],"beat_id":beat,"beat_index":idx}; return msg,node
def add(V,T,M,msg,node,cycle):
    V.append(msg); T["nodes"].append(node)
    if not node["parent"]: T.setdefault("roots",[]).append(node["id"])
    s=M["entities"][msg["speaker"]]; s["spoken"]=s.get("spoken",0)+1; s["self_history"].append({"source":msg["id"],"text":msg["text"],"move":msg["cognition"]["move_type"],"memory":msg["cognition"].get("memory_provenance"),"branch_memory":msg["cognition"].get("branch_memory"),"discourse":msg["discourse_id"],"beat_id":msg["beat_id"]}); s["self_history"]=s["self_history"][-180:]; observe(M,msg)

def commit(parts,key):
    S=state(); M=minds(); T=tree(); V=conv(); prev=event(); cycle=S.get("cycle",0)+1; ingest(M,V)
    for e in ORDER:
        ep=[p for p in parts if p["entity"]==e]; c=next(p for p in ep if p["role"]=="comprehension"); co=c["private"]["work"][c["tasks"][0]]["coactive"]; s=M["entities"][e]; s["noise"]=nz(e,s,key); s["fast"]={"activation":round(sum(p["public"]["readiness"] for p in ep)/3,3),"attention":co[:10]}; s["medium"]={"topics":co[:10],"branch_interest":round(clamp(.4*trait(e,"curiosity")+.4*trait(e,"attention_persistence")),3)}
    order,E=order4(parts,prev,cycle); beat=f"beat-{BOOT}-{cycle:06d}"; spoken=[]; q=prev if isq(prev) else None; qscope=((q or {}).get("cognition") or {}).get("move_type")
    if q is None:
        asker=order.pop(0); tgt=order[0]; text=rr("starter",asker,key).choice(STARTERS); msg,node=emit(asker,"question",tgt,None,(prev or {}).get("discourse_id"),text,beat,0,M,T); add(V,T,M,msg,node,cycle); spoken.append(msg); q=msg; qscope="question"; order.remove(tgt); order.insert(0,tgt)
    ans_e=target(q) if target(q) in order else order[0]; order.remove(ans_e); base=E[ans_e]["private"]["intent"]; bo,bm=anchor(q); general=((q.get("cognition") or {}).get("move_type")=="question"); I={"memory":None if general else base.get("memory"),"branch_memory":bm}; text=answer(ans_e,I,q["text"],M); msg,node=emit(ans_e,"answer",q["speaker"],q["discourse_id"],None,text,beat,len(spoken),M,T,(bo,bm),I["memory"]); add(V,T,M,msg,node,cycle); spoken.append(msg); answer_msg=msg
    final_e=order.pop(cycle%len(order))
    while order:
        e=order.pop(0)
        if qscope=="question": text=blank_answer(e,q["text"]); msg,node=emit(e,"self_disclosure",q["speaker"] if q["speaker"]!=e else None,q["discourse_id"],None,text,beat,len(spoken),M,T)
        else: bo,bm=anchor(answer_msg); text=react(e,answer_msg); msg,node=emit(e,"reaction",answer_msg["speaker"],answer_msg["discourse_id"],None,text,beat,len(spoken),M,T,(bo,bm))
        add(V,T,M,msg,node,cycle); spoken.append(msg)
    if depth(answer_msg["discourse_id"],T)>=A["discourse"]["max_depth"]-1:
        peers=[x for x in ORDER if x!=final_e]; tgt=rr("root",final_e,key).choice(peers); text=rr("starter2",final_e,key).choice(STARTERS); msg,node=emit(final_e,"question",tgt,None,answer_msg["discourse_id"],text,beat,len(spoken),M,T)
    else:
        bo,bm=anchor(answer_msg); text=follow(final_e,answer_msg,key); msg,node=emit(final_e,"follow_up",answer_msg["speaker"],answer_msg["discourse_id"],None,text,beat,len(spoken),M,T,(bo,bm))
    add(V,T,M,msg,node,cycle); spoken.append(msg)
    T["nodes"]=T["nodes"][-900:]; T["roots"]=T.get("roots",[])[-240:]; V=V[-800:]; stamp=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    S.update({"version":VERSION,"boot_id":BOOT,"cycle":cycle,"last_run":stamp,"messages":len(V),"last_public_event":spoken[-1]["id"],"last_speaker":spoken[-1]["speaker"],"last_beat_id":beat,"beat_contributors":[m["speaker"] for m in spoken],"beat_message_count":4,"silence_cycles":0,"note":"4 separate entities; 12 nodes x 4 tasks = 48 processes; all 4 contribute once per beat; no voting"})
    save(ROOM/"conversation.json",V); save(ROOM/"discourse.json",T); save(ROOM/"cognitive_state.json",M); save(ROOM/"state.json",S)
    cm={"schema":4,"entities":{e:{"name":N[e],"profile":P[e],"genome":P[e]["traits"],"development":{"turns":cycle,"spoken":M["entities"][e].get("spoken",0),"silences":M["entities"][e].get("silences",0),"topic_weights":{t:1 for t in M["entities"][e].get("medium",{}).get("topics",[])},"relationships":{o:v.get("familiarity",0) for o,v in M["entities"][e].get("people",{}).items()},"lifetime_memory_count":len(SEED[e])},"memory":[{"text":x["text"]} for x in M["entities"][e].get("room_memories",[])[-12:]]} for e in ORDER}}
    live={"generated_at":stamp,"architecture_version":VERSION,"boot_id":BOOT,"minds":cm,"profiles":P,"state":S,"conversation":V,"discourse":T,"network":{"compute_nodes":12,"entities":4,"nodes_per_entity":3,"tasks_per_node":4,"active_processes":48,"voting":False,"public_bus":True,"private_scope":"same_entity","beat_output":"4 unique speakers"}}
    save(ROOM/"live.json",live); save(ROOT/"society"/"live.json",live); print("Room beat",cycle,":",", ".join(N[m["speaker"]] for m in spoken))

def selftest():
    S=[sense(n,"test") for n in range(12)]; B=bus(S,"test"); R=[recurrent(n,"test",B) for n in range(12)]; o,E=order4(R,event(),state().get("cycle",0)+1)
    assert len(S)==12 and len(R)==12 and set(o)==set(ORDER) and A["network"]["voting"] is False
    legacy={"id":"legacy-test","speaker":"sarah","text":"A pre-beat Room event.","runtime":"room-cognition-v3","boot_id":BOOT,"cognition":{"move_type":"question","target":"mara"},"discourse_id":"d-legacy-test"}; tm=fresh_minds(); observe(tm,legacy); assert tm["entities"]["mara"]["room_memories"][-1]["beat_id"]=="legacy-legacy-test"
    print("PASS v4: 12 nodes, 48 processes, legacy events normalized, four contributors per beat, no voting")
def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True); p=sp.add_parser("node"); p.add_argument("--phase",choices=["sense","recurrent"],required=True); p.add_argument("--bus",default=""); sp.add_parser("bus"); sp.add_parser("commit"); sp.add_parser("selftest"); a=ap.parse_args(); key=os.environ.get("ROOM_CYCLE_KEY") or f'{state().get("cycle",0)+1}:{os.environ.get("GITHUB_RUN_ID","local")}'
    if a.cmd=="node":
        n=int(os.environ["ROOM_NODE_ID"]); x=sense(n,key) if a.phase=="sense" else recurrent(n,key,load(Path(a.bus),{})); PARTS.mkdir(exist_ok=True); save(PARTS/f"{a.phase}-{n:02d}.json",x)
    elif a.cmd=="bus": WORK.mkdir(exist_ok=True); save(WORK/"bus-sense.json",bus([load(p,{}) for p in sorted(PARTS.glob("sense-*.json"))],key))
    elif a.cmd=="commit":
        x=[load(p,{}) for p in sorted(PARTS.glob("recurrent-*.json"))]
        if {p["node"] for p in x}!=set(range(12)): raise RuntimeError("commit requires all 12 recurrent nodes")
        commit(x,key)
    else:selftest()
if __name__=="__main__": main()
