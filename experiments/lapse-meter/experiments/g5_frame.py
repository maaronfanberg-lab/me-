"""Gauge G5: clipped activation-frame SGD with movable zero biases.
See GAUGE_G5_PREREGISTRATION.md. Run: python experiments/g5_frame.py results/g5/holdout.json 10 11
"""
import copy,json,os,sys
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
import numpy as np
from lapse.nets import MLP
from lapse.data import digits
from g4_trajectory import scales, log_parameter_step
from g2_gauge_invariants import reparameterize

SEEDS=(10,11)
ETA=0.05
CAP=1.0
STEPS=150
CHECKPOINTS=(0,1,5,25,50,100,150)

def frame_coordinates(net,X,y):
    """Batch-dependent gauge-equivariant parameter frames and normalized gradient norm."""
    _,z=net.forward(X)
    _,gW,gb,_=net.backward(X,y)
    anchors=[np.sqrt(np.mean(v*v,axis=0)) for v in z[:-1]]+[np.ones(net.W[-1].shape[0])]
    prior=[np.sqrt(np.mean(X*X,axis=0))]+anchors[:-1]
    prior[0][prior[0]==0]=1.0
    framesW=[];framesB=[];grad_norm_sq=0.
    for i in range(len(net.W)):
        out,inp=anchors[i],prior[i]
        if (not np.all(np.isfinite(out)) or not np.all(np.isfinite(inp)) or
            np.any(out<=0) or np.any(inp<=0)):
            raise FloatingPointError(f'G5 undefined/nonfinite frame, layer={i}')
        q=out[:,None]/inp[None,:]
        framesW.append(q);framesB.append(out)
        grad_norm_sq+=float(np.sum((q*gW[i])**2)+np.sum((out*gb[i])**2))
    G=float(np.sqrt(grad_norm_sq))
    if not np.isfinite(G):raise FloatingPointError('G5 gradient norm nonfinite')
    return framesW,framesB,gW,gb,G

def frame_step(net,X,y,eta=ETA,cap=CAP):
    if not np.isfinite(eta) or not 0<=eta or not np.isfinite(cap) or not cap>0:
        raise ValueError('eta>=0 and cap>0 must be finite')
    qw,qb,gw,gb,G=frame_coordinates(net,X,y)
    divisor=max(1.,G/cap)
    for i in range(len(net.W)):
        net.W[i]-=(eta/divisor)*qw[i]*qw[i]*gw[i]
        net.b[i]-=(eta/divisor)*qb[i]*qb[i]*gb[i]
        if not np.all(np.isfinite(net.W[i])) or not np.all(np.isfinite(net.b[i])):
            raise FloatingPointError(f'G5 nonfinite weights, layer={i}')
    return G

def error_from_gauge(a,b,ds):
    exact=reparameterize(a,ds)
    return max(float(np.max(np.abs(p-q)/np.maximum(1.,np.abs(p))))
               for p,q in zip(exact.W+exact.b,b.W+b.b))

def run(seeds=SEEDS):
    records=[]
    for seed in seeds:
        X,y,Xt,yt=digits(seed)
        batches=np.random.default_rng(10000+seed)
        index=[batches.integers(0,len(X),64) for _ in range(STEPS)]
        for residual,depth in ((False,8),(True,24)):
            original=MLP(X.shape[1],64,depth,10,act='relu',residual=residual,seed=seed)
            ds=scales(original,'neuronwise',seed)
            a=copy.deepcopy(original)
            b=reparameterize(original,ds)
            log_model=copy.deepcopy(original)
            norm_a=frame_coordinates(a,X[index[0]],y[index[0]])[-1]
            norm_b=frame_coordinates(b,X[index[0]],y[index[0]])[-1]
            norm_difference=abs(norm_a-norm_b)
            first_gauge_error=error_from_gauge(a,b,ds)
            rows=[]
            prior_biases=[bb.copy() for bb in a.b]
            for step in range(STEPS+1):
                if step in CHECKPOINTS:
                    z=a.forward(X[:256])[1][-1]
                    other=b.forward(X[:256])[1][-1]
                    rows.append(dict(step=step,logit_difference=float(np.max(np.abs(z-other))),
                          gauge_parameter_error=error_from_gauge(a,b,ds),
                          loss_a=a.loss(X,y),loss_b=b.loss(X,y),
                          test_loss_a=a.loss(Xt,yt),test_loss_b=b.loss(Xt,yt),
                          accuracy_a=a.accuracy(Xt,yt),accuracy_b=b.accuracy(Xt,yt),
                          log_model_loss=log_model.loss(X,y),
                          log_model_accuracy=log_model.accuracy(Xt,yt),
                          changed_initial_zero_biases=sum(int(np.sum((ob==0)&(nb!=0))) for ob,nb in zip(prior_biases,a.b))))
                if step==STEPS:break
                idx=index[step]
                frame_step(a,X[idx],y[idx]);frame_step(b,X[idx],y[idx])
                _,gw,gb,_=log_model.backward(X[idx],y[idx])
                log_parameter_step(log_model,gw,gb)
            primary_ok=(norm_difference<1e-9 and all(
                r['logit_difference']<1e-8 and r['gauge_parameter_error']<1e-8 and
                abs(r['loss_a']-r['loss_b'])<1e-9 and
                abs(r['test_loss_a']-r['test_loss_b'])<1e-9 and
                r['accuracy_a']==r['accuracy_b'] for r in rows))
            bias_ok=rows[1]['changed_initial_zero_biases']>0
            improvement=float(rows[-1]['accuracy_a']-rows[-1]['log_model_accuracy'])
            result=dict(seed=seed,architecture='residual' if residual else 'plain',depth=depth,
                gauge='neuronwise',first_frame_norm_a=norm_a,first_frame_norm_b=norm_b,
                initial_gauge_error=first_gauge_error,first_frame_norm_difference=norm_difference,
                primary_invariance_pass=bool(primary_ok),zero_bias_escape_pass=bool(bias_ok),
                accuracy_improvement_over_log_update=improvement,
                plain_improvement_pass=bool(improvement>=.20) if not residual else None,checkpoints=rows)
            records.append(result)
            print(f"{result['architecture']:8s} seed={seed} "
                f"gauge_err={max(r['logit_difference'] for r in rows):.2e} "
                f"loss={rows[0]['loss_a']:.3f}->{rows[-1]['loss_a']:.3f} "
                f"accuracy={rows[-1]['accuracy_a']:.3f} vs log={rows[-1]['log_model_accuracy']:.3f} "
                f"bias_changed={rows[1]['changed_initial_zero_biases']} ",flush=True)
    assert len(records)==len(seeds)*2
    return dict(study='G5',eta=ETA,cap=CAP,steps=STEPS,records=records,
          all_invariance_pass=all(r['primary_invariance_pass'] for r in records),
          all_bias_escape_pass=all(r['zero_bias_escape_pass'] for r in records),
          all_plain_improvement_pass=all(r['plain_improvement_pass'] for r in records if r['plain_improvement_pass'] is not None))

if __name__=='__main__':
    path=sys.argv[1] if len(sys.argv)>1 else 'results/g5/holdout.json'
    seeds=tuple(int(a) for a in sys.argv[2:]) if len(sys.argv)>2 else SEEDS
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    result=run(seeds)
    with open(path,'w') as f:json.dump(result,f,indent=2,allow_nan=False)
    if not (result['all_invariance_pass'] and result['all_bias_escape_pass'] and result['all_plain_improvement_pass']):
        raise SystemExit('G5 SOME PREREGISTERED CHECKS FAILED; inspect results JSON')
    print('PASS all G5 held-out criteria',flush=True)
