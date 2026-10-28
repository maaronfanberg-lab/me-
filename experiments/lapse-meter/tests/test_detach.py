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
print(f"{sum(R)}/{len(R)} detach checks passed")
