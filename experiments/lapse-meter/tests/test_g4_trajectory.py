"""Synthetic Gauge G4 checks; run python tests/test_g4_trajectory.py."""
import os,sys,copy
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','experiments'))
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
import numpy as np
from lapse.nets import MLP
from g2_gauge_invariants import reparameterize
from g4_trajectory import log_parameter_step, scales, gauge_parameter_error

rng=np.random.default_rng(987);X=rng.standard_normal((25,9));y=rng.integers(0,4,25)
checks=0
for residual in (True,False):
 for signed in ((False,True) if residual else (False,)):
  net=MLP(9,12,6,4,act='relu',residual=residual,seed=8,branch_sign=signed)
  for gauge in ('uniform4','neuronwise'):
   ds=scales(net,gauge,8)
   trial=reparameterize(net,ds)
   assert np.max(np.abs(net.forward(X)[1][-1]-trial.forward(X)[1][-1]))<1e-10;checks+=1
   _,gw,gb,_=net.backward(X,y);_,gwt,gbt,_=trial.backward(X,y)
   maxerr=max(np.max(np.abs(w*g-z*h)) for w,g,z,h in zip(net.W+net.b,gw+gb,trial.W+trial.b,gwt+gbt))
   assert maxerr<1e-9,(residual,signed,gauge,maxerr);checks+=1
   for eta in (0.,.1,2.):
    a=copy.deepcopy(net);b=copy.deepcopy(trial)
    log_parameter_step(a,gw,gb,eta);log_parameter_step(b,gwt,gbt,eta)
    assert np.max(np.abs(a.forward(X)[1][-1]-b.forward(X)[1][-1]))<1e-9
    assert gauge_parameter_error(a,b,ds)<1e-9
    checks+=1
   a=copy.deepcopy(net);orig=[p.copy() for p in a.W+a.b]
   log_parameter_step(a,gw,gb,2.)
   for p,old in zip(a.W+a.b,orig):
    assert np.all(p[old==0]==0)
    assert np.all(np.sign(p[old!=0])==np.sign(old[old!=0]))
   checks+=1
net=MLP(9,12,6,4,act='relu',seed=4,residual=True)
_,gw,gb,_=net.backward(X,y)
i,j,k=3,2,5;eps=1e-6
orig=net.W[i][j,k];pred=orig*gw[i][j,k]
net.W[i][j,k]=orig*np.exp(eps);lp=net.loss(X,y)
net.W[i][j,k]=orig*np.exp(-eps);lm=net.loss(X,y)
net.W[i][j,k]=orig
fd=(lp-lm)/(2*eps)
assert abs(fd-pred)<1e-7,(fd,pred);checks+=1
broken=reparameterize(net,scales(net,'neuronwise',4));broken.W[-1]=net.W[-1].copy()
assert np.max(np.abs(net.forward(X)[1][-1]-broken.forward(X)[1][-1]))>1e-4;checks+=1
bad=MLP(9,12,6,4,act='tanh',seed=2)
try:reparameterize(bad,[np.ones(12) for _ in range(6)])
except ValueError:checks+=1
else:raise AssertionError('tanh gauge accepted')
try:log_parameter_step(net,gw,gb,-1.)
except ValueError:checks+=1
else:raise AssertionError('negative eta accepted')
print(f'PASS {checks} G4 synthetic invariance / failure-mode / derivative checks')
