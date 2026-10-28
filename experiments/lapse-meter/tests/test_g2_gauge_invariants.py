"""G2 synthetic controls: python tests/test_g2_gauge_invariants.py"""
import os,sys
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','experiments'))
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
import numpy as np
from lapse.nets import MLP
from g2_gauge_invariants import scales,reparameterize,compare,diagnostic,hidden_grads
rng=np.random.default_rng(17)
X=rng.standard_normal((29,9));y=rng.integers(0,4,29)
count=0
for residual in (True,False):
    for sign in ((False,True) if residual else (False,)):
        net=MLP(9,16,6,4,act='relu',residual=residual,seed=7,branch_sign=sign)
        for gauge in ('identity','uniform4','neuronwise'):
            r=compare(net,X,y,gauge,7)
            assert r['max_logit_error']<1e-9 and r['max_activation_work_rel_error']<1e-9
            assert r['max_parameter_pressure_rel_error']<1e-9
            count+=1
        before=[w.copy() for w in net.W]
        reparameterize(net,scales(net,'neuronwise',7))
        assert all(np.array_equal(a,b) for a,b in zip(net.W,before))
        count+=1
        d=diagnostic(net,X,y)
        assert np.all(d['activation_work']>0)
        count+=1

net=MLP(9,12,5,4,act='relu',residual=True,seed=2)
h,z=net.forward(X);g=hidden_grads(net,X,y)
i,j,eps=2,4,1e-6
def downstream_loss(state):
    cur=state.copy()
    for k in range(i+1,len(net.W)):
        zz=cur@net.W[k].T+net.b[k]
        if k==len(net.W)-1:logits=zz
        elif net.residual and k>0:cur=cur+net.alpha*np.maximum(zz,0)
        else:cur=np.maximum(zz,0)
    logits=logits-logits.max(1,keepdims=True)
    lp=logits-np.log(np.exp(logits).sum(1,keepdims=True))
    return -lp[np.arange(len(y)),y].mean()
p=h[i+1].copy();m=p.copy()
p[0,j]+=eps;m[0,j]-=eps
fd=(downstream_loss(p)-downstream_loss(m))/(2*eps)
assert abs(fd-g[i][0,j])<1e-7,(fd,g[i][0,j])
count+=1
_,gw,gb,_=net.backward(X,y)
net.W[i][j,3]+=eps;lp=net.loss(X,y)
net.W[i][j,3]-=2*eps;lm=net.loss(X,y)
net.W[i][j,3]+=eps
assert abs((lp-lm)/(2*eps)-gw[i][j,3])<1e-7
count+=1
net=MLP(9,16,6,4,act='relu',residual=True,seed=7)
broken=reparameterize(net,scales(net,'neuronwise',7))
broken.W[-1]=net.W[-1].copy()
assert np.max(np.abs(net.forward(X)[1][-1]-broken.forward(X)[1][-1]))>1e-4
count+=1
for residual in (True,False):
    net=MLP(9,16,6,4,act='tanh',residual=residual,seed=7)
    try:reparameterize(net,[np.ones(16) for _ in range(net.depth)])
    except ValueError:count+=1
    else:raise AssertionError('tanh not eligible')
net=MLP(9,16,6,4,act='relu',residual=True,seed=7)
ds=scales(net,'neuronwise',7);ds[2]=2*ds[2]
try:reparameterize(net,ds)
except ValueError:count+=1
else:raise AssertionError('residual scales must agree')
print(f'PASS {count} G2 synthetic, negative-control, finite-difference checks')
