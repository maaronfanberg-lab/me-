#!/usr/bin/env python3
import base64, hashlib, json, math, os, random, time
from discovery_cluster import worker_result as discovery_worker_result
from genealogy_cluster import worker_result as genealogy_worker_result

worker = int(os.getenv('WORKER_ID','0'))
workers = int(os.getenv('WORKER_COUNT','12'))
workload = os.getenv('WORKLOAD','montecarlo')
scale = max(1, min(20, int(os.getenv('SCALE','5'))))
started = time.time()
request = None

if workload == 'shared_job':
    raw = os.getenv('CLUSTER_REQUEST_B64','')
    if not raw:
        raise SystemExit('shared_job requires CLUSTER_REQUEST_B64')
    request = json.loads(base64.b64decode(raw).decode('utf-8'))
    project=request.get('project');task=request.get('task')
    if project == 'discovery' and task == 'conceptual_bridge':
        result = discovery_worker_result(request, worker)
        units = int(result.get('units',0))
    elif project == 'genealogy' and task == 'relatedness':
        result = genealogy_worker_result(request, worker)
        units = int(result.get('units',0))
    else:
        raise SystemExit('unsupported shared job handler')
elif workload == 'montecarlo':
    n = scale * 1_000_000
    rng = random.Random(9173 + worker * 104729)
    inside = 0
    for _ in range(n):
        x, y = rng.random(), rng.random()
        inside += (x*x + y*y <= 1.0)
    result = {'samples': n, 'inside': inside}
    units = n
elif workload == 'primes':
    width = scale * 120_000
    lo = 2 + worker * width
    hi = lo + width
    count = 0
    last = 2
    for n in range(max(2, lo), hi):
        prime = True
        r = int(math.isqrt(n))
        for d in range(2, r + 1):
            if n % d == 0:
                prime = False
                break
        if prime:
            count += 1
            last = n
    result = {'range':[lo,hi], 'count':count, 'last_prime':last}
    units = width
elif workload == 'hashstorm':
    n = scale * 500_000
    h = f'cluster-{worker}'.encode()
    for i in range(n):
        h = hashlib.sha256(h + i.to_bytes(8,'little')).digest()
    result = {'iterations': n, 'digest': h.hex()}
    units = n
else:
    raise SystemExit(f'unknown workload: {workload}')

elapsed = time.time() - started
out = {
    'worker': worker,
    'workers': workers,
    'workload': workload,
    'scale': scale,
    'job_id': (request or {}).get('job_id'),
    'project': (request or {}).get('project'),
    'task': (request or {}).get('task'),
    'units': units,
    'elapsed': elapsed,
    'rate': units / elapsed if elapsed else 0,
    'result': result,
}
os.makedirs('cluster_parts', exist_ok=True)
with open(f'cluster_parts/worker-{worker:02d}.json','w') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False))
