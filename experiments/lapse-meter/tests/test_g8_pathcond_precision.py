"""Synthetic checks + independent smoke for G8A (seed 59 is NOT G8 target set)."""
import os,sys,copy
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','experiments'))
import torch
from g7_official_pathcond import setup,make_model,gauge_copy
from g8_pathcond_precision import independent_double_bz,run_case,param_max_diff
from pathcond.rescaling_polyn import optimize_rescaling_polynomial,reweight_model_inplace
setup()
for depth in (3,6):
    model,_=make_model(8,4,depth,59)
    x=torch.randn(24,8,dtype=torch.float64)
    gauged=gauge_copy(model,59)
    with torch.no_grad():assert (model(x)-gauged(x)).abs().max()<1e-10
    bz64=independent_double_bz(copy.deepcopy(model))
    bz32,_=optimize_rescaling_polynomial(copy.deepcopy(model),n_iter=10,tol=1e-2,resnet=False)
    assert bz64.dtype==torch.float64
    assert bz32.dtype==torch.float32
    assert torch.equal(bz64.float(),bz32), 'Diagnostic primitives differ from released optimizer factors'
    orig=copy.deepcopy(model)
    rounded=copy.deepcopy(model)
    reweight_model_inplace(orig,bz32)
    reweight_model_inplace(rounded,bz64.to(torch.float32))
    assert param_max_diff(orig,rounded)==0
r=run_case('digits',3,59,'identity')
assert r['failed'] is None,r
assert r['instrumentation_valid'],r
assert r['max_rounding_in_bz']>0
print('PASS G8 upstream primitive identity, strict A-C control, unused seed59 smoke',flush=True)
