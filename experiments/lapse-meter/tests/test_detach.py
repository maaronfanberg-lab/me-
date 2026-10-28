"""Checks for the detach option of lapse.nets.MLP (experiment 33). Run: python tests/test_detach.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from lapse.nets import MLP
R = []
def check(name, ok):
    R.append(ok); print(("PASS " if ok else "FAIL ") + name); assert ok, name
rng = np.random.default_rng(0); X = rng.standard_normal((30, 6)); y = rng.integers(0, 3, 30)
a = MLP(6, 8, 6, 3, act="relu", residual=True, seed=1); b = MLP(6, 8, 6, 3, act="relu", residual=True, seed=1); b.detach = "mean"
ra, rb = a.backward(X, y), b.backward(X, y); h = a.forward(X)[0]; L = len(a.W)
u = h[-2].mean(0); u /= np.linalg.norm(u)
check("forward pass and loss unchanged", ra[0] == rb[0])
check("readout's own gradient unchanged", np.array_equal(ra[1][-1], rb[1][-1]) and np.array_equal(ra[2][-1], rb[2][-1]))
gh_a = ra[3][-1] @ a.W[-1]; gh_b = gh_a - np.outer(gh_a @ u, u)
d_last = gh_b * a.alpha * (a.forward(X)[1][L - 2] > 0)
check("top block's delta equals the true one with the u-component of dL/dh removed", np.allclose(rb[3][L - 2], d_last, rtol=0, atol=1e-14))
check("detached top stream gradient has no u-component", abs(float(np.max(np.abs(gh_b @ u)))) < 1e-12)
c = MLP(6, 8, 6, 3, act="relu", residual=True, seed=1); c.detach = "random"; rc = c.backward(X, y)
check("random control changes the blocks' gradients differently from mean", not np.allclose(rc[1][1], rb[1][1]) and not np.allclose(rc[1][1], ra[1][1]))
# experiment 35: with block_nomean, each block's own step-0 update does not move its mean pre-activation on that minibatch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments"))
from probe_run import run
import e4
snap = []
run(dict(task="digits", depth=6, steps=1, log_every=1, block_nomean=True), hook=lambda net, X_, y_: snap.append(([w.copy() for w in net.W], [v.copy() for v in net.b], net)) or {})
(W0, b0, net_), (W1, b1, _) = snap[0], snap[1]
Xd = e4.make("digits", 0)[0]; idx = np.random.default_rng(10_000).integers(0, len(Xd), 64)
net_.W, net_.b = W0, b0; hs = net_.forward(Xd[idx])[0]
worst = max(float(np.max(np.abs(hs[i].mean(0) @ (W1[i] - W0[i]).T + (b1[i] - b0[i])))) for i in range(1, len(W0) - 1))
moved = max(float(np.max(np.abs(W1[i] - W0[i]))) for i in range(1, len(W0) - 1))
check("block_nomean: own update leaves each block's minibatch-mean pre-activation fixed (weights did move)", worst < 1e-12 and moved > 1e-8)
print(f"{sum(R)}/{len(R)} detach checks passed")
