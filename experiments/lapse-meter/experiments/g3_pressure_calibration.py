"""Gauge G3: pressure calibrated against proportional loss perturbations.
Protocol: GAUGE_G3_PREREGISTRATION.md
Usage: python experiments/g3_pressure_calibration.py results/g3/results.json
"""
import copy,json,os,sys
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
from lapse.nets import MLP,SGD
from lapse.data import digits
from g2_gauge_invariants import scales,reparameterize
import numpy as np
SEEDS=(4,5)
EPS=(.001,.01)
N=64

def perturb(net,layer,rw,rb,eps):
    t=copy.deepcopy(net)
    t.W[layer]*=np.exp(eps*rw)
    t.b[layer]*=np.exp(eps*rb)
    return t

def cell(net,X,y,seed,layer,eps,directions):
    alt=reparameterize(net,scales(net,'neuronwise',seed))
    baseline=net.loss(X,y)
    alt_baseline=alt.loss(X,y)
    _,grad,bgrad,_=net.backward(X,y)
    wg=net.W[layer]*grad[layer]
    bg=net.b[layer]*bgrad[layer]
    pressure=float(np.sqrt(np.sum(wg**2)+np.sum(bg**2)))
    actual=[];pred=[];alt_actual=[]
    for rw,rb in directions:
        pred.append(float(eps*(np.sum(wg*rw)+np.sum(bg*rb))))
        actual.append(float(perturb(net,layer,rw,rb,eps).loss(X,y)-baseline))
        alt_actual.append(float(perturb(alt,layer,rw,rb,eps).loss(X,y)-alt_baseline))
    a=np.array(actual);p=np.array(pred);b=np.array(alt_actual)
    denom=float(np.sqrt(np.mean(p*p)))
    error=float(np.sqrt(np.mean((a-p)**2))/denom) if denom>0 else None
    corr=float(np.corrcoef(a,p)[0,1]) if np.std(a)>0 and np.std(p)>0 else None
    sd_ratio=float(np.std(a,ddof=1)/(eps*pressure)) if pressure>0 else None
    r=dict(seed=seed,architecture='residual' if net.residual else 'plain',
           depth=net.depth,layer=layer,epsilon=eps,n_directions=len(directions),
           baseline_loss=baseline,pressure=pressure,correlation=corr,
           relative_rms_error=error,empirical_sd_ratio=sd_ratio,
           maximum_gauge_loss_difference=float(np.max(np.abs(a-b))))
    assert r['maximum_gauge_loss_difference']<1e-9,r
    if eps==.001:
        assert corr is not None and corr>.98,r
        assert error is not None and error<.1,r
        assert sd_ratio is not None and .65<sd_ratio<1.35,r
    return r

def run():
    records=[]
    for seed in SEEDS:
        full,labels,_,_=digits(seed)
        X,y=full[:256],labels[:256]
        for residual,depth in ((True,24),(False,8)):
            net=MLP(full.shape[1],64,depth,10,act='relu',residual=residual,seed=seed)
            opt=SGD(.05);trng=np.random.default_rng(10_000+seed)
            for _ in range(500):
                idx=trng.integers(0,len(full),64)
                _,gw,gb,_=net.backward(full[idx],labels[idx])
                opt.step(net,gw,gb)
            rng=np.random.default_rng(220000+seed)
            for layer in (0,(depth-1)//2,depth-1,depth):
                directions=[(rng.choice([-1.,1.],net.W[layer].shape),
                             rng.choice([-1.,1.],net.b[layer].shape)) for _ in range(N)]
                for eps in EPS:
                    r=cell(net,X,y,seed,layer,eps,directions)
                    records.append(r)
                    print(f"seed{seed} {'residual' if residual else 'plain'} d{depth} layer{layer} "
                          f"eps={eps} corr={r['correlation']:.4f} "
                          f"rms_err={r['relative_rms_error']:.3g} "
                          f"sd/P={r['empirical_sd_ratio']:.3f} "
                          f"gauge_err={r['maximum_gauge_loss_difference']:.2e}",flush=True)
    assert len(records)==2*2*4*2
    return dict(study='G3',records=records,passed_primary=True)

if __name__=='__main__':
    path=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'..','results','g3','results.json')
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    r=run()
    with open(path,'w') as f:json.dump(r,f,indent=2,allow_nan=False)
    print(f"PASS G3 {len(r['records'])} cells",flush=True)
