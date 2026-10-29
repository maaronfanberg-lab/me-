"""G11: larger/longer native-float32 PathCond amortization benchmark.
Scientific preregistration: GAUGE_G11_PREREGISTRATION.md (frozen before runs).
Original upstream PathCond at git SHA 535b202e3476c64d5e7e9ec5e817344fb5cfd787.
"""
import copy
import inspect
import json
import math
import os
import sys
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lapse.nets import MLP
from g7_official_pathcond import gauge_copy

TASKS = ("digits", "large_circle")
NETWORKS = ((64, 6), (128, 12))
TARGET_SEEDS = tuple(range(120, 125))
METHODS = ("adam", "pathcond_adam")
UPSTREAM_SHA = "535b202e3476c64d5e7e9ec5e817344fb5cfd787"
STEPS = 600
BATCH = 128
LR = 0.003
TARGETS = {"digits": 0.95, "large_circle": 0.96}
PROBES = (100, 300, 600)

def configure():
    torch.set_num_threads(1)
    torch.set_default_dtype(torch.float64)

def split_data(task, seed):
    if task == "digits":
        x, y = load_digits(return_X_y=True)
    elif task == "large_circle":
        r = np.random.default_rng(600000 + seed)
        x = r.uniform(-1.0, 1.0, size=(8192, 2))
        y = (np.sum(x*x, axis=1) < 0.55**2).astype(np.int64)
    else:
        raise ValueError(task)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.int64)
    ids = np.arange(len(y))
    work, test = train_test_split(ids, test_size=0.2, random_state=seed, stratify=y)
    train, valid = train_test_split(work, test_size=0.25, random_state=seed+1, stratify=y[work])
    assert not (set(train)&set(valid) or set(train)&set(test) or set(valid)&set(test))
    scaler=StandardScaler().fit(x[train])
    scaled=scaler.transform(x)
    assert np.isfinite(scaled).all()
    parts=[(torch.tensor(scaled[ix],dtype=torch.float32),torch.tensor(y[ix],dtype=torch.long))
           for ix in (train,valid,test)]
    assert len(parts[0][0])+len(parts[1][0])+len(parts[2][0])==len(y)
    return parts,dict(n_total=len(y),n_train=len(train),n_val=len(valid),
                      n_test=len(test),n_classes=int(y.max()+1))

def make_model(input_dim, classes, width, depth, seed):
    base=MLP(input_dim,width,depth,classes,act="relu",residual=False,seed=seed)
    layers=[]
    for i,(w,b) in enumerate(zip(base.W,base.b)):
        affine=nn.Linear(w.shape[1],w.shape[0])
        with torch.no_grad():
            affine.weight.copy_(torch.from_numpy(w))
            affine.bias.copy_(torch.from_numpy(b))
        layers.append(affine)
        if i<depth:layers.append(nn.ReLU())
    return nn.Sequential(*layers).to(torch.float32)

def probe_condition(model, name, samples):
    from pathcond.pathcond import rescaling_path_cond
    with torch.no_grad():
        before=model(samples).detach().clone()
        params=[p.detach().clone() for p in model.parameters()]
    if name=="pathcond_adam":
        tic=time.perf_counter()
        # The original upstream pathnorm code uses a default-dtype dummy input.
        # Align that caller context with native float32 parameters, then restore.
        original_dtype=torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.float32)
            rescaling_path_cond(model,nb_iter_optim_rescaling=10)
        finally:
            torch.set_default_dtype(original_dtype)
        elapsed=time.perf_counter()-tic
    elif name=="adam":
        elapsed=0.0
    else:
        raise ValueError(name)
    with torch.no_grad():
        diff=float((model(samples)-before).abs().max())
        moved=max(float((p-q).abs().max()) for p,q in zip(model.parameters(),params))
    if not math.isfinite(diff) or not math.isfinite(moved) or diff>=1e-3:
        raise FloatingPointError("PathCond initial functional error: "+str(diff))
    if name=="pathcond_adam" and moved <= 1e-12:
        raise FloatingPointError("PathCond produced no nontrivial rescaling")
    if not all(torch.isfinite(p).all() for p in model.parameters()):
        raise FloatingPointError("nonfinite conditioned parameter")
    return dict(seconds=float(elapsed),max_function_drift=diff,max_parameter_change=moved)

def assess(model, x, y):
    with torch.no_grad():
        logits=model(x)
        ce=float(F.cross_entropy(logits,y))
        acc=float((logits.argmax(1)==y).double().mean())
    if not (math.isfinite(ce) and math.isfinite(acc)):
        raise FloatingPointError("nonfinite CE/accuracy")
    return dict(ce=ce,accuracy=acc)

def one(task, width, depth, seed, method):
    record=dict(task=task,width=width,depth=depth,seed=seed,method=method,
                failed=None,precondition=None,initial_gauge_error=None,
                data=None, traces={"identity":[],"neuronwise":[]},
                first_cross={"identity":None,"neuronwise":None},checkpoints={},
                final_logit_gauge_gap=None,compute_seconds=None)
    try:
        data,meta=split_data(task,seed)
        record["data"]=meta
        xt,yt=data[0];xv,yv=data[1];xe,ye=data[2]
        raw=make_model(xt.shape[1],meta["n_classes"],width,depth,seed)
        models={"identity":copy.deepcopy(raw),"neuronwise":gauge_copy(raw,seed)}
        with torch.no_grad():
            err=float((models["identity"](xt[:128])-models["neuronwise"](xt[:128])).abs().max())
        record["initial_gauge_error"]=err
        if not math.isfinite(err) or err>=1e-3:
            raise FloatingPointError("bad initial gauge error "+str(err))
        preps={n:probe_condition(net,method,xt[:128]) for n,net in models.items()}
        record["precondition"]=preps
        accumulated={k:v["seconds"] for k,v in preps.items()}
        optimizers={name:torch.optim.Adam(net.parameters(),lr=LR,betas=(.9,.999),
                          eps=1e-8,weight_decay=0.) for name,net in models.items()}
        batch_rng=np.random.default_rng(10000+seed)
        for step in range(STEPS+1):
            if step %10==0:
                for name,net in models.items():
                    val=assess(net,xv,yv)
                    record["traces"][name].append(dict(step=step,
                        val_accuracy=val["accuracy"],val_ce=val["ce"],
                        compute_seconds=accumulated[name]))
                    if record["first_cross"][name] is None and val["accuracy"]>=TARGETS[task]:
                        record["first_cross"][name]=dict(step=step,
                            compute_seconds=accumulated[name])
            if step in PROBES:
                vals={name:assess(net,xe,ye) for name,net in models.items()}
                with torch.no_grad():
                    gap=float((models["identity"](xe)-models["neuronwise"](xe)).abs().max())
                if not math.isfinite(gap):raise FloatingPointError("nonfinite gauge mismatch")
                record["checkpoints"][str(step)]=dict(
                    identity=vals["identity"],neuronwise=vals["neuronwise"],
                    max_test_logit_gauge_gap=gap)
            if step==STEPS:break
            ix=batch_rng.integers(0,len(xt),size=BATCH)
            xb,yb=xt[ix],yt[ix]
            for name,net in models.items():
                tic=time.perf_counter()
                opt=optimizers[name]
                opt.zero_grad(set_to_none=True)
                F.cross_entropy(net(xb),yb).backward()
                opt.step()
                accumulated[name]+=time.perf_counter()-tic
                if not all(torch.isfinite(p).all() for p in net.parameters()):
                    raise FloatingPointError("nonfinite weight, step "+str(step+1)+" "+name)
        record["compute_seconds"]=accumulated
        record["final_logit_gauge_gap"]=record["checkpoints"]["600"]["max_test_logit_gauge_gap"]
    except Exception as e:
        record["failed"]=(type(e).__name__+": "+str(e))[:320]
    return record

def summarize(records):
    expected=2*2*5*2
    assert len(records)==expected
    cells=[]
    for task in TASKS:
      for width,depth in NETWORKS:
        stats={}
        for method in METHODS:
            rs=[r for r in records if (r["task"],r["width"],r["depth"],r["method"])==
                                        (task,width,depth,method)]
            assert len(rs)==5
            good=[r for r in rs if r["failed"] is None]
            crossed=[r["first_cross"]["identity"]["compute_seconds"] for r in good
                     if r["first_cross"]["identity"] is not None]
            crossed_gauge=[r["first_cross"]["neuronwise"]["compute_seconds"] for r in good
                     if r["first_cross"]["neuronwise"] is not None]
            stepcross=[r["first_cross"]["identity"]["step"] for r in good
                     if r["first_cross"]["identity"] is not None]
            def complete_mean(key, step=600):
                if len(good)!=5:return None
                vals=[r["checkpoints"][str(step)]["identity"][key] for r in good]
                return float(np.mean(vals)) if all(map(math.isfinite,vals)) else None
            stats[method]=dict(
              n=5,failures=5-len(good),crossed=len(crossed),
              crossed_gauge=len(crossed_gauge),
              median_time_to_target=float(np.median(crossed)) if crossed else None,
              median_time_to_target_gauge=float(np.median(crossed_gauge)) if crossed_gauge else None,
              median_steps_to_target=float(np.median(stepcross)) if stepcross else None,
              mean_test_acc_600=complete_mean("accuracy"),
              mean_test_ce_100=complete_mean("ce",100),
              mean_test_ce_300=complete_mean("ce",300),
              mean_test_ce_600=complete_mean("ce",600),
              mean_gauge_gap_600=float(np.mean([r["final_logit_gauge_gap"] for r in good]))
                  if len(good)==5 else None,
              median_init_seconds=float(np.median([r["precondition"]["identity"]["seconds"] for r in good]))
                  if len(good)==5 else None,
              mean_full_training_seconds=float(np.mean([r["compute_seconds"]["identity"] for r in good]))
                  if len(good)==5 else None)
        a=stats["adam"]; p=stats["pathcond_adam"]
        good=(a["failures"]==0 and p["failures"]==0)
        h1=good and a["crossed"]>=4 and p["crossed"]>=4 and (
            p["median_time_to_target"]<a["median_time_to_target"])
        h2=good and a["mean_gauge_gap_600"] is not None and p["mean_gauge_gap_600"] is not None and (
            p["mean_gauge_gap_600"]<a["mean_gauge_gap_600"])
        h3=good and a["mean_test_acc_600"] is not None and p["mean_test_acc_600"] is not None and (
            p["mean_test_acc_600"]>=a["mean_test_acc_600"]-.01)
        cells.append(dict(task=task,width=width,depth=depth,stats=stats,
                          h1_time_win=bool(h1),h2_gauge_win=bool(h2),h3_noninferior=bool(h3)))
    h1=sum(c["h1_time_win"] for c in cells)
    h2=sum(c["h2_gauge_win"] for c in cells)
    h3=sum(c["h3_noninferior"] for c in cells)
    pc=[r for r in records if r["method"]=="pathcond_adam"]
    n_ok=sum(r["failed"] is None and r["precondition"] is not None and
             all(v["max_function_drift"]<1e-3 for v in r["precondition"].values()) for r in pc)
    return dict(n_pairs=len(records),n_trajectories=2*len(records),
                n_failure_pairs=sum(r["failed"] is not None for r in records),
                h1_time_wins=h1,h1_pass=h1>=3,
                h2_gauge_wins=h2,h2_pass=h2>=3,
                h3_noninferiority_cells=h3,h3_pass=h3>=3,
                h4_accepted_pathcond_pairs=n_ok,h4_pass=n_ok==20,cells=cells)

def run(seeds=TARGET_SEEDS):
    configure()
    from pathcond.pathcond import rescaling_path_cond
    assert "pathcond" in inspect.getfile(rescaling_path_cond).lower()
    records=[]
    for task in TASKS:
      for width,depth in NETWORKS:
        for seed in seeds:
          for method in METHODS:
            r=one(task,width,depth,seed,method)
            records.append(r)
            print("G11",task,width,depth,seed,method,"failed",r["failed"],
                  "cross",r["first_cross"]["identity"],
                  "CE600",r["checkpoints"].get("600",{}).get("identity",{}).get("ce"),flush=True)
    result=dict(study="G11",upstream_sha=UPSTREAM_SHA,seeds=tuple(seeds),records=records)
    if tuple(seeds)==TARGET_SEEDS:result["summary"]=summarize(records)
    return result

if __name__=="__main__":
    if "--smoke" in sys.argv:
        r=run((119,))
        assert len(r["records"])==8
        failures=[x for x in r["records"] if x["failed"] is not None]
        if failures:raise RuntimeError("G11 smoke failures: "+str(failures))
        print("PASS G11 8 unused-seed paired smoke runs",flush=True)
    else:
        out=sys.argv[1] if len(sys.argv)>1 else "results/g11/ci_full.json"
        os.makedirs(os.path.dirname(os.path.abspath(out)),exist_ok=True)
        r=run()
        with open(out,"w") as f:json.dump(r,f,indent=2,allow_nan=False)
        print("G11 SCIENTIFIC OUTCOMES",json.dumps(r["summary"],indent=2),flush=True)
