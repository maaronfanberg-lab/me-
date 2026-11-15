#!/usr/bin/env python3
import glob, json, os, re, time
from genealogy_cluster import aggregate as aggregate_genealogy

EXPECTED_WORKERS=12
parts=[]
for p in sorted(glob.glob('cluster_parts/worker-*.json')):
    with open(p) as f: parts.append(json.load(f))
if not parts: raise SystemExit('no worker results')
workload=parts[0]['workload']
summary={
  'generated_at': int(time.time()),
  'workload': workload,
  'workers': len(parts),
  'expected_workers': EXPECTED_WORKERS,
  'missing_workers': max(0,EXPECTED_WORKERS-len(parts)),
  'degraded': len(parts)<EXPECTED_WORKERS,
  'scale': parts[0]['scale'],
  'total_units': sum(p.get('units',0) for p in parts),
  'slowest_worker_seconds': max(p.get('elapsed',0) for p in parts),
  'aggregate_rate': sum(p.get('rate',0) for p in parts),
  'parts': parts,
}

if workload=='montecarlo':
    samples=sum(p['result']['samples'] for p in parts)
    inside=sum(p['result']['inside'] for p in parts)
    summary['result']={'pi_estimate':4*inside/samples,'samples':samples}
elif workload=='primes':
    summary['result']={'prime_count':sum(p['result']['count'] for p in parts),'largest_prime':max(p['result']['last_prime'] for p in parts)}
elif workload=='hashstorm':
    summary['result']={'combined_digest':'-'.join(p['result']['digest'][:12] for p in parts)}
elif workload=='shared_job':
    job_id=parts[0].get('job_id') or ''
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{5,80}', job_id): raise SystemExit('invalid shared job id in worker results')
    project=parts[0].get('project');task=parts[0].get('task')

    if project=='discovery' and task=='conceptual_bridge':
        if len(parts)<3: raise SystemExit('too few compute nodes returned a Discovery result')
        grouped={}
        for p in parts:
            r=p.get('result') or {}; path=r.get('path') or {}; pair=tuple(r.get('pair') or [])
            if len(pair)!=2 or not path.get('edges'):continue
            sig='|'.join((e.get('a','')+'>'+e.get('rel','')+'>'+e.get('b','')) for e in path['edges'])
            bucket=grouped.setdefault(pair,{})
            old=bucket.get(sig)
            if old is None or path.get('score',-9999)>old.get('score',-9999):bucket[sig]=path
        pairs=[]
        terms=(parts[0].get('result') or {}).get('terms') or []
        for i in range(len(terms)):
            for j in range(i+1,len(terms)):
                pair=(terms[i],terms[j]); rows=sorted(grouped.get(pair,{}).values(),key=lambda x:x.get('score',-9999),reverse=True)
                pairs.append({'from':pair[0],'to':pair[1],'best':rows[0] if rows else None,'alternatives':rows[1:3]})
        result={
            'status':'complete','job_id':job_id,'project':project,'task':task,'terms':terms,
            'pairs':pairs,'successful_workers':sum(1 for p in parts if ((p.get('result') or {}).get('path') or {}).get('edges')),
            'participating_workers':len(parts),'expected_workers':EXPECTED_WORKERS,
        }
    elif project=='genealogy' and task=='relatedness':
        result=aggregate_genealogy(parts,EXPECTED_WORKERS)
        result['job_id']=job_id
    else:
        raise SystemExit('unsupported shared aggregate handler')

    summary['job_id']=job_id;summary['project']=project;summary['task']=task;summary['result']=result
    os.makedirs('cluster/jobs',exist_ok=True)
    with open(f'cluster/jobs/{job_id}.json','w') as f:json.dump(summary,f,indent=2,ensure_ascii=False)

os.makedirs('cluster', exist_ok=True)
with open('cluster/latest.json','w') as f: json.dump(summary,f,indent=2,ensure_ascii=False)
print(json.dumps(summary,indent=2,ensure_ascii=False))
