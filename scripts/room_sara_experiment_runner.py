#!/usr/bin/env python3
"""Run genuine Room-model replies to Sara without mutating production Room state.

Uses the existing Room private model boundary and personalities, but reads/writes only
experiments/room-sara/session.json. Sara remains externally supplied by ChatGPT.
"""
from __future__ import annotations
import json, os, sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import room_private_model as model
import room_personality_v2 as personality

SESSION=ROOT/'experiments/room-sara/session.json'
AI=('sarah','mara','owen','jules')
DISPLAY={'sarah':'Sarah','mara':'Mara','owen':'Owen','jules':'Jules','sara':'Sara'}

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def load(): return json.loads(SESSION.read_text())
def save(x): SESSION.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def public_messages(s):
 out=[]
 for m in s.get('seed_messages',[]): out.append({'speaker':str(m.get('speaker','')).lower(),'text':m.get('text','')})
 for t in s.get('turns',[]):
  m=t.get('message',t); out.append({'speaker':str(m.get('speaker','')).lower(),'text':m.get('text','')})
 return out

def profile(entity):
 p=ROOT/'room'/'profiles'/f'{entity}.json'
 try:return json.loads(p.read_text())
 except:return {'name':DISPLAY[entity]}

def relationship(entity,partner):
 return {'exposure':0.2,'direct_familiarity':0.1,'trust':0.1,'predictability':0.1,'reciprocity':0.1,'warmth':0.1,'respect':0.12,'disclosure_depth':0.0,'tension':0.0}

def run_one(entity, conversation):
 latest=conversation[-1]
 partner=latest['speaker']
 payload={'entity':entity,'profile':profile(entity),'event':{'speaker':partner,'text':latest['text'],'cognition':{'target':entity}},'context':conversation[-12:],'partner':partner,'relationship':relationship(entity,partner),'topic':{},'keywords':[]}
 thought=model.run('thought',deepcopy(payload)) or {}
 payload['deliberation']=thought
 expression=model.run('expression',payload) or {}
 text=str(expression.get('utterance') or '').strip()
 if not text: raise RuntimeError(f'empty expression for {entity}')
 return text,expression

def main():
 if not os.environ.get('ROOM_MODEL_URL'): raise SystemExit('ROOM_MODEL_URL missing')
 s=load(); conv=public_messages(s)
 if not conv or conv[-1]['speaker']!='sara':
  print('No fresh Sara turn to answer; leaving experiment unchanged.'); return
 # One natural response sequence from the real four generators. Each later voice
 # hears the prior response, preserving sequential interaction rather than four parallel echoes.
 for entity in AI:
  text,cog=run_one(entity,conv)
  seq=len(s.setdefault('turns',[]))+1
  msg={'id':f'exp-{seq:04d}','speaker':entity,'display_name':DISPLAY[entity],'text':text,'timestamp':now(),'cognition':{'move_type':cog.get('move'),'target':cog.get('target'),'experimental':True}}
  s['turns'].append({'sequence':seq,'message':msg}); conv.append({'speaker':entity,'text':text})
 save(s)
 print(f'Added {len(AI)} autonomous Room replies; waiting for Sara.')
if __name__=='__main__': main()
