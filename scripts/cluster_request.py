#!/usr/bin/env python3
import base64, json, os, re, sys
from discovery_cluster import key as concept_key, resolve_root_facets
from genealogy_cluster import build_public_ancestry

JOB_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{5,80}$')
KEY_RE = re.compile(r'^([a-z0-9_]+)\s*:\s*(.+?)\s*$')
ALLOWED = {('discovery','conceptual_bridge'),('genealogy','relatedness')}


def parse_issue_request(body: str):
    fields = {}
    for raw in (body or '').splitlines():
        m = KEY_RE.match(raw.strip())
        if m: fields[m.group(1)] = m.group(2)
    job_id = fields.get('job_id','').strip().lower()
    project = fields.get('project','').strip().lower()
    task = fields.get('task','').strip().lower()
    payload_b64 = fields.get('payload_b64','').strip()
    if not JOB_RE.fullmatch(job_id): raise ValueError('invalid job_id')
    if (project, task) not in ALLOWED: raise ValueError(f'unsupported shared job: {project}/{task}')
    try:
        payload = json.loads(base64.b64decode(payload_b64, validate=True).decode('utf-8'))
    except Exception as e:
        raise ValueError('invalid payload_b64') from e
    if not isinstance(payload, dict): raise ValueError('payload must be an object')

    if project=='discovery':
        terms = payload.get('terms')
        if not isinstance(terms, list) or not (2 <= len(terms) <= 4): raise ValueError('discovery job requires 2-4 terms')
        cleaned = []
        for term in terms:
            if not isinstance(term, str): raise ValueError('terms must be strings')
            t = ' '.join(term.split()).strip()
            if not (1 <= len(t) <= 100): raise ValueError('term length out of range')
            cleaned.append(t)
        payload['terms'] = cleaned
        payload['max_depth'] = max(3, min(7, int(payload.get('max_depth', 6))))

        facets = {}
        for term in cleaned:
            rows = resolve_root_facets(term, 20)
            facets[concept_key(term)] = rows
            labels = ', '.join(x.get('label','') for x in rows[:8]) or '(none)'
            print(f'RESOLVED {term}: {labels}', file=sys.stderr)
        payload['root_facets'] = facets

    elif project=='genealogy':
        names=payload.get('names')
        if not isinstance(names,list) or not (2<=len(names)<=6): raise ValueError('genealogy job requires 2-6 people')
        cleaned=[]
        for name in names:
            if not isinstance(name,str):raise ValueError('genealogy names must be strings')
            n=' '.join(name.split()).strip()
            if not (2<=len(n)<=120):raise ValueError('genealogy name length out of range')
            cleaned.append(n)
        generations=max(2,min(10,int(payload.get('max_generations',8))))
        graph=build_public_ancestry(cleaned,generations)
        payload=graph
        for p in graph['targets']:
            by=f" ({p['birth_year']})" if p.get('birth_year') else ''
            print(f"RESOLVED {p['query']}: {p['label']}{by} [{p['id']}]",file=sys.stderr)
        print(f"GENEALOGY GRAPH: {graph['graph_nodes']} people, {graph['graph_edges']} parent edges, {generations} generations",file=sys.stderr)

    return {
        'schema': 3,
        'job_id': job_id,
        'project': project,
        'task': task,
        'payload': payload,
        'issue_number': int(os.getenv('ISSUE_NUMBER','0') or 0),
    }


def encode_request(req):
    raw = json.dumps(req, separators=(',',':'), ensure_ascii=False).encode('utf-8')
    return base64.b64encode(raw).decode('ascii')


def main():
    mode = os.getenv('EVENT_NAME','workflow_dispatch')
    if mode == 'issues':
        req = parse_issue_request(os.getenv('CLUSTER_REQUEST',''))
        print('mode=shared')
        print('workload=shared_job')
        print('scale=1')
        print('job_id=' + req['job_id'])
        print('request_b64=' + encode_request(req))
    else:
        workload = os.getenv('MANUAL_WORKLOAD','montecarlo').strip()
        if workload not in {'montecarlo','primes','hashstorm'}: raise ValueError('unsupported manual workload')
        scale = max(1, min(20, int(os.getenv('MANUAL_SCALE','5'))))
        print('mode=manual')
        print('workload=' + workload)
        print('scale=' + str(scale))
        print('job_id=manual-' + os.getenv('GITHUB_RUN_ID','local'))
        print('request_b64=')

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print(f'cluster request rejected: {e}', file=sys.stderr)
        raise
