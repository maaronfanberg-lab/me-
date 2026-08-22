#!/usr/bin/env python3
"""Isolated fifth-participant experiment. Never writes live Room state."""
from __future__ import annotations
import argparse,json
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path

def load(p): return json.loads(Path(p).read_text())
def save(p,o): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(o,indent=2,ensure_ascii=False)+'\n')
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def init(a):
 s=load(a.state); m=load(a.minds); f=load(a.feed)
 e={'schema':1,'created_at':now(),'source_cycle':int(s.get('cycle',0)),'participant':{'id':'sara','name':'Sara'},'state':deepcopy(s),'minds':deepcopy(m),'seed_messages':list(f.get('messages',[]))[-24:],'turns':[]}
 save(a.out,e)
def inbox(a):
 e=load(a.experiment); public=(e['seed_messages']+[x['message'] for x in e['turns']])[-16:]
 save(a.out,{'participant':{'id':'sara','name':'Sara'},'instruction':'You are another participant in this conversation. Respond naturally if you have something you want to say. You may respond, make an association, change direction, or remain silent. Do not moderate, diagnose, optimize, or repair the group.','conversation':public,'topic_episode':e.get('state',{}).get('topic_episode')})
def record(a):
 e=load(a.experiment); text=Path(a.text).read_text().strip(); seq=len(e['turns'])+1
 if not text: raise SystemExit('empty turn')
 e['turns'].append({'sequence':seq,'message':{'id':f'sara-{seq:04d}','speaker':'sara','display_name':'Sara','text':text,'timestamp':now()}}); save(a.experiment,e)
def main():
 p=argparse.ArgumentParser(); sp=p.add_subparsers(dest='cmd',required=True)
 q=sp.add_parser('init'); q.add_argument('--state',default='room/state.json');q.add_argument('--minds',default='room/minds.json');q.add_argument('--feed',default='room/feed.json');q.add_argument('--out',default='experiments/room-sara/session.json');q.set_defaults(fn=init)
 q=sp.add_parser('inbox');q.add_argument('--experiment',default='experiments/room-sara/session.json');q.add_argument('--out',default='experiments/room-sara/inbox.json');q.set_defaults(fn=inbox)
 q=sp.add_parser('record');q.add_argument('--experiment',default='experiments/room-sara/session.json');q.add_argument('text');q.set_defaults(fn=record)
 a=p.parse_args();a.fn(a)
if __name__=='__main__':main()
