"""Gauge G2: invariant signals under neuronwise ReLU rescaling.
Protocol: GAUGE_G2_PREREGISTRATION.md.
Run: python experiments/g2_gauge_invariants.py results/g2/results.json
"""
import copy, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse import geometry
from lapse.data import digits
from lapse.nets import MLP, SGD

SEEDS=(0,1)
CHECKPOINTS=(0,250,500)
GAUGES=("identity","uniform4","neuronwise")

def scales(net, name, seed):
    """Positive diagonal hidden scales; residual streams share a single diagonal."""
    if net.act!="relu": raise ValueError("G2 scaling requires ReLU")
    n=len(net.W)-1; width=net.W[0].shape[0]
    if name not in GAUGES: raise ValueError("Unknown gauge")
    if name=="identity": return [np.ones(width) for _ in range(n)]
    if name=="uniform4": return [np.full(width,4.) for _ in range(n)]
    rng=np.random.default_rng(100_000+seed)
    def draw():
        return np.exp(np.linspace(-np.log(32),np.log(32),width)[rng.permutation(width)])
    if net.residual:
        d=draw()
        return [d.copy() for _ in range(n)]
    return [draw() for _ in range(n)]

def reparameterize(net, hidden_scales):
    """Transform W_i -> D_i W_i D_(i-1)^-1, b_i -> D_i b_i.

    Identity residual skips require all D_i equal. Output weights receive D_last^-1.
    """
    if net.act!="relu": raise ValueError("requires ReLU")
    nh=len(net.W)-1
    if len(hidden_scales)!=nh: raise ValueError("wrong number of hidden scales")
    ds=[np.asarray(d,dtype=np.float64) for d in hidden_scales]
    if any(d.ndim!=1 or d.size!=net.W[i].shape[0] or
           not np.isfinite(d).all() or np.any(d<=0) for i,d in enumerate(ds)):
        raise ValueError("invalid positive diagonal")
    if net.residual and any(not np.array_equal(d,ds[0]) for d in ds[1:]):
        raise ValueError("residual skips require one shared diagonal")
    n=copy.deepcopy(net)
    for i in range(nh):
        n.W[i]*=ds[i][:,None]
        if i>0: n.W[i]/=ds[i-1][None,:]
        n.b[i]*=ds[i]
    n.W[-1]/=ds[-1][None,:]
    return n

def hidden_grads(net,X,y,bwd=None,states=None):
    """Return dL/dh_i for post-activation hidden states."""
    if bwd is None: bwd=net.backward(X,y)
    ds=bwd[3]; gh=ds[-1]@net.W[-1]
    out=[None]*(len(net.W)-1)
    for i in range(len(net.W)-2,-1,-1):
        out[i]=gh.copy()
        gh=gh+ds[i]@net.W[i] if net.residual and i>0 else ds[i]@net.W[i]
    return out

def diagnostic(net,X,y):
    h,z=net.forward(X)
    bw=net.backward(X,y)
    gh=hidden_grads(net,X,y,bw,(h,z))
    A=np.array([np.sqrt(np.mean(np.sum((h[i+1]*gh[i])**2,axis=1)))
                for i in range(len(gh))],dtype=np.float64)
    P=np.array([np.sqrt(np.sum((w*gw)**2)+np.sum((b*gb)**2))
                for w,gw,b,gb in zip(net.W,bw[1],net.b,bw[2])],dtype=np.float64)
    profile=A/A[-1] if A[-1]>0 else None
    return dict(logits=z[-1],loss=net.loss(X,y),accuracy=net.accuracy(X,y),
                activation_work=A,parameter_pressure=P,relative_work=profile,
                work_tilt=math.log(profile[0]) if profile is not None and profile[0]>0 else None,
                raw=geometry(net.geometry_deltas(bw[3])),
                corrected=geometry(net.geometry_deltas(bw[3],remove_alpha=True)))

def max_component_relative_error(a,b):
    if np.shape(a)!=np.shape(b): raise ValueError("shape mismatch")
    if not (np.isfinite(a).all() and np.isfinite(b).all()): return float("inf")
    return float(np.max(np.abs(a-b)/np.maximum(1e-12,np.abs(a))))

def compare(net,X,y,gauge,seed):
    trial=reparameterize(net,scales(net,gauge,seed))
    a,b=diagnostic(net,X,y),diagnostic(trial,X,y)
    def shift(x,z): return None if x is None or z is None else float(z-x)
    diff=float(np.max(np.abs(a["logits"]-b["logits"])))
    loss_diff=float(abs(a["loss"]-b["loss"]))
    work_error=max_component_relative_error(a["activation_work"],b["activation_work"])
    param_error=max_component_relative_error(a["parameter_pressure"],b["parameter_pressure"])
    profile_error=(max_component_relative_error(a["relative_work"],b["relative_work"])
                   if a["relative_work"] is not None and b["relative_work"] is not None else None)
    r=dict(gauge=gauge,architecture="residual" if net.residual else "plain",depth=net.depth,
           seed=seed,max_logit_error=diff,loss_error=loss_diff,
           accuracy_before=a["accuracy"],accuracy_after=b["accuracy"],
           max_activation_work_rel_error=work_error,
           max_parameter_pressure_rel_error=param_error,
           max_relative_work_profile_error=profile_error,
           work_tilt_before=a["work_tilt"],work_tilt_after=b["work_tilt"],
           work_tilt_shift=shift(a["work_tilt"],b["work_tilt"]),
           raw_tilt_before=a["raw"].tilt,raw_tilt_after=b["raw"].tilt,
           raw_tilt_shift=float(b["raw"].tilt-a["raw"].tilt),
           corrected_tilt_shift=float(b["corrected"].tilt-a["corrected"].tilt),
           raw_slope_shift=shift(a["raw"].kappa,b["raw"].kappa),
           raw_horizons_before=len(a["raw"].horizons),
           raw_horizons_after=len(b["raw"].horizons))
    assert np.isfinite([diff,loss_diff,work_error,param_error]).all(),r
    assert diff<1e-9 and loss_diff<1e-9 and a["accuracy"]==b["accuracy"],r
    assert work_error<1e-9 and param_error<1e-9,r
    assert profile_error is not None and profile_error<1e-9,r
    assert r["work_tilt_shift"] is not None and abs(r["work_tilt_shift"])<1e-9,r
    return r

def run(seeds=SEEDS):
    records=[]
    for seed in seeds:
        X,y,Xt,yt=digits(seed)
        for residual,depth in ((True,24),(False,8)):
            net=MLP(X.shape[1],64,depth,10,act="relu",residual=residual,seed=seed)
            opt=SGD(.05);rng=np.random.default_rng(10_000+seed)
            for step in range(max(CHECKPOINTS)+1):
                if step in CHECKPOINTS:
                    for gauge in GAUGES:
                        r=compare(net,X[:256],y[:256],gauge,seed)
                        r["step"]=step;r["test_accuracy"]=net.accuracy(Xt,yt)
                        records.append(r)
                        print(f"{r['architecture']:8s} d{depth} seed{seed} step{step:3d} {gauge:10s} "
                              f"logit_err={r['max_logit_error']:.1e} "
                              f"A_err={r['max_activation_work_rel_error']:.1e} "
                              f"P_err={r['max_parameter_pressure_rel_error']:.1e} "
                              f"raw_tilt_d={r['raw_tilt_shift']:+.3f}",flush=True)
                if step==max(CHECKPOINTS):break
                idx=rng.integers(0,len(X),64)
                _,gw,gb,_=net.backward(X[idx],y[idx]);opt.step(net,gw,gb)
    assert len(records)==len(seeds)*2*len(CHECKPOINTS)*len(GAUGES)
    assert any(abs(r["raw_tilt_shift"])>1e-8 for r in records if r["gauge"]=="neuronwise")
    return dict(study="G2",total=len(records),all_primary_checks_passed=True,records=records)

if __name__=="__main__":
    path=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),"..","results","g2","results.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    seeds=tuple(int(s) for s in sys.argv[2:]) if len(sys.argv)>2 else SEEDS
    result=run(seeds)
    with open(path,"w") as f:json.dump(result,f,indent=2,allow_nan=False)
    print(f"PASS {result['total']} G2 comparisons",flush=True)
