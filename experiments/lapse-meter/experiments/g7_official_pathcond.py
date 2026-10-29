"""G7A: official upstream PathCond+Adam vs Adam/G5, plain ReLU only.
Pre-registration: GAUGE_G7A_PREREGISTRATION.md.
Upstream pinned to 535b202e3476c64d5e7e9ec5e817344fb5cfd787.
No reimplementation or fallback for official PathCond.
"""
import copy, json, math, os, sys, time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
from lapse.nets import MLP
from g6_benchmark import dataset
from g5_frame import frame_step as numpy_frame_step

UPSTREAM_SHA='535b202e3476c64d5e7e9ec5e817344fb5cfd787'
TASKS=('digits','circle')
DEPTHS=(3,6)
METHODS=('adam','pathcond_adam','g5')
RATES={'adam':(.001,.003),'pathcond_adam':(.001,.003),'g5':(.01,.05)}
TUNING=(40,41)
HOLDOUT=(50,51,52)
STEPS=100
CHECKPOINTS=(0,1,25,50,100)

def setup():
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(1)

def make_model(din,nclasses,depth,seed):
    original=MLP(din,32,depth,nclasses,act='relu',residual=False,seed=seed)
    modules=[]
    for i,(w,b) in enumerate(zip(original.W,original.b)):
        l=nn.Linear(w.shape[1],w.shape[0])
        with torch.no_grad():
            l.weight.copy_(torch.from_numpy(w));l.bias.copy_(torch.from_numpy(b))
        modules.append(l)
        if i<depth:modules.append(nn.ReLU())
    return nn.Sequential(*modules),original

def torch_g5_step(model,X,y,lr):
    layers=[x for x in model if isinstance(x,nn.Linear)]
    zs=[];h=X
    for i,l in enumerate(layers):
        z=l(h);zs.append(z);h=torch.relu(z) if i<len(layers)-1 else z
    grad=torch.autograd.grad(F.cross_entropy(h,y),[p for l in layers for p in (l.weight,l.bias)])
    with torch.no_grad():
        anchors=[(z.detach().square().mean(0)).sqrt() for z in zs[:-1]]+[torch.ones(layers[-1].out_features,dtype=X.dtype)]
        prior=[(X.square().mean(0)).sqrt()]+anchors[:-1]
        prior[0]=torch.where(prior[0]==0,torch.ones_like(prior[0]),prior[0])
        values=[];norm2=0.
        for i,l in enumerate(layers):
            o=anchors[i];inp=prior[i]
            if not torch.isfinite(o).all() or not torch.isfinite(inp).all() or (o<=0).any() or (inp<=0).any():
                raise FloatingPointError('G5 undefined frame')
            q=o[:,None]/inp[None,:]
            gw,gb=grad[2*i:2*i+2]
            norm2+=float(((q*gw)**2).sum()+((o*gb)**2).sum())
            values.append((l,q,o,gw,gb))
        scale=lr/max(1.,math.sqrt(norm2)/1.)
        for l,q,o,gw,gb in values:
            l.weight.sub_(scale*q*q*gw);l.bias.sub_(scale*o*o*gb)
            if not torch.isfinite(l.weight).all() or not torch.isfinite(l.bias).all():
                raise FloatingPointError('G5 nonfinite parameter')

def gauge_copy(model,seed):
    n=copy.deepcopy(model);ls=[x for x in n if isinstance(x,nn.Linear)]
    rng=np.random.default_rng(100000+seed)
    ds=[torch.from_numpy(np.exp(np.linspace(-np.log(8),np.log(8),l.out_features)[rng.permutation(l.out_features)])) for l in ls[:-1]]
    with torch.no_grad():
        for i,l in enumerate(ls):
            if i<len(ds):
                l.weight.mul_(ds[i][:,None]);l.bias.mul_(ds[i])
            if i>0:l.weight.div_(ds[i-1][None,:])
    return n

def condition(model,X):
    from pathcond.pathcond import rescaling_path_cond
    with torch.no_grad():
        before=model(X).clone();params=[p.detach().clone() for p in model.parameters()]
    rescaling_path_cond(model,nb_iter_optim_rescaling=10)
    with torch.no_grad():
        difference=float((model(X)-before).abs().max())
        changed=max(float((a-b).abs().max()) for a,b in zip(params,model.parameters()))
    if not math.isfinite(difference) or difference>=1e-7 or not math.isfinite(changed) or changed<=1e-10:
        raise RuntimeError(f'Official PathCond invalid/no-op: logit error {difference}, change {changed}')
    return dict(max_initial_logit_change=difference,max_parameter_change=changed,upstream_sha=UPSTREAM_SHA)

def to_tensors(data):
    return torch.tensor(data[0],dtype=torch.float64),torch.tensor(data[1],dtype=torch.long)

def run_one(task,depth,method,lr,seed,stress=False):
    data,info=dataset(task,seed)
    parts=[to_tensors(p) for p in data]
    X,y=parts[0];Xt,yt=parts[2]
    model,_=make_model(X.shape[1],info['classes'],depth,seed)
    time0=time.perf_counter();conditioned=None;stressed_conditioned=None;checkpoints=[];gauge=[]
    failure=None;initial_gap=None
    try:
        transformed=gauge_copy(model,seed) if stress else None
        if transformed is not None:
            with torch.no_grad():
                if float((model(X[:128])-transformed(X[:128])).abs().max())>=1e-7:
                    raise ValueError('gauge did not preserve initial function')
        if method=='pathcond_adam':
            conditioned=condition(model,X[:128])
            if transformed is not None:stressed_conditioned=condition(transformed,X[:128])
        if transformed is not None:
            with torch.no_grad():
                initial_gap=float((model(X[:128])-transformed(X[:128])).abs().max())
            if not math.isfinite(initial_gap) or initial_gap>=1e-7:
                raise ValueError('preprocessing destroyed gauge equivalence')
        optimizer=torch.optim.Adam(model.parameters(),lr=lr) if method!='g5' else None
        other_optimizer=torch.optim.Adam(transformed.parameters(),lr=lr) if transformed is not None and method!='g5' else None
        rng=np.random.default_rng(10000+seed)
        for step in range(STEPS+1):
            if step in CHECKPOINTS:
                with torch.no_grad():
                    losses=[float(F.cross_entropy(model(u),v)) for u,v in parts]
                    accu=float((model(Xt).argmax(1)==yt).double().mean())
                    if not all(math.isfinite(v) for v in losses):raise FloatingPointError('nonfinite checkpoint loss')
                    checkpoints.append(dict(step=step,train_ce=losses[0],validation_ce=losses[1],test_ce=losses[2],test_accuracy=accu))
                    if transformed is not None:
                        a=model(Xt);b=transformed(Xt)
                        gap=float((a-b).abs().max())
                        lgap=abs(float(F.cross_entropy(a,yt)-F.cross_entropy(b,yt)))
                        if not all(math.isfinite(v) for v in (gap,lgap)):raise FloatingPointError('nonfinite gauge output')
                        gauge.append(dict(step=step,max_logit_gap=gap,loss_gap=lgap,labels_match=bool(torch.equal(a.argmax(1),b.argmax(1)))))
            if step==STEPS:break
            idx=rng.integers(0,len(X),64)
            bx,by=X[idx],y[idx]
            for network,opt in (((model,optimizer),(transformed,other_optimizer)) if transformed is not None else ((model,optimizer),)):
                if method=='g5':torch_g5_step(network,bx,by,lr)
                else:
                    opt.zero_grad(set_to_none=True)
                    F.cross_entropy(network(bx),by).backward();opt.step()
                if not all(torch.isfinite(p).all() for p in network.parameters()):
                    raise FloatingPointError(f'nonfinite weights step {step+1}')
    except Exception as e:
        failure=(type(e).__name__+': '+str(e))[:300]
    return dict(task=task,depth=depth,method=method,lr=lr,seed=seed,stress=stress,
                failed=failure,seconds=time.perf_counter()-time0,
                initial_pathcond=conditioned,transformed_pathcond=stressed_conditioned,
                initial_gauge_logit_gap=initial_gap,checkpoints=checkpoints,gauge=gauge)

def metric(r,key):
    if r['failed'] or not r['checkpoints'] or r['checkpoints'][-1]['step']!=STEPS:return math.inf
    return r['checkpoints'][-1][key]

def preflight():
    setup()
    for depth in DEPTHS:
        X=np.random.default_rng(45).standard_normal((50,7))
        y=np.random.default_rng(46).integers(0,4,50)
        torch_model,numpy_model=make_model(7,4,depth,123)
        with torch.no_grad():
            assert np.max(np.abs(torch_model(torch.tensor(X)).numpy()-numpy_model.forward(X)[1][-1]))<1e-12
        torch_g5_step(torch_model,torch.tensor(X),torch.tensor(y),.05)
        numpy_frame_step(numpy_model,X,y,eta=.05,cap=1.)
        for t,(w,b) in zip([m for m in torch_model if isinstance(m,nn.Linear)],zip(numpy_model.W,numpy_model.b)):
            assert np.max(np.abs(t.weight.detach().numpy()-w))<1e-12
            assert np.max(np.abs(t.bias.detach().numpy()-b))<1e-12
        gauge=gauge_copy(torch_model,123)
        with torch.no_grad():assert float((torch_model(torch.tensor(X))-gauge(torch.tensor(X))).abs().max())<1e-12
    print('PASS G7 Torch/Numpy G5 and gauge preflight',flush=True)

def run():
    setup();preflight()
    # Require ORIGINAL upstream package: no silent fallback for inaccessible source.
    from pathcond.pathcond import rescaling_path_cond
    tuning=[]
    for task in TASKS:
        for depth in DEPTHS:
            for method in METHODS:
                for lr in RATES[method]:
                    for seed in TUNING:tuning.append(run_one(task,depth,method,lr,seed))
                print('TUNE',task,depth,method,flush=True)
    selected=[]
    for task in TASKS:
        for depth in DEPTHS:
            for method in METHODS:
                choices=[]
                for lr in RATES[method]:
                    rr=[r for r in tuning if (r['task'],r['depth'],r['method'],r['lr'])==(task,depth,method,lr)]
                    assert len(rr)==len(TUNING)
                    costs=[metric(r,'validation_ce') for r in rr]
                    choices.append(dict(lr=lr,failed=sum(r['failed'] is not None for r in rr),mean_val_ce=float(np.mean(costs)) if all(map(math.isfinite,costs)) else None))
                best=min(choices,key=lambda z:(z['failed'],math.inf if z['mean_val_ce'] is None else z['mean_val_ce'],z['lr']))
                selected.append(dict(task=task,depth=depth,method=method,lr=best['lr'],candidates=choices))
    evaluation=[]
    for c in selected:
        for seed in HOLDOUT:evaluation.append(run_one(c['task'],c['depth'],c['method'],c['lr'],seed,stress=True))
        print('HOLDOUT',c['task'],c['depth'],c['method'],flush=True)
    cells=[]
    for task in TASKS:
        for depth in DEPTHS:
            stats={}
            for method in METHODS:
                rs=[r for r in evaluation if (r['task'],r['depth'],r['method'])==(task,depth,method)]
                assert len(rs)==len(HOLDOUT)
                cost=[metric(r,'test_ce') for r in rs]
                gaps=[r['gauge'][-1]['max_logit_gap'] if not r['failed'] and len(r['gauge'])==len(CHECKPOINTS) else math.inf for r in rs]
                stats[method]=dict(failures=sum(r['failed'] is not None for r in rs),
                    mean_test_ce=float(np.mean(cost)) if all(map(math.isfinite,cost)) else None,
                    mean_accuracy=float(np.mean([metric(r,'test_accuracy') for r in rs])) if all(map(math.isfinite,cost)) else None,
                    mean_runtime_s=float(np.mean([r['seconds'] for r in rs])),
                    mean_terminal_gauge_gap=float(np.mean(gaps)) if all(map(math.isfinite,gaps)) else None)
            ap=stats['adam'];pp=stats['pathcond_adam']
            cells.append(dict(task=task,depth=depth,stats=stats,
                pathcond_ce_win=pp['mean_test_ce'] is not None and ap['mean_test_ce'] is not None and pp['mean_test_ce']<ap['mean_test_ce'],
                pathcond_gauge_win=pp['mean_terminal_gauge_gap'] is not None and ap['mean_terminal_gauge_gap'] is not None and pp['mean_terminal_gauge_gap']<ap['mean_terminal_gauge_gap']))
    pathruns=[r for r in evaluation if r['method']=='pathcond_adam']
    h1=len(pathruns)==12 and all(not r['failed'] and r['initial_pathcond'] is not None and r['initial_pathcond']['max_initial_logit_change']<1e-7 for r in pathruns)
    h2=sum(c['pathcond_ce_win'] for c in cells)
    h3=sum(c['pathcond_gauge_win'] for c in cells)
    return dict(study='G7A',upstream_sha=UPSTREAM_SHA,tuning=tuning,selected=selected,evaluation=evaluation,
                summary=dict(h1_integration_pass=h1,h2_test_ce_wins=h2,h2_pass=h2>=3,h3_gauge_wins=h3,h3_pass=h3>=3,cells=cells))

if __name__=='__main__':
    if '--preflight' in sys.argv:preflight()
    else:
        output=sys.argv[1] if len(sys.argv)>1 else 'results/g7a/full.json'
        os.makedirs(os.path.dirname(os.path.abspath(output)),exist_ok=True)
        r=run()
        with open(output,'w') as f:json.dump(r,f,indent=2,allow_nan=False)
        print('G7A SUMMARY',json.dumps(r['summary'],indent=2),flush=True)
