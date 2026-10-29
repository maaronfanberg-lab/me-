"""G9: 10-seed, 300-update replication with original vs double diagnostic PathCond.
The double variant calls upstream computational primitives: see G8A. Never substitute
it for the original implementation when reporting published PathCond results.
"""
import copy,inspect,json,math,os,sys,time
import numpy as np
import torch
from torch.nn import functional as F
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
from g6_benchmark import dataset
from g7_official_pathcond import setup,make_model,gauge_copy
from g8_pathcond_precision import independent_double_bz

TASKS=('digits','circle')
DEPTHS=(3,6)
SEEDS=tuple(range(80,90))
METHODS=('adam','pathcond_official','pathcond_double_diagnostic')
CHECKPOINTS=(0,1,100,300)
UPSTREAM_SHA='535b202e3476c64d5e7e9ec5e817344fb5cfd787'
LR=.003
STEPS=300
BATCH=64

def score(model,parts):
    with torch.no_grad():
        tr,va,te=parts
        result=dict(train_ce=float(F.cross_entropy(model(*tr[:1]),tr[1])),
                    validation_ce=float(F.cross_entropy(model(va[0]),va[1])),
                    test_ce=float(F.cross_entropy(model(te[0]),te[1])),
                    test_accuracy=float((model(te[0]).argmax(1)==te[1]).double().mean()))
        if not all(math.isfinite(x) for x in result.values()):
            raise FloatingPointError('nonfinite CE or accuracy')
        return result

def prep(model,method,probes):
    from pathcond.pathcond import rescaling_path_cond
    from pathcond.rescaling_polyn import reweight_model_inplace
    with torch.no_grad(): before=model(probes).clone()
    if method=='pathcond_official':
        rescaling_path_cond(model,nb_iter_optim_rescaling=10)
    elif method=='pathcond_double_diagnostic':
        bz=independent_double_bz(model)
        reweight_model_inplace(model,bz)
    elif method!='adam':raise ValueError('unknown method '+method)
    with torch.no_grad():
        v=model(probes)
        error=float((before-v).abs().max())
        if not math.isfinite(error) or error>1e-3:
            raise FloatingPointError(f'PathCond initial function drift {error}')
    return error

def model_pair(task,depth,method,seed):
    (train,valid,test),info=dataset(task,seed)
    tensors=[(torch.tensor(x,dtype=torch.float64),torch.tensor(y,dtype=torch.long))
             for x,y in (train,valid,test)]
    x,y=tensors[0];xt,yt=tensors[2]
    original,_=make_model(x.shape[1],info['classes'],depth,seed)
    a=copy.deepcopy(original)
    b=gauge_copy(original,seed)
    before=float((a(x[:128])-b(x[:128])).abs().max())
    if not math.isfinite(before) or before>=1e-10:
        raise FloatingPointError('starting gauge not function-preserving')
    start=time.perf_counter()
    errors=[prep(a,method,x[:128]),prep(b,method,x[:128])]
    gap0=float((a(x[:128])-b(x[:128])).abs().max())
    optimizers=[torch.optim.Adam(a.parameters(),lr=LR),
                torch.optim.Adam(b.parameters(),lr=LR)]
    random=np.random.default_rng(10000+seed)
    checkpoints=[]
    failed=None
    try:
        for step in range(STEPS+1):
            if step in CHECKPOINTS:
                pa=score(a,tensors);pb=score(b,tensors)
                with torch.no_grad():
                    aout=a(xt);bout=b(xt)
                    gap=float((aout-bout).abs().max())
                    aloss=float(F.cross_entropy(aout,yt))
                    bloss=float(F.cross_entropy(bout,yt))
                    match=bool(torch.equal(aout.argmax(1),bout.argmax(1)))
                if not math.isfinite(gap) or not math.isfinite(aloss) or not math.isfinite(bloss):
                    raise FloatingPointError('nonfinite gauge comparison')
                checkpoints.append(dict(step=step,original=pa,transformed=pb,
                    max_logit_gap=gap,test_loss_gap=abs(aloss-bloss),
                    labels_match=match))
            if step==STEPS:break
            ix=random.integers(0,len(x),BATCH)
            bx,by=x[ix],y[ix]
            for net,opt in ((a,optimizers[0]),(b,optimizers[1])):
                opt.zero_grad(set_to_none=True)
                F.cross_entropy(net(bx),by).backward()
                opt.step()
                if not all(torch.isfinite(p).all() for p in net.parameters()):
                    raise FloatingPointError(f'nonfinite parameter at step {step+1}')
    except Exception as exc:
        failed=type(exc).__name__+': '+str(exc)[:250]
    return dict(task=task,depth=depth,method=method,seed=seed,
                initial_plain_gauge_gap=before,initial_drift_identity=errors[0],
                initial_drift_gauge=errors[1],initial_conditioned_gauge_gap=gap0,
                failed=failed,seconds=float(time.perf_counter()-start),
                checkpoints=checkpoints)

def one(task,depth,method,seed):
    try: return model_pair(task,depth,method,seed)
    except Exception as e:
        return dict(task=task,depth=depth,method=method,seed=seed,
                    failed=type(e).__name__+': '+str(e)[:250],
                    checkpoints=[],seconds=None,initial_drift_identity=None,
                    initial_drift_gauge=None,initial_conditioned_gauge_gap=None)

def value(r,step,metric):
    if r['failed']:return math.inf
    a=next((row for row in r['checkpoints'] if row['step']==step),None)
    if a is None:return math.inf
    if metric=='max_logit_gap':return a['max_logit_gap']
    return a['original'][metric]

def summarize(rows):
    assert len(rows)==len(TASKS)*len(DEPTHS)*len(SEEDS)*len(METHODS)
    cells=[]
    h1=0
    n_double=0
    for r in rows:
        if r['method']=='pathcond_double_diagnostic':
            n_double+=2
            h1+=int(r['initial_drift_identity'] is not None and r['initial_drift_identity']<1e-10)
            h1+=int(r['initial_drift_gauge'] is not None and r['initial_drift_gauge']<1e-10)
    for task in TASKS:
        for depth in DEPTHS:
            stats={}
            for method in METHODS:
                selected=[r for r in rows if (r['task'],r['depth'],r['method'])==(task,depth,method)]
                assert len(selected)==10
                stats[method]=dict(failures=sum(bool(r['failed']) for r in selected),
                     initial_preservation_over_1e7=sum((r['initial_drift_identity'] or 0)>=1e-7 or
                           (r['initial_drift_gauge'] or 0)>=1e-7 for r in selected),
                     mean_test_ce_100=(float(np.mean([value(r,100,'test_ce') for r in selected]))
                          if all(math.isfinite(value(r,100,'test_ce')) for r in selected) else None),
                     mean_test_ce_300=(float(np.mean([value(r,300,'test_ce') for r in selected]))
                          if all(math.isfinite(value(r,300,'test_ce')) for r in selected) else None),
                     mean_test_accuracy_300=(float(np.mean([value(r,300,'test_accuracy') for r in selected]))
                          if all(math.isfinite(value(r,300,'test_accuracy')) for r in selected) else None),
                     mean_gauge_gap_300=(float(np.mean([value(r,300,'max_logit_gap') for r in selected]))
                          if all(math.isfinite(value(r,300,'max_logit_gap')) for r in selected) else None),
                     mean_paired_runtime_s=(float(np.mean([r['seconds'] for r in selected]))
                          if all(r['seconds'] is not None for r in selected) else None))
            a,o,d=(stats[m] for m in METHODS)
            valid=lambda u,k:u[k] is not None
            cells.append(dict(task=task,depth=depth,stats=stats,
                h2_ce100_double_beats_adam=(valid(d,'mean_test_ce_100') and valid(a,'mean_test_ce_100') and
                    d['mean_test_ce_100']<a['mean_test_ce_100']),
                h3_double_gauge_better=(valid(d,'mean_gauge_gap_300') and valid(o,'mean_gauge_gap_300') and
                    d['mean_gauge_gap_300']<o['mean_gauge_gap_300']),
                h4_double_ce300_noninferior=(valid(d,'mean_test_ce_300') and valid(o,'mean_test_ce_300') and
                    d['mean_test_ce_300']<=o['mean_test_ce_300']+.01)))
    h2=sum(int(c['h2_ce100_double_beats_adam']) for c in cells)
    h3=sum(int(c['h3_double_gauge_better']) for c in cells)
    h4=sum(int(c['h4_double_ce300_noninferior']) for c in cells)
    return dict(n=len(rows),n_double_conditions=n_double,h1_initial_strict_n=h1,h1_pass=(h1==80),
       h2_ce100_win_cells=h2,h2_pass=h2>=3,
       h3_gauge300_win_cells=h3,h3_pass=h3>=3,
       h4_noninferiority_cells=h4,h4_pass=h4==4,cells=cells)

def run():
    setup()
    from pathcond.pathcond import rescaling_path_cond
    assert 'pathcond' in inspect.getfile(rescaling_path_cond).lower()
    rows=[]
    for task in TASKS:
        for depth in DEPTHS:
            for seed in SEEDS:
                for method in METHODS:
                    r=one(task,depth,method,seed);rows.append(r)
                    print(task,depth,seed,method,'failed=',r['failed'],
                          'ce100=',value(r,100,'test_ce'),
                          'ce300=',value(r,300,'test_ce'),
                          'gap300=',value(r,300,'max_logit_gap'),flush=True)
    return dict(study='G9',source_commit=UPSTREAM_SHA,steps=STEPS,lr=LR,
         records=rows,summary=summarize(rows))

if __name__=='__main__':
    if '--smoke' in sys.argv:
        setup()
        for method in METHODS:
            r=one('digits',3,method,79)
            print('SMOKE',method,r['failed'],value(r,300,'test_ce'),flush=True)
            assert r['failed'] is None,r
        print('PASS G9 unused seed 79 smoke')
    else:
        path=sys.argv[1] if len(sys.argv)>1 else 'results/g9/results.json'
        os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        result=run()
        with open(path,'w') as f:json.dump(result,f,indent=2,allow_nan=False)
        print('G9 HYPOTHESES',json.dumps(result['summary'],indent=2),flush=True)
