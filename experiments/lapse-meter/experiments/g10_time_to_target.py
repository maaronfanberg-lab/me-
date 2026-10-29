"""G10: float32 and float64 PathCond/Adam, validation time-to-target.
Protocol: GAUGE_G10_PREREGISTRATION.md. Uses pinned upstream primitives,
and never calls the double precision *diagnostic* the released PathCond.
"""
import copy, inspect, json, math, os, sys, time
import numpy as np
import torch
from torch.nn import functional as F
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from g6_benchmark import dataset
from g7_official_pathcond import make_model, gauge_copy
from g8_pathcond_precision import independent_double_bz

TASKS = ('digits','circle')
DEPTHS = (3,6)
SEEDS = tuple(range(90,95))
ARMS = (('f32','adam'), ('f32','official'),
        ('f64','adam'), ('f64','official'), ('f64','double_diagnostic'))
TARGETS = {'digits':.90,'circle':.90}
STEPS = 300
LR = .003
BATCH = 64
SOURCE_COMMIT = '535b202e3476c64d5e7e9ec5e817344fb5cfd787'

def configure():
    torch.set_num_threads(1)
    torch.set_default_dtype(torch.float64)

def probe_condition(model,method,x):
    """Return preprocessing seconds, max initial function error and nontriviality."""
    from pathcond.pathcond import rescaling_path_cond
    from pathcond.rescaling_polyn import reweight_model_inplace
    with torch.no_grad():
        before=model(x).clone()
        start_params=[p.detach().clone() for p in model.parameters()]
    tick=time.perf_counter()
    if method=='official':
        rescaling_path_cond(model,nb_iter_optim_rescaling=10)
    elif method=='double_diagnostic':
        if next(model.parameters()).dtype!=torch.float64:
            raise ValueError('double precision diagnostic requires float64 model')
        bz=independent_double_bz(model)
        reweight_model_inplace(model,bz)
    elif method!='adam':
        raise ValueError('unknown method')
    elapsed=time.perf_counter()-tick if method!='adam' else 0.0
    with torch.no_grad():
        changed=max(float(torch.max(torch.abs(p-q))) for p,q in zip(model.parameters(),start_params))
        d=float(torch.max(torch.abs(model(x)-before)))
    if not math.isfinite(d) or d>1e-3 or (method!='adam' and changed<=1e-12):
        raise FloatingPointError(f'Invalid preconditioning: logit drift={d}, parameter change={changed}')
    if not all(torch.isfinite(p).all() for p in model.parameters()):
        raise FloatingPointError('Nonfinite conditioned parameters')
    return dict(seconds=elapsed,initial_max_logit_error=d,max_parameter_change=changed)

def assess(model,data):
    with torch.no_grad():
        p=F.cross_entropy(model(data[0]),data[1]).item()
        accuracy=(model(data[0]).argmax(1)==data[1]).double().mean().item()
        if not math.isfinite(p):raise FloatingPointError('nonfinite CE')
        return float(p),float(accuracy)

def train_pair(task,depth,seed,dtype_name,method):
    dtype=torch.float32 if dtype_name=='f32' else torch.float64
    old_default=torch.get_default_dtype()
    torch.set_default_dtype(dtype)
    entry=dict(task=task,depth=depth,seed=seed,dtype=dtype_name,method=method,
               failed=None,training_steps=STEPS,precondition=None,initial_gauge_gap=None,
               traces={'identity':[],'neuronwise':[]},results={},final_max_logit_gap=None,
               step100=None,step300=None)
    try:
        (tr,va,te),metadata=dataset(task,seed)
        parts=[(torch.tensor(x,dtype=dtype),torch.tensor(y,dtype=torch.long)) for x,y in (tr,va,te)]
        x,y=parts[0];v=parts[1];test=parts[2]
        raw,_=make_model(x.shape[1],metadata['classes'],depth,seed)
        raw=raw.to(dtype)
        a=copy.deepcopy(raw);b=gauge_copy(raw,seed)
        with torch.no_grad():
            gap0=float((a(x[:128])-b(x[:128])).abs().max())
        entry['initial_gauge_gap']=gap0
        if not math.isfinite(gap0) or gap0>=1e-3:raise FloatingPointError('bad starting gauge')
        p1=probe_condition(a,method,x[:128])
        p2=probe_condition(b,method,x[:128])
        entry['precondition']={'identity':p1,'neuronwise':p2}
        models={'identity':a,'neuronwise':b}
        optim={name:torch.optim.Adam(net.parameters(),lr=LR,betas=(.9,.999),eps=1e-8,weight_decay=0)
               for name,net in models.items()}
        costs={name:entry['precondition'][name]['seconds'] for name in models}
        first_cross={name:None for name in models}
        rng=np.random.default_rng(10000+seed)
        for step in range(STEPS+1):
            if step%10==0:
                for name,net in models.items():
                    _,acc=assess(net,v)
                    entry['traces'][name].append(dict(step=step,val_accuracy=acc,
                                                        cum_train_seconds=float(costs[name])))
                    if first_cross[name] is None and acc>=TARGETS[task]:
                        first_cross[name]=dict(step=step,
                                               computation_seconds=float(costs[name]))
            if step in (100,300):
                cpa,aca=assess(a,test);cpb,acb=assess(b,test)
                with torch.no_grad():
                    gap=float((a(test[0])-b(test[0])).abs().max())
                entry['step'+str(step)]=dict(identity_test_ce=cpa,identity_test_accuracy=aca,
                    neuronwise_test_ce=cpb,neuronwise_test_accuracy=acb,max_test_logit_gap=gap)
            if step==STEPS:break
            ix=rng.integers(0,len(x),BATCH)
            bx,by=x[ix],y[ix]
            for name,net in models.items():
                start=time.perf_counter()
                op=optim[name]
                op.zero_grad(set_to_none=True)
                F.cross_entropy(net(bx),by).backward()
                op.step()
                costs[name]+=time.perf_counter()-start
                if not all(torch.isfinite(p).all() for p in net.parameters()):
                    raise FloatingPointError('Nonfinite parameters at '+name+' step '+str(step+1))
        entry['results']=dict(
            first_cross=first_cross,
            computation_seconds=costs,
            target_accuracy=TARGETS[task],
            identities_never_crossed=sum(first_cross[k] is None for k in models))
        entry['final_max_logit_gap']=entry['step300']['max_test_logit_gap']
    except Exception as e:
        entry['failed']=type(e).__name__+': '+str(e)[:280]
    finally:
        torch.set_default_dtype(old_default)
    return entry

def cell_stats(records,dtype,method,task,depth):
    rs=[r for r in records if (r['dtype'],r['method'],r['task'],r['depth'])==(dtype,method,task,depth)]
    assert len(rs)==5
    good=[r for r in rs if not r['failed']]
    def mean(key,step=300):
        if len(good)!=5:return None
        vals=[r['step'+str(step)][key] for r in good]
        return float(np.mean(vals)) if all(map(math.isfinite,vals)) else None
    crossings={}
    for name in ('identity','neuronwise'):
        wins=[r['results']['first_cross'][name]['computation_seconds']
              for r in good if r['results']['first_cross'][name] is not None]
        crossings[name]=dict(n_crossed=len(wins),
                             median_seconds=(float(np.median(wins)) if wins else None),
                             mean_seconds=(float(np.mean(wins)) if wins else None))
    return dict(n=5,failed=5-len(good),
                crossings=crossings,
                mean_test_ce_100=mean('identity_test_ce',100),
                mean_test_ce_300=mean('identity_test_ce',300),
                mean_accuracy_300=mean('identity_test_accuracy',300),
                mean_gauge_gap_300=mean('max_test_logit_gap',300),
                mean_total_step_time=(float(np.mean([r['results']['computation_seconds']['identity']
                      for r in good])) if len(good)==5 else None),
                init_preservation_fail_count=sum(
                    bool(r['failed']) or (r['precondition'] is not None and
                        any(v['initial_max_logit_error'] >= (1e-4 if dtype=='f32' else 1e-10)
                            for v in r['precondition'].values()))
                    for r in rs))

def summary(records):
    assert len(records)==2*2*5*5
    cells=[];h1_native=0;h1_double=0
    for r in records:
        if r['failed'] or r['precondition'] is None:continue
        if r['dtype']=='f32' and r['method']=='official':
            h1_native+=sum(p['initial_max_logit_error']<1e-4 for p in r['precondition'].values())
        if r['dtype']=='f64' and r['method']=='double_diagnostic':
            h1_double+=sum(p['initial_max_logit_error']<1e-10 for p in r['precondition'].values())
    for task in TASKS:
      for depth in DEPTHS:
        stats={dtype+'_'+method:cell_stats(records,dtype,method,task,depth)
               for dtype,method in ARMS}
        a=stats['f32_adam'];b=stats['f32_official']
        ac=a['crossings']['identity'];bc=b['crossings']['identity']
        timewin=(a['failed']==0 and b['failed']==0 and ac['n_crossed']>=4 and
                 bc['n_crossed']>=4 and bc['median_seconds']<ac['median_seconds'])
        gapwin=(a['failed']==0 and b['failed']==0 and
                a['mean_gauge_gap_300'] is not None and b['mean_gauge_gap_300'] is not None and
                b['mean_gauge_gap_300']<a['mean_gauge_gap_300'])
        accwin=(a['failed']==0 and b['failed']==0 and
                a['mean_accuracy_300'] is not None and b['mean_accuracy_300'] is not None and
                b['mean_accuracy_300']>=a['mean_accuracy_300']-.01)
        cells.append(dict(task=task,depth=depth,arms=stats,
                          h2_time_win=bool(timewin),h3_robustness_win=bool(gapwin),
                          h4_accuracy_noninferior=bool(accwin)))
    n2=sum(c['h2_time_win'] for c in cells)
    n3=sum(c['h3_robustness_win'] for c in cells)
    n4=sum(c['h4_accuracy_noninferior'] for c in cells)
    return dict(n_pair_runs=len(records),n_trajectories=2*len(records),
                n_failed_pairs=sum(bool(r['failed']) for r in records),
                h1_fp32_n=h1_native,h1_double_n=h1_double,
                h1_pass=(h1_native==40 and h1_double==40),
                h2_time_win_cells=n2,h2_pass=n2>=3,
                h3_robust_win_cells=n3,h3_pass=n3>=3,
                h4_noninferior_cells=n4,h4_pass=n4>=3,cells=cells)

def run(seeds=SEEDS):
    configure()
    from pathcond.pathcond import rescaling_path_cond
    assert 'pathcond' in inspect.getfile(rescaling_path_cond).lower()
    records=[]
    for task in TASKS:
      for depth in DEPTHS:
       for seed in seeds:
        for dtype,method in ARMS:
            r=train_pair(task,depth,seed,dtype,method)
            records.append(r)
            print(task,depth,seed,dtype,method,'failed=',r['failed'],
                  'time_target=',(r['results'].get('first_cross') if r['results'] else None),
                  'test_ce300=',(r['step300'].get('identity_test_ce') if r['step300'] else None),
                  flush=True)
    if tuple(seeds)==SEEDS:
        return dict(study='G10',frozen_seed_ids=SEEDS,records=records,
                    summary=summary(records))
    return dict(study='G10-smoke',seeds=seeds,records=records)

if __name__=='__main__':
    if '--smoke' in sys.argv:
        z=run((79,))
        assert len(z['records'])==20
        assert not any(r['failed'] for r in z['records']),z['records']
        print('PASS G10 20 paired seed79 smoke checks',flush=True)
    else:
        path=sys.argv[1] if len(sys.argv)>1 else 'results/g10/ci_full.json'
        os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        z=run()
        with open(path,'w') as f:json.dump(z,f,indent=2,allow_nan=False)
        print('G10 SCIENTIFIC OUTCOMES',json.dumps(z['summary'],indent=2),flush=True)
