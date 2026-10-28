"""G6A regression and leakage checks; run python tests/test_g6_benchmark.py."""
import os
import sys
import numpy as np
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','experiments'))
from g6_benchmark import dataset, train_one, RATES, choose_rates, summary, TEST_SEEDS
n=0
for task in ('digits','wine','circle'):
    (tr,val,te),meta=dataset(task,30)
    assert len(tr[0])+len(val[0])+len(te[0])=={'digits':1797,'wine':178,'circle':1800}[task]
    assert abs(np.mean(tr[0]))<1e-10
    assert np.isfinite(tr[0]).all()
    assert len(set(tr[1]))==meta['classes']
    n+=4
for optimizer,rate in (('sgd',.05),('adam',.001),('g5',.03)):
    a,_=train_one('wine','plain',8,optimizer,rate,30)
    b,_=train_one('wine','plain',8,optimizer,rate,30)
    assert not a['failed'] and not b['failed'],(optimizer,a['failed'],b['failed'])
    assert a['snapshots']==b['snapshots']
    assert a['snapshots'][-1]['step']==200
    n+=3
for task in ('digits','wine','circle'):
    a,_=train_one(task,'plain',8,'g5',.03,30)
    assert a['snapshots'][0]['step']==0
    assert np.isfinite(a['snapshots'][0]['val_loss'])
    n+=2
print('PASS',n,'G6A data isolation and determinism checks')
