"""G8A: upstream PathCond float32-cast precision ablation (not a new optimizer).
See GAUGE_G8A_PREREGISTRATION.md. Uses original upstream primitives unchanged.
"""
import copy,json,math,os,sys,time
import numpy as np
import torch
from torch import nn
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
from g7_official_pathcond import setup,make_model,gauge_copy
from g6_benchmark import dataset
UPSTREAM_SHA='535b202e3476c64d5e7e9ec5e817344fb5cfd787'
SEEDS=tuple(range(60,70))
TASKS=('digits','circle')
DEPTHS=(3,6)
GAUGES=('identity','neuronwise')

def independent_double_bz(model):
    """Same author's optimization primitives, without the published final fp32 cast."""
    from pathcond.network_to_optim import compute_diag_G,compute_B_mlp
    from pathcond.rescaling_polyn import update_z_polynomial
    from pathcond.utils import MLPCompatibilityWrapper
    diag=compute_diag_G(model).to(dtype=torch.float64)
    wrapped=MLPCompatibilityWrapper(model)
    layers=[layer for layer in wrapped.model if isinstance(layer,nn.Linear)]
    assert len(layers)>=2
    n_hidden=sum(layer.out_features for layer in layers[:-1])
    pos,neg=compute_B_mlp(wrapped)
    bz,z=update_z_polynomial(diag,pos,neg,10,n_hidden,1e-2)
    if bz.dtype!=torch.float64 or not torch.isfinite(bz).all() or not torch.isfinite(z).all():
        raise FloatingPointError('nonfinite or non-double upstream BZ')
    return bz

def param_max_diff(a,b):
    return max(float((x-y).abs().max()) for x,y in zip(a.parameters(),b.parameters()))

def max_logit_delta(model,original,x):
    with torch.no_grad():
        a=model(x);b=original(x)
        if not torch.isfinite(a).all() or not torch.isfinite(b).all():
            raise FloatingPointError('nonfinite logit')
        return float((a-b).abs().max())

def run_case(task,depth,seed,gauge):
    from pathcond.pathcond import rescaling_path_cond
    from pathcond.rescaling_polyn import reweight_model_inplace
    (tr,val,te),meta=dataset(task,seed)
    model,_=make_model(tr[0].shape[1],meta['classes'],depth,seed)
    if gauge=='neuronwise':model=gauge_copy(model,seed)
    elif gauge!='identity':raise ValueError('bad gauge name')
    xtr=torch.as_tensor(tr[0][:128],dtype=torch.float64)
    xte=torch.as_tensor(te[0],dtype=torch.float64)
    result=dict(task=task,depth=depth,seed=seed,gauge=gauge,failed=None)
    start=time.perf_counter()
    try:
        a=copy.deepcopy(model);b=copy.deepcopy(model);c=copy.deepcopy(model)
        rescaling_path_cond(a,nb_iter_optim_rescaling=10)
        bz64=independent_double_bz(b)
        bz32=bz64.to(torch.float32)
        reweight_model_inplace(b,bz64)
        reweight_model_inplace(c,bz32)
        delta_param=param_max_diff(a,c)
        quantization=float((bz64-bz32.to(torch.float64)).abs().max())
        result.update(official_vs_rounded_max_parameter_difference=delta_param,
            max_rounding_in_bz=quantization,
            diagnostic_changed_parameters=param_max_diff(model,b),
            official_changed_parameters=param_max_diff(model,a))
        for name,m in (('official',a),('double',b),('rounded',c)):
            result[name+'_train_max_logit_change']=max_logit_delta(m,model,xtr)
            result[name+'_test_max_logit_change']=max_logit_delta(m,model,xte)
        result['official_vs_rounded_test_max_logit_difference']=max_logit_delta(a,c,xte)
        result['instrumentation_valid']=(delta_param<1e-10 and
            result['official_vs_rounded_test_max_logit_difference']<1e-10)
        result['double_strict_pass']=bool(result['double_test_max_logit_change']<1e-10)
        ae=result['official_test_max_logit_change'];be=result['double_test_max_logit_change']
        result['eligible_for_h3']=(ae>1e-10)
        result['tenfold_improvement']=(be<=ae/10.) if ae>1e-10 else None
        result['original_h1_failure']=bool(ae>=1e-7)
    except Exception as exc:
        result['failed']=type(exc).__name__+': '+str(exc)[:400]
        result['instrumentation_valid']=False
    result['elapsed_seconds']=time.perf_counter()-start
    return result

def summarize(records):
    assert len(records)==len(TASKS)*len(DEPTHS)*len(SEEDS)*len(GAUGES)
    usable=[r for r in records if not r['failed'] and r.get('instrumentation_valid',False)]
    eligible=[r for r in usable if r['eligible_for_h3']]
    improved=[r for r in eligible if r['tenfold_improvement']]
    h1=sum(r['double_strict_pass'] for r in usable)
    quantized=sum(r['max_rounding_in_bz']>0 for r in usable)
    return dict(n_total=len(records),n_usable=len(usable),
        n_failed=sum(bool(r['failed']) for r in records),
        h1_double_strict_n=h1,h1_pass=(len(usable)==80 and h1>=72),
        h2_matching_original_n=len(usable),h2_quantized_n=quantized,
        h2_pass=(len(usable)==80 and quantized>=64),
        h3_eligible_n=len(eligible),h3_improved_n=len(improved),
        h3_decision=('INCONCLUSIVE' if len(eligible)<10 else
            'PASS' if len(usable)==80 and 4*len(improved)>=3*len(eligible) else 'FAIL'),
        official_fail_1e7_n=sum(r['official_test_max_logit_change']>=1e-7 for r in usable),
        double_fail_1e7_n=sum(r['double_test_max_logit_change']>=1e-7 for r in usable),
        official_median_error=float(np.median([r['official_test_max_logit_change'] for r in usable])) if usable else None,
        double_median_error=float(np.median([r['double_test_max_logit_change'] for r in usable])) if usable else None,
        official_max_error=max((r['official_test_max_logit_change'] for r in usable),default=None),
        double_max_error=max((r['double_test_max_logit_change'] for r in usable),default=None))

def run():
    setup();records=[]
    for task in TASKS:
        for depth in DEPTHS:
            for seed in SEEDS:
                for gauge in GAUGES:
                    r=run_case(task,depth,seed,gauge);records.append(r)
                    print(f'{task:6s} d{depth} seed{seed} {gauge:10s} '
                        f'official={r.get("official_test_max_logit_change")} '
                        f'double={r.get("double_test_max_logit_change")} '
                        f'error={r["failed"]}',flush=True)
    return dict(study='G8A',upstream_sha=UPSTREAM_SHA,records=records,summary=summarize(records))

if __name__=='__main__':
    if '--smoke' in sys.argv:
        setup();r=run_case('digits',3,59,'identity')
        print(json.dumps(r,indent=2))
        if r['failed'] or not r['instrumentation_valid']:raise SystemExit('smoke failed')
    else:
        output=sys.argv[1] if len(sys.argv)>1 else 'results/g8a/ci_precision.json'
        os.makedirs(os.path.dirname(os.path.abspath(output)),exist_ok=True)
        outcome=run()
        with open(output,'w') as f:json.dump(outcome,f,indent=2,allow_nan=False)
        print('G8A',json.dumps(outcome['summary'],indent=2),flush=True)
