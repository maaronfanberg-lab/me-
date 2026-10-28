"""G4: coordinate-equivariant log-parameter update vs SGD. See GAUGE_G4_PREREGISTRATION.md."""
import os,sys,json,copy
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
import numpy as np
from lapse.data import digits
from lapse.nets import MLP,SGD
from g2_gauge_invariants import reparameterize

def scales(net,name,seed):
    """Locked G4: uniform x4 or neuronwise 1/8..8, respecting residual skips."""
    if net.act!="relu": raise ValueError("ReLU only")
    n=len(net.W)-1; width=net.W[0].shape[0]
    if name=="uniform4": return [np.full(width,4.) for _ in range(n)]
    if name!="neuronwise": raise ValueError("unknown gauge")
    rng=np.random.default_rng(100_000+seed)
    def draw(): return np.exp(np.linspace(-np.log(8),np.log(8),width)[rng.permutation(width)])
    if net.residual:
        d=draw(); return [d.copy() for _ in range(n)]
    return [draw() for _ in range(n)]

SEEDS=(6,7)
GAUGES=('uniform4','neuronwise')
CHECKPOINTS=(0,1,5,25,50,100,150)
ETA=2.0

def log_parameter_step(net,gW,gb,eta=ETA):
    """Elementwise log-magnitude gradient update, zero preserving, sign preserving."""
    if eta<0 or not np.isfinite(eta): raise ValueError('finite nonnegative eta needed')
    for p,g in zip(net.W+net.b,gW+gb):
        multiplier=np.exp(-eta*(p*g))
        if not np.all(np.isfinite(multiplier)):raise FloatingPointError('nonfinite scale')
        p*=multiplier
        if not np.all(np.isfinite(p)):raise FloatingPointError('nonfinite updated parameter')

def gauge_parameter_error(net,transformed,ds):
    expected=reparameterize(net,ds)
    errs=[np.max(np.abs(x-y)/np.maximum(1.0,np.abs(x))) for x,y in zip(expected.W+expected.b,transformed.W+transformed.b)]
    return float(max(errs))

def diagnostic(a,b,ds,X,y,Xt,yt,step):
    za=a.forward(X)[1][-1];zb=b.forward(X)[1][-1]
    return dict(step=step,max_logit_difference=float(np.max(np.abs(za-zb))),
        train_loss_a=a.loss(X,y),train_loss_b=b.loss(X,y),
        test_loss_a=a.loss(Xt,yt),test_loss_b=b.loss(Xt,yt),
        accuracy_a=a.accuracy(Xt,yt),accuracy_b=b.accuracy(Xt,yt),
        parameter_gauge_error=gauge_parameter_error(a,b,ds))

def run(seeds=SEEDS):
    records=[]
    for seed in seeds:
        X,y,Xt,yt=digits(seed)
        for residual,depth in ((True,24),(False,8)):
            original=MLP(X.shape[1],64,depth,10,act='relu',residual=residual,seed=seed)
            indices=[];rng=np.random.default_rng(10000+seed)
            for _ in range(150):indices.append(rng.integers(0,len(X),64))
            for gauge in GAUGES:
                ds=scales(original,gauge,seed)
                a=copy.deepcopy(original);b=reparameterize(original,ds)
                _,gwa,gba,_=a.backward(X[indices[0]],y[indices[0]])
                _,gwb,gbb,_=b.backward(X[indices[0]],y[indices[0]])
                pressure_err=float(max(np.max(np.abs(q*g-z*h)/np.maximum(1.0,np.abs(q*g)))
                                    for q,g,z,h in zip(a.W+a.b,gwa+gba,b.W+b.b,gwb+gbb)))
                assert pressure_err<1e-9,(seed,residual,gauge,pressure_err)
                rows=[]
                for step in range(151):
                    if step in CHECKPOINTS:
                        row=diagnostic(a,b,ds,X,y,Xt,yt,step)
                        assert row['max_logit_difference']<1e-8,row
                        assert abs(row['train_loss_a']-row['train_loss_b'])<1e-9,row
                        assert abs(row['test_loss_a']-row['test_loss_b'])<1e-9,row
                        assert row['accuracy_a']==row['accuracy_b'],row
                        assert row['parameter_gauge_error']<1e-8,row
                        rows.append(row)
                    if step==150:break
                    idx=indices[step]
                    _,wa,ba,_=a.backward(X[idx],y[idx]);_,wb,bb,_=b.backward(X[idx],y[idx])
                    log_parameter_step(a,wa,ba);log_parameter_step(b,wb,bb)
                ca=copy.deepcopy(original);cb=reparameterize(original,ds)
                idx=indices[0]
                _,wa,ba,_=ca.backward(X[idx],y[idx]);_,wb,bb,_=cb.backward(X[idx],y[idx])
                SGD(.05).step(ca,wa,ba);SGD(.05).step(cb,wb,bb)
                sgd=diagnostic(ca,cb,ds,X,y,Xt,yt,1)
                assert sgd['max_logit_difference']>1e-7,(seed,residual,gauge,sgd)
                r=dict(seed=seed,architecture='residual' if residual else 'plain',depth=depth,gauge=gauge,
                       initial_pressure_error=pressure_err,sgd_control=sgd,checkpoints=rows)
                records.append(r)
                print(f"{r['architecture']:8s} seed={seed} gauge={gauge:10s} "
                      f"log_err={max(row['max_logit_difference'] for row in rows):.2e} "
                      f"gauge_err={max(row['parameter_gauge_error'] for row in rows):.2e} "
                      f"SGD_control={sgd['max_logit_difference']:.2e} "
                      f"loss={rows[0]['train_loss_a']:.3f}->{rows[-1]['train_loss_a']:.3f}",flush=True)
    assert len(records)==len(seeds)*4
    return dict(study='G4',eta=ETA,steps=150,all_primary_checks_passed=True,records=records)

if __name__=='__main__':
    path=sys.argv[1] if len(sys.argv)>1 else 'results/g4/results.json'
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    seeds=tuple(int(s) for s in sys.argv[2:]) if len(sys.argv)>2 else SEEDS
    r=run(seeds)
    with open(path,'w') as f:json.dump(r,f,indent=2,allow_nan=False)
