#!/usr/bin/env python3
import hashlib, json, re, urllib.parse, urllib.request
from collections import defaultdict, deque

UA='Genealogy-Kinship-Shared-Cluster/1.1 (+https://github.com/maaronfanberg-lab/me-)'
HUMAN_QID='Q5'
MAX_GRAPH_NODES=2500


def fetch_json(url, timeout=4.0):
    req=urllib.request.Request(url, headers={'User-Agent':UA,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8','replace'))
    except Exception:
        return None


def chunks(items,n=35):
    for i in range(0,len(items),n):yield items[i:i+n]


def year_from_value(v):
    if not isinstance(v,dict):return None
    m=re.match(r'^[+-](\d{4,})-',str(v.get('time') or ''))
    return int(m.group(1)) if m else None


def claim_entity_ids(claims,prop):
    out=[]
    for c in claims.get(prop,[]) or []:
        v=(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {})
        if isinstance(v,dict) and v.get('id'):out.append(v['id'])
    return out


def birth_year(claims):
    for c in claims.get('P569',[]) or []:
        y=year_from_value(((c.get('mainsnak') or {}).get('datavalue') or {}).get('value'))
        if y is not None:return y
    return None


def fetch_entities(ids):
    out={}
    for batch in chunks(list(dict.fromkeys(ids))):
        if not batch:continue
        url='https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({
            'origin':'*','action':'wbgetentities','format':'json','languages':'en',
            'props':'labels|descriptions|claims','ids':'|'.join(batch)
        })
        out.update((fetch_json(url) or {}).get('entities',{}) or {})
    return out


def parse_query(raw):
    text=' '.join(str(raw or '').split()).strip();year=None
    m=re.search(r'(?:\(|\b)(1[0-9]{3}|20[0-9]{2})(?:\)|\b)',text)
    if m:
        year=int(m.group(1));name=(text[:m.start()]+text[m.end():]).replace('()',' ').strip(' ,-');name=' '.join(name.split()) or text
    else:name=text
    return name,year


def resolve_person(raw):
    name,wanted_year=parse_query(raw)
    url='https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({
        'origin':'*','action':'wbsearchentities','format':'json','language':'en','type':'item','limit':'8','search':name
    })
    hits=(fetch_json(url) or {}).get('search',[]) or []
    if not hits:raise ValueError(f'No Wikidata person found for {raw}')
    entities=fetch_entities([h.get('id') for h in hits if h.get('id')]);best=None
    for rank,h in enumerate(hits):
        qid=h.get('id');ent=entities.get(qid,{}) or {};claims=ent.get('claims',{}) or {};types=claim_entity_ids(claims,'P31')
        label=((ent.get('labels',{}).get('en',{}) or {}).get('value')) or h.get('label') or name
        desc=((ent.get('descriptions',{}).get('en',{}) or {}).get('value')) or h.get('description') or ''
        by=birth_year(claims);score=120-rank*8
        if label.casefold()==name.casefold():score+=90
        score+=90 if HUMAN_QID in types else -110
        if any(x in desc.casefold() for x in ('family name','given name','disambiguation page','wikimedia list')):score-=120
        if wanted_year is not None:
            if by==wanted_year:score+=150
            elif by is not None:score-=min(90,abs(by-wanted_year)*4)
        cand={'id':qid,'label':label,'description':desc,'birth_year':by,'query':raw,'score':score}
        if best is None or cand['score']>best['score']:best=cand
    if best is None or best['score']<0:raise ValueError(f'Could not confidently resolve {raw} as a person')
    best.pop('score',None);return best


def build_public_ancestry(raw_names,max_generations=8):
    targets=[];seen_target=set()
    for raw in raw_names:
        p=resolve_person(raw)
        if p['id'] in seen_target:continue
        seen_target.add(p['id']);targets.append(p)
    if len(targets)<2:raise ValueError('Genealogy comparison needs at least two distinct people')

    people={p['id']:{'l':p['label'],'y':p.get('birth_year')} for p in targets}
    edges=[];edge_seen=set();frontier={p['id'] for p in targets};visited=set();depth=0
    while frontier and depth<max_generations and len(people)<MAX_GRAPH_NODES:
        ids=[x for x in frontier if x not in visited]
        if not ids:break
        ents=fetch_entities(ids);next_front=set()
        for qid in ids:
            visited.add(qid);ent=ents.get(qid,{}) or {};claims=ent.get('claims',{}) or {};old=people.get(qid,{})
            label=((ent.get('labels',{}).get('en',{}) or {}).get('value')) or old.get('l') or qid
            people[qid]={'l':label,'y':birth_year(claims) or old.get('y')}
            for prop in ('P22','P25'):
                for parent in claim_entity_ids(claims,prop)[:1]:
                    ek=(qid,parent)
                    if ek not in edge_seen:edge_seen.add(ek);edges.append([qid,parent])
                    if parent not in visited:next_front.add(parent)
                    people.setdefault(parent,{'l':parent,'y':None})
                    if len(people)>=MAX_GRAPH_NODES:break
        frontier=next_front;depth+=1

    missing=[qid for qid,v in people.items() if v.get('l')==qid]
    if missing:
        for qid,ent in fetch_entities(missing).items():
            people[qid]={'l':((ent.get('labels',{}).get('en',{}) or {}).get('value')) or qid,'y':birth_year(ent.get('claims',{}) or {})}

    return {
        'targets':targets,'parent_edges':edges,'people':people,'max_generations':max_generations,
        'source':'Wikidata father/mother statements (P22/P25)','graph_nodes':len(people),'graph_edges':len(edges),
    }


def ancestry_distances(start,parents,max_depth):
    dist={start:0};q=deque([start])
    while q:
        cur=q.popleft();d=dist[cur]
        if d>=max_depth:continue
        for p in parents.get(cur,()):
            if p not in dist or d+1<dist[p]:dist[p]=d+1;q.append(p)
    return dist


def shard_slots(value,workers):
    h=hashlib.sha256(value.encode()).digest();a=int.from_bytes(h[:4],'big')%workers;b=int.from_bytes(h[4:8],'big')%workers
    if b==a:b=(a+1)%workers
    return {a,b}


def worker_result(request,worker):
    payload=request['payload'];targets=payload['targets'];people=payload.get('people') or {};max_depth=int(payload.get('max_generations',8));workers=12
    parents=defaultdict(list)
    for row in payload.get('parent_edges') or []:
        if len(row)>=2:parents[row[0]].append(row[1])
    maps={t['id']:ancestry_distances(t['id'],parents,max_depth) for t in targets};pairs=[];units=0
    for i in range(len(targets)):
        for j in range(i+1,len(targets)):
            a=targets[i];b=targets[j];ma=maps[a['id']];mb=maps[b['id']];common=set(ma)&set(mb);candidates=[]
            for anc in common:
                if worker not in shard_slots(anc,workers):continue
                info=people.get(anc,{}) or {}
                candidates.append({'ancestor':anc,'label':info.get('l') or anc,'birth_year':info.get('y'),'da':ma[anc],'db':mb[anc]})
            candidates.sort(key=lambda x:(max(x['da'],x['db']),x['da']+x['db'],x['label']));units+=len(common)
            pairs.append({'a':a['id'],'b':b['id'],'a_label':a['label'],'b_label':b['label'],'candidates':candidates})
    return {
        'project':'genealogy','task':'relatedness','job_id':request['job_id'],'targets':targets,'pairs':pairs,
        'source':payload.get('source'),'max_generations':max_depth,'graph_nodes':payload.get('graph_nodes'),'graph_edges':payload.get('graph_edges'),'units':units,
    }


def ordinal(n):
    if 10<=n%100<=20:s='th'
    else:s={1:'st',2:'nd',3:'rd'}.get(n%10,'th')
    return f'{n}{s}'


def direct_label(gens):
    if gens==1:return 'parent ↔ child'
    if gens==2:return 'grandparent ↔ grandchild'
    prefix='great-'*(gens-2);return prefix+'grandparent ↔ '+prefix+'grandchild'


def classify(da,db,shared_count):
    if da==0 or db==0:
        gens=max(da,db);return {'kind':'direct','generations':gens,'ancestor_side':'a' if da==0 else 'b','label':direct_label(gens)}
    if da==1 and db==1:return {'kind':'siblings','label':'siblings' if shared_count>=2 else 'siblings / possible half-siblings'}
    if min(da,db)==1:
        farther=max(da,db);greats=max(0,farther-2);prefix='great-'*greats
        return {'kind':'avuncular','greats':greats,'older_side':'a' if da==1 else 'b','label':prefix+'aunt/uncle ↔ '+prefix+'niece/nephew'}
    degree=min(da,db)-1;removal=abs(da-db);label=f'{ordinal(degree)} cousins'
    if removal==1:label+=' once removed'
    elif removal==2:label+=' twice removed'
    elif removal>2:label+=f' {removal} times removed'
    return {'kind':'cousins','degree':degree,'removal':removal,'label':label}


def aggregate(parts,expected_workers=12):
    if not parts:raise ValueError('no genealogy worker results')
    first=parts[0]['result'];targets=first.get('targets') or [];by_pair={}
    for part in parts:
        for row in (part.get('result') or {}).get('pairs') or []:
            pk=(row['a'],row['b']);bucket=by_pair.setdefault(pk,{'candidates':{}})
            for c in row.get('candidates') or []:
                old=bucket['candidates'].get(c['ancestor'])
                if old is None or (c['da']+c['db'])<(old['da']+old['db']):bucket['candidates'][c['ancestor']]=c
    out=[]
    for i in range(len(targets)):
        for j in range(i+1,len(targets)):
            a=targets[i];b=targets[j];rows=list(by_pair.get((a['id'],b['id']),{'candidates':{}})['candidates'].values())
            rows.sort(key=lambda x:(max(x['da'],x['db']),x['da']+x['db'],x['label']))
            if not rows:
                out.append({'a':a['id'],'b':b['id'],'a_label':a['label'],'b_label':b['label'],'found':False,'relationship':'No common ancestor found in the searched generations','common_ancestors':[],'expected_relatedness':None});continue
            best_rank=(max(rows[0]['da'],rows[0]['db']),rows[0]['da']+rows[0]['db']);closest=[r for r in rows if (max(r['da'],r['db']),r['da']+r['db'])==best_rank]
            da,db=closest[0]['da'],closest[0]['db'];rel=classify(da,db,len(closest));coeff=min(1.0,sum(0.5**(r['da']+r['db']) for r in closest))
            out.append({
                'a':a['id'],'b':b['id'],'a_label':a['label'],'b_label':b['label'],'found':True,'relationship':rel['label'],'relationship_data':rel,
                'distance_from_a':da,'distance_from_b':db,'common_ancestors':closest[:12],'expected_relatedness':coeff,
                'expected_relatedness_percent':round(coeff*100,4),'all_common_ancestors_found':len(rows),
            })
    return {
        'status':'complete','project':'genealogy','task':'relatedness','targets':targets,'pairs':out,'source':first.get('source'),
        'max_generations':first.get('max_generations'),'graph_nodes':first.get('graph_nodes'),'graph_edges':first.get('graph_edges'),
        'participating_workers':len(parts),'expected_workers':expected_workers,'degraded':len(parts)<expected_workers,
        'warning':'Wikidata family relationships can be incomplete. “No common ancestor found” is not proof that two people are unrelated.'
    }
