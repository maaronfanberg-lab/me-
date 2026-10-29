"""G7A preflight: official PathCond, PyTorch/NumPy G5 parity, and valid gauges."""
import inspect,sys,os
import numpy as np
import torch
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','experiments'))
from g7_official_pathcond import setup,preflight,make_model,condition,gauge_copy,run_one
from g6_benchmark import dataset
from pathcond.pathcond import rescaling_path_cond
setup()
assert 'pathcond' in inspect.getfile(rescaling_path_cond).lower()
preflight()
for task in ('digits','circle'):
    (tr,va,te),meta=dataset(task,40)
    assert len(tr[0])+len(va[0])+len(te[0]) in (1797,1800)
    assert abs(tr[0].mean())<1e-10
    for depth in (3,6):
        net,_=make_model(tr[0].shape[1],meta['classes'],depth,40)
        x=torch.tensor(tr[0][:128],dtype=torch.float64)
        base=net(x).detach().clone()
        transformed=gauge_copy(net,40)
        assert float((base-transformed(x)).abs().max())<1e-11
        cond=condition(net,x)
        cond2=condition(transformed,x)
        assert cond['max_initial_logit_change']<1e-7
        assert cond2['max_initial_logit_change']<1e-7
        assert float((net(x)-transformed(x)).abs().max())<1e-7
print('PASS G7 original PathCond preserves outputs on 4 model/task combinations')
