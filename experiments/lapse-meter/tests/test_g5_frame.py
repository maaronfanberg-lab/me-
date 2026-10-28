"""Gauge G5 synthetic tests: covariance, bias escape, nonfinite frame and clipping controls."""
import os,sys,copy
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','experiments'))
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
import numpy as np
from lapse.nets import MLP
from g2_gauge_invariants import reparameterize
from g4_trajectory import scales
from g5_frame import frame_coordinates,frame_step,error_from_gauge
rng=np.random.default_rng(47)
X=rng.standard_normal((37,9));y=rng.integers(0,4,37)
checks=0
for residual in (False,True):
 for signed in ((False,True) if residual else (False,)):
  n=MLP(9,16,6,4,act='relu',residual=residual,seed=7,branch_sign=signed)
  for gauge in ('uniform4','neuronwise'):
   ds=scales(n,gauge,7)
   a=copy.deepcopy(n);b=reparameterize(n,ds)
   f=frame_coordinates(a,X,y)[-1];g=frame_coordinates(b,X,y)[-1]
   assert abs(f-g)<1e-9;checks+=1
   aa,ab,aw,abg,_=frame_coordinates(a,X,y)
   ba,bb,bw,bbg,_=frame_coordinates(b,X,y)
   normerr=max(np.max(np.abs(x*y-u*v)) for x,y,u,v in zip(aa+ab,aw+abg,ba+bb,bw+bbg))
   assert normerr<1e-9,normerr;checks+=1
   old=[x.copy() for x in a.b]
   for step in range(10):
    frame_step(a,X,y);frame_step(b,X,y)
    assert error_from_gauge(a,b,ds)<1e-9;checks+=1
    assert np.max(np.abs(a.forward(X)[1][-1]-b.forward(X)[1][-1]))<1e-9;checks+=1
   assert sum(np.count_nonzero(o!=v) for o,v in zip(old,a.b))>0;checks+=1
n=MLP(9,16,6,4,act='relu',residual=True,seed=7)
for eta,cap in ((-1,1),(0.1,0),(.1,float('nan')), (float('inf'),1)):
 try:frame_step(n,X,y,eta,cap)
 except ValueError:checks+=1
 else:raise AssertionError('bad eta/cap accepted')
orig=copy.deepcopy(n)
frame_step(n,X,y,0,1)
assert all(np.array_equal(p,q) for p,q in zip(orig.W+orig.b,n.W+n.b));checks+=1
n=MLP(9,16,6,4,act='relu',residual=True,seed=7)
n.W[3][1,2]=0.
frame_step(n,X,y)
assert n.W[3][1,2]!=0;checks+=1
print(f'PASS {checks} G5 covariance, signed skips, clipping and zero-parameter checks')
