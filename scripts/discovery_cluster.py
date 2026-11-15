#!/usr/bin/env python3
import hashlib, json, random, re, signal, time, urllib.parse, urllib.request

UA='Things-Universe-Shared-Cluster/3.1 (+https://github.com/maaronfanberg-lab/me-)'
GENERIC={'thing','things','object','objects','entity','entities','concept','concepts','system','systems','process','processes','subject','subjects','topic','topics','stuff','something','phenomenon','phenomena','category','categories','item','items','property','properties','type','types','kind','kinds'}
DROP_CAT=re.compile(r'\b(wikipedia|articles|pages|templates|stubs?|lists?|by year|by country|births|deaths|works by|albums by|songs by|films by|people from|members of)\b',re.I)
LITERARY={'children\'s literature','picture book','literature','book','narrative','text'}
INCOMPATIBLE_WITH_LITERARY={'music','film','album','song','go-go','video game','game'}

LENSES=[
 ('language',{'language','meaning','word','symbol','communication','story','narrative','literature','text'}),
 ('ethics',{'ethics','moral','morality','value','rule','authority','justice','choice'}),
 ('mind',{'mind','thought','emotion','feeling','memory','attention','cognition','belief','perception'}),
 ('culture',{'culture','society','tradition','art','literature','education','play','ritual','history'}),
 ('causal',{'cause','effect','influence','produce','result','change','behavior','action','consequence'}),
 ('structure',{'part','whole','class','category','structure','pattern','form','relation'}),
 ('aesthetic',{'art','beauty','style','play','absurdity','humor','imagination','creativity','symbol'}),
 ('knowledge',{'knowledge','reason','reasoning','evidence','truth','belief','learning','inference','philosophy'}),
 ('social',{'social','person','people','trust','relationship','power','authority','norm','community'}),
 ('science',{'science','biology','brain','chemistry','physics','mathematics','neuron','dopamine','nature'}),
 ('function',{'use','purpose','function','goal','tool','support','require','practice','method'}),
 ('wide',set()),
]

ATLAS={
 'philosophy':[('reasoning','studies and uses'),('knowledge','studies'),('ethics','includes'),('meaning','examines'),('language','examines'),('mind','examines'),('truth','examines'),('aesthetics','includes')],
 'literature':[('language','uses'),('narrative','often uses'),('meaning','conveys'),('culture','is part of'),('art','is a form of')],
 "children's literature":[('literature','is a kind of'),('education','can support'),('narrative','often uses'),('play','can use'),('imagination','can cultivate')],
 'picture book':[("children's literature",'is a kind of'),('visual art','combines with text'),('narrative','often presents')],
 'book':[('literature','can be a form of'),('text','contains'),('narrative','can present'),('language','uses')],
 'text':[('language','uses'),('meaning','can convey'),('communication','can support')],
 'narrative':[('story','is closely related to'),('meaning','can convey'),('language','can be expressed through'),('culture','can transmit')],
 'story':[('narrative','is a form of'),('meaning','can convey'),('memory','can organize'),('culture','can transmit')],
 'language':[('meaning','expresses'),('communication','supports'),('symbol','uses'),('thought','can shape')],
 'meaning':[('interpretation','depends on'),('language','can be expressed through'),('philosophy','is examined by')],
 'ethics':[('morality','studies'),('value','examines'),('choice','evaluates'),('consequence','can consider'),('philosophy','is a branch of')],
 'morality':[('ethics','is studied by'),('rule','can involve'),('value','depends on'),('behavior','can guide')],
 'rule':[('authority','can be enforced by'),('behavior','can guide'),('morality','can reflect'),('norm','is related to')],
 'authority':[('power','is related to'),('rule','can enforce'),('social norm','can shape'),('ethics','can be evaluated by')],
 'play':[('imagination','uses'),('learning','can support'),('rule','can involve'),('creativity','supports')],
 'absurdity':[('humor','can produce'),('meaning','can challenge'),('logic','can violate'),('art','can use')],
 'imagination':[('creativity','supports'),('thought','is a form of'),('play','supports'),('narrative','can generate')],
 'art':[('culture','is part of'),('meaning','can convey'),('symbol','can use'),('aesthetics','is studied by')],
 'aesthetics':[('beauty','examines'),('art','examines'),('philosophy','is a branch of')],
 'emotion':[('feeling','is related to'),('brain','involves'),('behavior','can influence'),('memory','can influence')],
 'love':[('emotion','is a kind of'),('attachment','can involve'),('trust','can involve'),('dopamine','can involve')],
 'fear':[('emotion','is a kind of'),('threat','can respond to'),('brain','involves'),('behavior','can influence')],
 'peace':[('conflict','is opposed to'),('trust','can depend on'),('cooperation','can support'),('justice','can support')],
 'dopamine':[('neurotransmitter','is a kind of'),('brain','acts in'),('motivation','can influence'),('reward','is involved in')],
 'neurotransmitter':[('brain','acts in'),('neuron','is released by'),('chemical signaling','supports')],
 'brain':[('mind','supports'),('cognition','supports'),('emotion','supports'),('neuron','contains')],
 'memory':[('learning','supports'),('brain','depends on'),('meaning','can organize'),('identity','can influence')],
 'trust':[('relationship','supports'),('social interaction','affects'),('cooperation','supports'),('risk','can involve')],
 'music':[('sound','uses'),('rhythm','uses'),('emotion','can evoke'),('mathematics','can relate to'),('art','is a form of')],
 'mathematics':[('pattern','studies'),('reasoning','uses'),('number','studies'),('structure','studies')],
 'fungus':[('organism','is a kind of'),('ecosystem','participates in'),('decomposition','can perform'),('symbiosis','can form')],
 'economics':[('scarcity','studies'),('choice','studies'),('value','studies'),('resource','studies'),('social science','is a kind of')],
}

ANCHORS=[
 (re.compile(r"\bchildren'?s (?:book|books|literature)\b",re.I),"children's literature"),
 (re.compile(r'\bpicture book\b',re.I),'picture book'),
 (re.compile(r'\b(?:novel|novella|literary|literature)\b',re.I),'literature'),
 (re.compile(r'\bbook\b',re.I),'book'),
 (re.compile(r'\b(?:story|stories|narrative)\b',re.I),'narrative'),
 (re.compile(r'\b(?:film|movie|cinema)\b',re.I),'film'),
 (re.compile(r'\b(?:song|album|music|musical)\b',re.I),'music'),
 (re.compile(r'\b(?:painting|sculpture|visual art|artwork)\b',re.I),'art'),
 (re.compile(r'\b(?:philosopher|philosophical)\b',re.I),'philosophy'),
 (re.compile(r'\b(?:mathematical|mathematician)\b',re.I),'mathematics'),
 (re.compile(r'\b(?:economist|economic|economics)\b',re.I),'economics'),
 (re.compile(r'\b(?:brain|neural|neuron|neuroscience)\b',re.I),'brain'),
 (re.compile(r'\b(?:emotion|emotional)\b',re.I),'emotion'),
]

REL={
 'IsA':('is a kind of','includes'),'PartOf':('is part of','contains'),'HasA':('has','is part of'),
 'UsedFor':('is used for','can use'),'CapableOf':('can','can be done by'),'Causes':('can cause','can result from'),
 'HasProperty':('has property','is a property of'),'RelatedTo':('is related to','is related to'),
 'Synonym':('is synonymous with','is synonymous with'),'Antonym':('is opposed to','is opposed to'),
 'DerivedFrom':('is derived from','can give rise to'),'FormOf':('is a form of','has form'),
 'MotivatedByGoal':('can be motivated by','can motivate'),'CausesDesire':('can create desire for','can be desired because of'),
 'HasPrerequisite':('requires','can enable'),'HasSubevent':('can include','can be part of'),
 'MannerOf':('is a manner of','can be expressed as'),'SimilarTo':('is similar to','is similar to'),
 'DistinctFrom':('is distinct from','is distinct from'),
}
WD_PROPS={'P31':('is an instance of','has instance'),'P279':('is a subclass of','has subclass'),'P136':('has genre','is genre of'),'P921':('has main subject','is main subject of'),'P361':('is part of','contains'),'P527':('has part','is part of'),'P1269':('is a facet of','has facet'),'P1552':('has characteristic','characterizes')}


def key(s): return re.sub(r'\s+',' ',str(s or '').strip().lower())
def cap(s):
    s=' '.join(str(s or '').split()); return s[:1].upper()+s[1:] if s else s


def fetch_json(url,timeout=2.5):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode('utf-8','replace'))
    except Exception: return None


def reverse_relation(rel):
    table={'examines':'is examined by','includes':'is included in','uses':'is used by','conveys':'can be conveyed by','is a kind of':'includes','is part of':'contains','is a form of':'has form','supports':'is supported by','studies':'is studied by','studies and uses':'is studied and used by','often uses':'is often used by','can support':'can be supported by','can cultivate':'can be cultivated by','can use':'can be used by','can present':'can be presented by','contains':'is contained by','expresses':'is expressed by','can be expressed through':'can express','is examined by':'examines','is a branch of':'includes'}
    return table.get(rel,'is conceptually linked to')


def edge(label,rel,rev=None,score=200,source='conceptual source'):
    return {'k':key(label),'label':cap(label),'rel':rel,'rev':rev or reverse_relation(rel),'score':float(score),'source':source}


def atlas(term):
    out=[];t=key(term)
    for label,rel in ATLAS.get(t,[]): out.append(edge(label,rel,score=350,source='conceptual bridge atlas'))
    for src,rows in ATLAS.items():
        for label,rel in rows:
            if key(label)==t: out.append(edge(src,reverse_relation(rel),rel,300,'conceptual bridge atlas'))
    return out


def anchor_edges(text,source):
    out=[];seen=set()
    for pat,label in ANCHORS:
        if pat.search(text or '') and key(label) not in seen:
            seen.add(key(label)); out.append(edge(label,'is grounded as','can describe',430,source))
    return out


def conceptnet(term,limit=45):
    node='/c/en/'+urllib.parse.quote(key(term).replace(' ','_'))
    j=fetch_json('https://api.conceptnet.io/query?node='+node+'&limit='+str(limit));out=[];t=key(term)
    for e in (j or {}).get('edges',[]):
        rn=str((e.get('rel') or {}).get('@id','')).split('/')[-1]
        if rn not in REL: continue
        st=e.get('start') or {};en=e.get('end') or {};sk=key(st.get('label'));ek=key(en.get('label'));forward=sk==t
        if not forward and ek!=t: continue
        other=en if forward else st;oid=str(other.get('@id',''));lab=other.get('label')
        if not oid.startswith('/c/en/') or not lab or len(lab)>70: continue
        ok=key(lab)
        if not ok or ok==t: continue
        rel,rev=REL[rn]
        if not forward: rel,rev=rev,rel
        weight=float(e.get('weight') or 1.0);out.append(edge(lab,rel,rev,215+min(50,weight*12),'ConceptNet'))
    return out


def wikidata_root(term):
    q=urllib.parse.quote(term)
    s=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbsearchentities&format=json&language=en&type=item&limit=8&search='+q)
    hits=(s or {}).get('search',[])
    if not hits:return[]
    t=key(term)
    def hit_score(h):
        lab=key(h.get('label'));score=0
        if lab==t:score+=100
        if lab==key('the '+term):score+=75
        if t and (t in lab or lab in t):score+=35
        desc=key(h.get('description'))
        if any(w in desc for w in ('book','literary','novel','film','song','album','philosoph')):score+=12
        return score
    hit=max(hits,key=hit_score);qid=hit.get('id');out=anchor_edges(str(hit.get('description') or ''),'Wikidata description')
    if not qid:return out
    data=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbgetentities&format=json&languages=en&props=claims&ids='+qid)
    claims=((data or {}).get('entities',{}).get(qid,{}) or {}).get('claims',{});refs=[]
    for prop,(rel,rev) in WD_PROPS.items():
        for c in (claims.get(prop) or [])[:10]:
            v=(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {})
            if isinstance(v,dict) and v.get('id'):refs.append((v['id'],rel,rev))
    ids=[]
    for qid2,_,_ in refs:
        if qid2 not in ids:ids.append(qid2)
    if ids:
        labels=fetch_json('https://www.wikidata.org/w/api.php?origin=*&action=wbgetentities&format=json&languages=en&props=labels|descriptions&ids='+urllib.parse.quote('|'.join(ids[:36]),safe='|'))
        ents=(labels or {}).get('entities',{})
        for qid2,rel,rev in refs:
            ent=ents.get(qid2,{}) or {};lab=((ent.get('labels',{}).get('en',{}) or {}).get('value'))
            if lab and key(lab)!=t and len(lab)<=70:
                out.append(edge(lab,rel,rev,340,'Wikidata'))
                desc=str((ent.get('descriptions',{}).get('en',{}) or {}).get('value') or '')
                out.extend(anchor_edges(lab+' '+desc,'Wikidata grounding'))
    return out


def wikipedia_root(term):
    params={'action':'query','format':'json','generator':'search','gsrsearch':term,'gsrlimit':'3','prop':'extracts|categories','exintro':'1','explaintext':'1','cllimit':'50','origin':'*'}
    j=fetch_json('https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode(params));pages=list(((j or {}).get('query') or {}).get('pages',{}).values());out=[]
    if not pages:return out
    pages.sort(key=lambda p:p.get('index',999))
    for page in pages[:2]:
        text=(page.get('title','')+' '+page.get('extract',''))[:4000];out.extend(anchor_edges(text,'Wikipedia description'))
        for c in page.get('categories',[]):
            lab=str(c.get('title','')).replace('Category:','').strip()
            if not lab or len(lab)>70 or DROP_CAT.search(lab):continue
            out.extend(anchor_edges(lab,'Wikipedia category'))
    return out


def merge_edges(groups):
    best={}
    for group in groups:
        for e in group:
            if not e.get('k') or e['k'] in GENERIC:continue
            old=best.get(e['k'])
            if old is None or e['score']>old['score']:best[e['k']]=e
    return list(best.values())


def resolve_root_facets(term,limit=20):
    """Resolve one input meaning once. This packet is broadcast to all 12 workers."""
    wiki=wikipedia_root(term);wd=wikidata_root(term);cn=conceptnet(term,32);rows=merge_edges([atlas(term),wiki,wd,cn])
    wiki_keys={e['k'] for e in wiki}
    if len(wiki_keys & LITERARY)>=2:
        rows=[e for e in rows if e['k'] not in INCOMPATIBLE_WITH_LITERARY]
    rows.sort(key=lambda e:e.get('score',0),reverse=True)
    return [{k:e[k] for k in ('k','label','rel','rev','score','source')} for e in rows[:limit]]


def lens_score(e,lens_words,depth,jitter=0):
    k=e['k'];lab=key(e['label']);rel=key(e['rel']);s=float(e.get('score',200))-depth*20
    if k in GENERIC:s-=180
    if len(k)<=2:s-=80
    if lens_words and any(w in lab or w in rel for w in lens_words):s+=48
    if e.get('source')=='Wikidata':s+=22
    if e.get('source') in {'Wikipedia description','Wikidata description','Wikidata grounding','Wikipedia category'}:s+=18
    return s+jitter


def expand_search(term,lens_words,rng,cache,allow_network):
    ck=(key(term),tuple(sorted(lens_words)),bool(allow_network))
    if ck in cache:return cache[ck]
    groups=[atlas(term)]
    if allow_network:groups.append(conceptnet(term,28))
    rows=merge_edges(groups)
    for e in rows:e['_j']=rng.uniform(-5,5)
    rows.sort(key=lambda e:lens_score(e,lens_words,0,e['_j']),reverse=True);cache[ck]=rows;return rows


def seed_side(term,facets,labels,lens_words,rng):
    root=key(term);own={root:{'parent':None,'edge':None,'score':0.0,'depth':0}};front=[]
    for raw in facets or []:
        e=dict(raw);nk=e.get('k') or key(e.get('label'))
        if not nk or nk==root or nk in GENERIC:continue
        e['k']=nk;e.setdefault('label',cap(nk));e.setdefault('rel','is grounded as');e.setdefault('rev','can describe');e.setdefault('score',250);e.setdefault('source','semantic coordinator')
        labels.setdefault(nk,e['label']);score=lens_score(e,lens_words,1,rng.uniform(-3,3))
        if nk not in own or score>own[nk]['score']:
            own[nk]={'parent':root,'edge':e,'score':score,'depth':1};front.append(nk)
    if not front:
        for e in atlas(term)[:10]:
            nk=e['k'];labels.setdefault(nk,e['label']);score=lens_score(e,lens_words,1,rng.uniform(-3,3));own[nk]={'parent':root,'edge':e,'score':score,'depth':1};front.append(nk)
    return own,list(dict.fromkeys(front))


def reconstruct(meet,left,right,labels):
    nodes=[];cur=meet
    while cur is not None:
        nodes.append(cur);cur=left[cur]['parent'] if cur in left else None
    nodes.reverse();edges=[]
    for i in range(len(nodes)-1):
        rec=left[nodes[i+1]];edges.append({'a':labels[nodes[i]],'b':labels[nodes[i+1]],'rel':rec['edge']['rel'],'source':rec['edge']['source']})
    cur=meet
    while cur in right and right[cur]['parent'] is not None:
        rec=right[cur];parent=rec['parent'];edges.append({'a':labels[cur],'b':labels[parent],'rel':rec['edge'].get('rev') or 'is conceptually linked to','source':rec['edge']['source']});cur=parent
    return edges


def path_penalty(edges):
    p=max(0,len(edges)-4)*35
    for e in edges:
        if key(e['a']) in GENERIC or key(e['b']) in GENERIC:p+=160
        if e['rel']=='is conceptually linked to':p+=16
    return p


def consider_meets(meets,left,right,labels,best,max_depth,lens_name,expanded):
    for m in set(meets):
        if m not in left or m not in right:continue
        edges=reconstruct(m,left,right,labels)
        if not edges or len(edges)>max_depth:continue
        score=left[m]['score']+right[m]['score']-path_penalty(edges)
        cand={'edges':edges,'score':round(score,3),'lens':lens_name,'expanded':expanded}
        if best is None or cand['score']>best['score']:best=cand
    return best


def grow(front,own,other,labels,lens_words,rng,cache,beam,branch,allow_network,deadline,budget):
    next_scores={};meets=[];expanded=0
    for cur in sorted(front,key=lambda k:own[k]['score'],reverse=True)[:beam]:
        if time.monotonic()>=deadline or expanded>=budget:break
        rec=own[cur];rows=expand_search(labels.get(cur,cur),lens_words,rng,cache,allow_network)[:branch];expanded+=1
        for e in rows:
            nk=e['k'];labels.setdefault(nk,e['label']);nd=rec['depth']+1;ns=rec['score']+lens_score(e,lens_words,nd,e.get('_j',0));old=own.get(nk)
            if old is None or ns>old['score']:
                own[nk]={'parent':cur,'edge':e,'score':ns,'depth':nd};next_scores[nk]=max(next_scores.get(nk,-1e9),ns)
            if nk in other:meets.append(nk)
    return [k for k,_ in sorted(next_scores.items(),key=lambda kv:kv[1],reverse=True)],meets,expanded


def run_search(a,b,worker,max_depth,root_facets,allow_network,seconds,budget):
    lens_name,lens_words=LENSES[worker%len(LENSES)];seed=int(hashlib.sha256((key(a)+'|'+key(b)+'|'+str(worker)+'|'+str(allow_network)).encode()).hexdigest()[:12],16);rng=random.Random(seed);cache={};ka,kb=key(a),key(b);labels={ka:cap(a),kb:cap(b)}
    packet=root_facets or {};left,fl=seed_side(a,packet.get(ka),labels,lens_words,rng);right,fr=seed_side(b,packet.get(kb),labels,lens_words,rng)
    best=consider_meets(set(left)&set(right),left,right,labels,None,max_depth,lens_name,0);expanded=0
    if best and len(best['edges'])<=3:return {'from':a,'to':b,**best}
    deadline=time.monotonic()+seconds;beam=6+(worker%3);branch=12+(worker%4)*2
    while (fl or fr) and expanded<budget and time.monotonic()<deadline:
        if fl:
            fl,meets,z=grow(fl,left,right,labels,lens_words,rng,cache,beam,branch,allow_network,deadline,budget-expanded);expanded+=z
            best=consider_meets(meets,left,right,labels,best,max_depth,lens_name,expanded)
            if best and len(best['edges'])<=4:break
        if fr and expanded<budget and time.monotonic()<deadline:
            fr,meets,z=grow(fr,right,left,labels,lens_words,rng,cache,beam,branch,allow_network,deadline,budget-expanded);expanded+=z
            best=consider_meets(meets,left,right,labels,best,max_depth,lens_name,expanded)
            if best and len(best['edges'])<=4:break
    if best:return {'from':a,'to':b,**best,'expanded':expanded}
    return {'from':a,'to':b,'edges':[],'score':-9999,'lens':lens_name,'expanded':expanded}


def search_pair(a,b,worker,max_depth=6,root_facets=None):
    if key(a)==key(b):return {'from':a,'to':b,'edges':[],'score':10000,'lens':LENSES[worker%len(LENSES)][0],'expanded':0}
    local=run_search(a,b,worker,max_depth,root_facets,False,2.0,40)
    if local.get('edges'):
        local['mode']='local-first';return local
    old_handler=signal.getsignal(signal.SIGALRM)
    def timeout_handler(_sig,_frame):raise TimeoutError('bounded external search expired')
    try:
        signal.signal(signal.SIGALRM,timeout_handler);signal.alarm(24)
        remote=run_search(a,b,worker,max_depth,root_facets,True,20.0,12);remote['mode']='bounded-external';return remote
    except TimeoutError:
        local['mode']='external-timeout';return local
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old_handler)


def worker_result(request,worker):
    payload=request['payload'];terms=payload['terms'];pairs=[(terms[i],terms[j]) for i in range(len(terms)) for j in range(i+1,len(terms))];a,b=pairs[worker%len(pairs)]
    path=search_pair(a,b,worker,payload.get('max_depth',6),payload.get('root_facets') or {})
    return {'project':'discovery','task':'conceptual_bridge','job_id':request['job_id'],'terms':terms,'pair':[a,b],'path':path,'strategy':path.get('lens'),'units':path.get('expanded',0)}
