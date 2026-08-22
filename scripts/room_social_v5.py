from __future__ import annotations
import re
from collections import Counter

ORDER=("sarah","mara","owen","jules")
PARTICIPANTS=ORDER+("allen","sara")
REL_KEYS=("exposure","direct_familiarity","trust","predictability","reciprocity","warmth","respect","disclosure_depth","tension")
GENERIC=set("the and but for not was are you your our out too did can got one once that this with from have has had just what when where how there they them then than about would could should into only because been being does doing done will well yeah okay also still maybe kind sort thing things something anything someone everyone say saying think thinking thought know knowing mean means seem seems want wants wanted make making made start starting started try trying tried good great nice sure right actually probably pretty little much many few around again already even ever never always often sometimes today tonight tomorrow yesterday different together interesting going everything really people person conversation talk feel feeling answer question makes like their which while more very usually between over under through during before after each other another both such own same much example specific rule case point pattern actual interaction general concrete keep hear hearing saying said change changes changed outcome matter matters version part piece compare comparison contrast exception exceptions different differently useful interesting coming leaving leave pin rather now edge test against gets involving especially happens rest i'd".split())
GENERIC.update({"you're","we're","they're","i'm","don't","doesn't","isn't","aren't","wasn't","weren't","can't","won't","wouldn't","couldn't","shouldn't"})


def clamp(x,a=0,b=1): return max(a,min(b,float(x)))
def approach(x,rate): return clamp(float(x)+float(rate)*(1-float(x)))
def words(text):
 out=[]
 for w in re.findall(r"[a-z][a-z'-]{2,}",str(text or '').lower()):
  w=w.strip("'-"); w=w[:-2] if w.endswith("'s") else w
  if w and w not in GENERIC and w not in out: out.append(w)
 return out


def rel_template(legacy=.02):
 legacy=clamp(legacy)
 return {'social_model':3,'legacy_familiarity':legacy,'exposure':min(.75,.05+.70*legacy),'direct_familiarity':.08,'trust':.10,'predictability':.12,'reciprocity':.08,'warmth':.12,'respect':.12,'disclosure_depth':0.,'tension':0.,'direct_turns':0,'observed_turns':0,'repair_attempts':0,'repair_successes':0,'last_direct_cycle':None,'shared_references':[],'events':[],'reports':[]}
def rescale_legacy_relationship(r):
 dt=max(0,int(r.get('direct_turns',0))); obs=max(0,int(r.get('observed_turns',0)))
 r['direct_familiarity']=min(.72,.08+.00125*dt)
 r['reciprocity']=min(.64,.08+.00105*dt)
 r['predictability']=min(.64,.12+.00085*dt)
 r['warmth']=min(.56,.12+.00070*dt)
 r['respect']=min(.56,.12+.00055*dt)
 r['exposure']=min(1.,max(float(r.get('exposure',0)),.05+.001*obs))
 r['trust']=min(.35,max(.10,float(r.get('trust',.10))))
 r['social_model']=3
 return r
def migrate_minds(M):
 M=M or {'entities':{}}; ents=M.setdefault('entities',{})
 for e in ORDER:
  people=ents.setdefault(e,{}).setdefault('people',{})
  for o in PARTICIPANTS:
   if o==e: continue
   old=people.get(o) or {}
   if 'trust' not in old or 'direct_familiarity' not in old:
    new=rel_template(old.get('familiarity',.02)); new['reports']=list(old.get('reports',[]))[-90:]; people[o]=new
   else:
    old_model=int(old.get('social_model',1))
    defaults=rel_template(old.get('legacy_familiarity',old.get('familiarity',.02)))
    for k,v in defaults.items(): old.setdefault(k,v)
    if old_model<3: rescale_legacy_relationship(old)
    old['events']=list(old.get('events',[]))[-160:]; old['shared_references']=list(old.get('shared_references',[]))[-60:]; old['reports']=list(old.get('reports',[]))[-90:]
 return M


def topic_template(c=0):
 return {
  'semantic_schema':4,'id':f'topic-{c:06d}','root':None,'current_facet':None,
  'facets':[],'visited_facets':[],'facet_index':0,'unresolved':[],'examples':[],
  'disagreements':[],'shared_references':[],'participants':list(PARTICIPANTS),'turns':0,
  'low_novelty_beats':0,'recent_terms':[],'last_shift_cycle':c,'status':'forming',
  'branches':[],'branch_history':[],'focus_turns':0,'last_branch_cycle':c,'escape_pressure':0,
 }


def _term_tokens(value):
 return {w for w in words(value) if len(w)>=3}
def _near_term(a,b):
 a=str(a or '').strip().lower(); b=str(b or '').strip().lower()
 if not a or not b: return False
 if a==b: return True
 ta,tb=_term_tokens(a),_term_tokens(b)
 if not ta or not tb: return a in b or b in a
 if len(a)>=4 and len(b)>=4 and (a in b or b in a): return True
 return len(ta&tb)/max(1,min(len(ta),len(tb)))>=.72
def _branch_index(t,label):
 for i,b in enumerate(t.get('branches',[])):
  if _near_term(b.get('label'),label): return i
 return None
def _add_branch(t,label,parent,cycle,depth=None):
 label=str(label or '').strip().lower()
 if not label or not _term_tokens(label): return None
 idx=_branch_index(t,label)
 if idx is not None:
  b=t['branches'][idx]; b['hits']=int(b.get('hits',0))+1; b['last_cycle']=cycle; b['status']='open'; return b
 parent=str(parent or '').strip().lower() or None
 if depth is None:
  pidx=_branch_index(t,parent) if parent else None
  depth=(int(t['branches'][pidx].get('depth',0))+1) if pidx is not None else (0 if parent is None else 1)
 b={'label':label,'parent':parent,'depth':int(depth),'first_cycle':cycle,'last_cycle':cycle,'hits':1,'status':'open'}
 t.setdefault('branches',[]).append(b)
 return b
def _upgrade_topic_tree(t,cycle):
 defaults=topic_template(cycle)
 for k,v in defaults.items(): t.setdefault(k,v)
 t['participants']=list(PARTICIPANTS)
 if int(t.get('semantic_schema',1))<4:
  old_root=str(t.get('root') or '').strip().lower() or None
  old_facets=[str(x or '').strip().lower() for x in t.get('facets',[]) if str(x or '').strip()]
  old_visited=[str(x or '').strip().lower() for x in t.get('visited_facets',[]) if str(x or '').strip()]
  t['branches']=[]
  if old_root: _add_branch(t,old_root,None,int(t.get('last_shift_cycle') or cycle),0)
  for f in old_facets[:16]:
   if old_root and _near_term(f,old_root): continue
   _add_branch(t,f,old_root,cycle,1)
  t['branch_history']=old_visited[-24:]
  t['focus_turns']=0
  t['last_branch_cycle']=int(t.get('last_shift_cycle') or cycle)
  t['escape_pressure']=0
  t['semantic_schema']=4
 return t
def migrate_state(S):
 S=S or {}; cycle=int(S.get('cycle',0)); old=S.get('topic_episode')
 if not old or int(old.get('semantic_schema',1))<3:
  S['topic_episode']=topic_template(cycle); return S
 S['topic_episode']=_upgrade_topic_tree(S['topic_episode'],cycle)
 return S


def _target(msg,by=None):
 c=(msg or {}).get('cognition') or {}; tgt=c.get('target')
 if tgt in PARTICIPANTS: return tgt
 p=(msg or {}).get('parent_discourse_id')
 if p and by and p in by and by[p].get('speaker') in PARTICIPANTS: return by[p]['speaker']
 return None
def classify_event(listener,msg,by=None):
 sp=(msg or {}).get('speaker')
 if sp not in PARTICIPANTS or sp==listener: return None
 c=(msg or {}).get('cognition') or {}; move=c.get('move_type') or 'other'; direct=_target(msg,by)==listener; low=str(msg.get('text','')).lower(); risk=1 if move in {'self_disclosure','disclosure'} else 0
 if any(x in low for x in ('afraid','ashamed','regret','hurt','vulnerable','trust you','scared')): risk=max(risk,2)
 return {'speaker':sp,'listener':listener,'direct':direct,'participation':'DIRECT_ADDRESSEE' if direct else 'OVERHEARER','move':move,'risk':risk,'repair_attempt':any(x in low for x in ('sorry','misunderstood','what i meant','i was wrong','let me correct')),'disagreement':move in {'disagree','disagreement'} or bool(re.search(r"\b(i don't agree|i disagree|not sure i agree|but i think)\b",low)),'support':bool(re.search(r"\b(that makes sense|i can see why|i get why|i'm with you|i understand)\b",low)),'callback':move=='callback' or bool(c.get('shared_reference')),'terms':list(c.get('topic_terms') or words(msg.get('text','')))[:8],'message_id':msg.get('id')}
def apply_event(r,e,cycle):
 if not e:return r
 r['observed_turns']=int(r.get('observed_turns',0))+1; r['exposure']=approach(r.get('exposure',0),.0015)
 if not e.get('direct'): return r
 r['direct_turns']=int(r.get('direct_turns',0))+1; r['last_direct_cycle']=cycle; r['direct_familiarity']=approach(r.get('direct_familiarity',0),.0012); move=e.get('move')
 if move in {'answer','follow_up','deepen','compare','callback','repair','repair_success'}: r['reciprocity']=approach(r.get('reciprocity',0),.0009); r['predictability']=approach(r.get('predictability',0),.0005)
 if move in {'answer','follow_up','deepen','compare','support','callback','repair'}: r['warmth']=approach(r.get('warmth',0),.0006)
 if move in {'answer','deepen','compare','disagree','callback'}: r['respect']=approach(r.get('respect',0),.00045)
 if e.get('disagreement'): r['tension']=approach(r.get('tension',0),.010); r['predictability']=clamp(r.get('predictability',0)*.998)
 if e.get('support'): r['warmth']=approach(r.get('warmth',0),.0015)
 if e.get('repair_attempt'): r['repair_attempts']=int(r.get('repair_attempts',0))+1; r['tension']=clamp(r.get('tension',0)*.92)
 if move=='repair_success': r['repair_successes']=int(r.get('repair_successes',0))+1; r['tension']=clamp(r.get('tension',0)*.72); r['trust']=approach(r.get('trust',0),.006)
 if int(e.get('risk',0))>=1 and (e.get('support') or move in {'answer','repair_success','callback'}): r['trust']=approach(r.get('trust',0),.004*int(e['risk'])); r['disclosure_depth']=approach(r.get('disclosure_depth',0),.004*int(e['risk']))
 if e.get('callback'): r['predictability']=approach(r.get('predictability',0),.002); r['reciprocity']=approach(r.get('reciprocity',0),.002)
 r.setdefault('events',[]).append({'cycle':cycle,'kind':move,'direct':True,'message_id':e.get('message_id'),'risk':e.get('risk',0),'repair':bool(e.get('repair_attempt')),'disagreement':bool(e.get('disagreement'))}); r['events']=r['events'][-160:]; return r
def observe_message(M,msg,cycle,by=None):
 migrate_minds(M)
 for listener in ORDER:
  if listener==msg.get('speaker'): continue
  e=classify_event(listener,msg,by)
  if not e:continue
  r=M['entities'][listener]['people'][msg['speaker']]; apply_event(r,e,cycle)
  if e.get('direct'):
   refs=r.setdefault('shared_references',[])
   for term in e.get('terms',[])[:3]:
    term=str(term).strip().lower()
    if term and term not in refs: refs.append(term)
   r['shared_references']=refs[-60:]
 return M


def _declared_terms(m):
 c=(m or {}).get('cognition') or {}; vals=c.get('topic_terms')
 if isinstance(vals,list) and vals:
  out=[]
  for x in vals:
   x=str(x or '').strip().lower()
   if x and x not in out: out.append(x)
  return out
 return words((m or {}).get('text',''))
def topic_terms_from_messages(ms,limit=12,episode_id=None):
 c=Counter(); rec=[]
 for m in ms[-32:]:
  if episode_id and ((m.get('cognition') or {}).get('topic_episode')!=episode_id): continue
  ws=_declared_terms(m); rec.extend(ws); c.update(ws)
 return sorted(c,key=lambda w:(-c[w],-max(i for i,x in enumerate(rec) if x==w),w))[:limit] if rec else []

def _recent_term_counts(ms,episode_id=None,window=12):
 c=Counter()
 for m in ms[-window:]:
  if episode_id and ((m.get('cognition') or {}).get('topic_episode')!=episode_id): continue
  c.update(_declared_terms(m))
 return c
def _meaningfully_new(term,t):
 term=str(term or '').strip().lower()
 if not term or not _term_tokens(term): return False
 existing=[t.get('root'),t.get('current_facet')]+[b.get('label') for b in t.get('branches',[])]
 return not any(_near_term(term,x) for x in existing if x)
def _set_focus(t,label,cycle):
 label=str(label or '').strip().lower()
 if not label: return
 current=str(t.get('current_facet') or '').strip().lower()
 if current and not _near_term(current,label): t.setdefault('branch_history',[]).append(current)
 t['current_facet']=label
 if label not in t.setdefault('visited_facets',[]): t['visited_facets'].append(label)
 t['facet_index']=max(0,len(t['visited_facets'])-1)
 t['focus_turns']=0
 t['last_branch_cycle']=cycle
 t['escape_pressure']=0
 t['status']='active'

def _branch_score(branch,cycle,current):
 if _near_term(branch.get('label'),current): return -999
 age=max(0,cycle-int(branch.get('last_cycle',cycle)))
 recency=max(0,1-age/36)
 depth=min(4,int(branch.get('depth',0)))/4
 hits=min(8,int(branch.get('hits',1)))/8
 return 1.3*recency+.8*hits+.35*depth
def update_topic(t,ms,cycle):
 t=_upgrade_topic_tree(t or topic_template(cycle),cycle)
 terms=topic_terms_from_messages(ms,episode_id=t.get('id'))
 counts=_recent_term_counts(ms,t.get('id'),12)

 if t.get('root') is None and terms:
  t['root']=terms[0]
  _add_branch(t,t['root'],None,cycle,0)
  rest=[x for x in terms[1:] if not _near_term(x,t['root'])]
  t['facets']=list(dict.fromkeys(rest))
  for x in rest[:8]: _add_branch(t,x,t['root'],cycle,1)
  t['current_facet']=rest[0] if rest else t['root']
  t['visited_facets']=[t['current_facet']]
  t['branch_history']=[]; t['focus_turns']=0; t['status']='active'; t['last_shift_cycle']=cycle; t['last_branch_cycle']=cycle
 else:
  current=t.get('current_facet') or t.get('root')
  parent=current or t.get('root')
  added=[]
  for x in terms:
   idx=_branch_index(t,x)
   if idx is not None:
    b=t['branches'][idx]; b['hits']=int(b.get('hits',0))+max(1,int(counts.get(x,1))); b['last_cycle']=cycle
   elif _meaningfully_new(x,t):
    b=_add_branch(t,x,parent,cycle)
    if b: added.append(b)
   if x!=t.get('root') and x not in t.setdefault('facets',[]): t['facets'].append(x)

  t['focus_turns']=int(t.get('focus_turns',0))+1
  # A child introduced by the current exchange is the most natural next branch.
  if added and t['focus_turns']>=2:
   best=max(added,key=lambda b:(int(b.get('hits',1)),len(_term_tokens(b.get('label'))),-int(b.get('depth',0))))
   _set_focus(t,best['label'],cycle)
  elif t['focus_turns']>=6:
   # If the current branch is narrowing without producing a child, revive a recent sibling/cousin.
   candidates=[b for b in t.get('branches',[]) if b.get('status','open')=='open' and not _near_term(b.get('label'),current)]
   candidates=[b for b in candidates if int(b.get('last_cycle',0))>=cycle-40]
   if candidates:
    best=max(candidates,key=lambda b:_branch_score(b,cycle,current))
    if _branch_score(best,cycle,current)>.45: _set_focus(t,best['label'],cycle)

 t['turns']=int(t.get('turns',0))+1
 previous=set(t.get('recent_terms',[])); meaningful=[x for x in terms if _meaningfully_new(x,{'root':None,'current_facet':None,'branches':[{'label':p} for p in previous]})]
 t['recent_terms']=terms
 t['low_novelty_beats']=int(t.get('low_novelty_beats',0))+1 if not meaningful else 0

 # An unrelated stimulus is only an escape hatch when the whole live tree has stopped offering branches.
 current=t.get('current_facet') or t.get('root')
 viable=[b for b in t.get('branches',[]) if not _near_term(b.get('label'),current) and int(b.get('last_cycle',0))>=cycle-40]
 if int(t.get('focus_turns',0))>=10 and not viable:
  t['escape_pressure']=int(t.get('escape_pressure',0))+1
 else:
  t['escape_pressure']=max(0,int(t.get('escape_pressure',0))-1)
 if int(t.get('escape_pressure',0))>=3:
  t['status']='ready_to_bridge'

 t['facets']=list(dict.fromkeys(t.get('facets',[])))[:24]
 t['visited_facets']=list(dict.fromkeys(t.get('visited_facets',[])))[-24:]
 t['branch_history']=list(dict.fromkeys(t.get('branch_history',[])))[-32:]
 t['branches']=sorted(t.get('branches',[]),key=lambda b:(int(b.get('last_cycle',0)),int(b.get('hits',0))),reverse=True)[:48]
 return t
def should_shift_topic(t): return bool(t and t.get('status')=='ready_to_bridge')
def new_topic_from_terms(terms,cycle,prior=None):
 clean=[]
 for x in terms:
  x=str(x or '').strip().lower()
  if x and _term_tokens(x) and not any(_near_term(x,y) for y in clean): clean.append(x)
 t=topic_template(cycle)
 if clean:
  t['root']=clean[0]; _add_branch(t,clean[0],None,cycle,0)
  t['facets']=clean[1:]
  for x in clean[1:8]: _add_branch(t,x,clean[0],cycle,1)
  t['current_facet']=t['facets'][0] if t['facets'] else clean[0]
  t['visited_facets']=[t['current_facet']]; t['status']='active'
 if prior and prior.get('current_facet'): t['shared_references']=[prior['current_facet']]
 return t


def choose_partner(e,M,t,cycle):
 scored=[]
 for o in ORDER:
  if o==e:continue
  r=M['entities'][e]['people'][o]; strength=.20*r.get('direct_familiarity',0)+.12*r.get('trust',0)+.10*r.get('reciprocity',0)+.08*r.get('respect',0)+.06*r.get('warmth',0)-.10*r.get('tension',0)
  last=int(r.get('last_direct_cycle') or 0); gap=max(0,cycle-last); novelty=min(1.,gap/40.)
  recent=sum(1 for x in r.get('events',[]) if int(x.get('cycle',-999999))>=cycle-24); saturation=min(.42,.045*recent)
  jitter=randomish(e,o,cycle)
  scored.append((.18+.55*strength+.38*novelty-saturation+jitter,o))
 return max(scored)[1]
def randomish(e,o,cycle):
 import hashlib
 n=int(hashlib.sha256(f'{e}:{o}:{cycle}'.encode()).hexdigest()[:8],16)
 return (n%1000)/10000.0
def relationship_view(M,e,o):
 r=M['entities'][e]['people'][o]; return {k:r.get(k) for k in REL_KEYS}|{'direct_turns':r.get('direct_turns',0),'repair_successes':r.get('repair_successes',0),'shared_references':list(r.get('shared_references',[]))[-8:]}
def deepest_available_detail(t,ms): return (t or {}).get('current_facet') or (topic_terms_from_messages(ms,episode_id=(t or {}).get('id')) or ['detail'])[0]
def plan_actions(order,qtarget,M,t,cycle):
 roles=['answer','deepen','compare','callback']; plans={}; used=set()
 for i,e in enumerate(order):
  action='answer' if e==qtarget else roles[i%len(roles)]
  if action in used and e!=qtarget: action=next((x for x in roles if x not in used),'deepen')
  used.add(action); partner=qtarget if qtarget in PARTICIPANTS and qtarget!=e else choose_partner(e,M,t,cycle); plans[e]={'action':action,'target':partner,'topic_facet':(t or {}).get('current_facet'),'relationship':relationship_view(M,e,partner),'mandatory_speech':True}
 return plans
def audit_invariants(M,t):
 migrate_minds(M)
 for e in ORDER:
  for o in PARTICIPANTS:
   if e==o:continue
   for k in REL_KEYS:
    if not 0<=float(M['entities'][e]['people'][o].get(k,0))<=1: raise AssertionError(f'{e}->{o} {k} out of range')
 if t is not None and not isinstance(t.get('facets',[]),list): raise AssertionError('topic facets must be a list')
 if t is not None and not isinstance(t.get('branches',[]),list): raise AssertionError('topic branches must be a list')
 return True