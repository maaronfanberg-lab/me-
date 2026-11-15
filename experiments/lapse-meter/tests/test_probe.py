"""Checks for lapse/probe.py. Run: python tests/test_probe.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from lapse import geometry
from lapse.nets import MLP
from lapse.probe import diagnose
R = []
def check(name, ok, detail=""):
    R.append(ok); print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else "")); assert ok, name
rng = np.random.default_rng(0); X = rng.standard_normal((50, 12)); y = rng.integers(0, 4, 50)
for act in ("tanh", "relu"):
    net = MLP(12, 16, 20, 4, act=act, residual=True, seed=1)
    for _ in range(3):  # move off init so the check is not special to it
        net.W = [w + 0.05 * rng.standard_normal(w.shape) for w in net.W]
    dg, dl = diagnose(net, X, y)
    ref = net.backward(X, y)[3]
    check(f"{act}: probe deltas equal MLP.backward", max(np.max(np.abs(a - b)) for a, b in zip(dl, ref)) == 0.0)
    T = geometry(net.geometry_deltas(ref, remove_alpha=True)).tilt
    check(f"{act}: probe T* equals geometry T*", abs(dg["Tstar"] - T) < 1e-12, f"{dg['Tstar']:.6f} vs {T:.6f}")
    s = dg["ln_out"] + dg["ln_transport"] + dg["ln_gate"]
    check(f"{act}: three parts add to T*", abs(s - T) < 1e-12, f"sum {s:.6f}")
print(f"{sum(R)}/{len(R)} probe checks passed")
# branch_sign: gradients must still be exact (finite differences) and probe must match backward
net = MLP(12, 16, 10, 4, act="relu", residual=True, seed=4, branch_sign=True)
dg, dl = diagnose(net, X, y); ref = net.backward(X, y)
R2 = max(np.max(np.abs(a - b)) for a, b in zip(dl, ref[3]))
check("branch_sign: probe deltas equal MLP.backward", R2 == 0.0)
i, j, k, eps = 3, 2, 5, 1e-6
net.W[i][j, k] += eps; lp = net.loss(X, y); net.W[i][j, k] -= 2 * eps; lm = net.loss(X, y); net.W[i][j, k] += eps
fd = (lp - lm) / (2 * eps)
check("branch_sign: gradient matches finite difference", abs(fd - ref[1][i][j, k]) < 1e-7 * max(1, abs(fd)), f"{fd:.3e} vs {ref[1][i][j, k]:.3e}")
plain = MLP(12, 16, 10, 4, act="relu", residual=True, seed=4)
fresh = MLP(12, 16, 10, 4, act="relu", residual=True, seed=4, branch_sign=True)  # (net above was nudged by the finite difference)
check("branch_sign leaves the initial weights unchanged", all(np.array_equal(a, b) for a, b in zip(plain.W, fresh.W)))
print(f"{sum(R)}/{len(R)} probe checks passed (with branch_sign)")
# branch_sign = 1.0 (every sign +1) must be plain ReLU exactly
a = MLP(12, 16, 10, 4, act="relu", residual=True, seed=4, branch_sign=1.0); b = MLP(12, 16, 10, 4, act="relu", residual=True, seed=4)
ra, rb = a.backward(X, y), b.backward(X, y)
check("branch_sign = 1.0 is plain ReLU bit for bit", ra[0] == rb[0] and all(np.array_equal(u, v) for u, v in zip(ra[3], rb[3])))
print(f"{sum(R)}/{len(R)} probe checks passed (all)")
# Momentum with mu = 0 must be plain SGD exactly (experiment 21)
from lapse.nets import Momentum, SGD
a = MLP(12, 16, 6, 4, act="tanh", residual=True, seed=1); b = MLP(12, 16, 6, 4, act="tanh", residual=True, seed=1)
oa, ob = Momentum(0.05, mu=0.0), SGD(0.05)
for _ in range(5):
    _, g1, h1, _ = a.backward(X, y); oa.step(a, g1, h1); _, g2, h2, _ = b.backward(X, y); ob.step(b, g2, h2)
check("Momentum with mu = 0 is SGD bit for bit", all(np.array_equal(u, v) for u, v in zip(a.W, b.W)))
print(f"{sum(R)}/{len(R)} probe checks passed (all, with optimizers)")
# z-loss gradient (experiment 24) must match finite differences of CE + zloss * mean(logZ^2)
zn = MLP(12, 16, 6, 4, act="relu", residual=True, seed=9); zn.zloss = 0.05
def total(net):
    out = net.forward(X)[1][-1]; m = out.max(1, keepdims=True); lz = np.log(np.exp(out - m).sum(1)) + m[:, 0]
    return net.loss(X, y) + net.zloss * np.mean(lz ** 2)
_, gzW, _, _ = zn.backward(X, y); worst = 0.0
for i in range(len(zn.W)):
    j, k = 0, 1; o = zn.W[i][j, k]
    zn.W[i][j, k] = o + 1e-6; lp = total(zn); zn.W[i][j, k] = o - 1e-6; lm = total(zn); zn.W[i][j, k] = o
    fd = (lp - lm) / 2e-6; worst = max(worst, abs(fd - gzW[i][j, k]) / max(1e-9, abs(fd) + abs(gzW[i][j, k])))
check("z-loss gradient matches finite differences", worst < 1e-5, f"worst relative error {worst:.1e}")
check("z-loss off by default", MLP(12, 16, 6, 4, act="relu", residual=True, seed=9).zloss == 0.0)
print(f"{sum(R)}/{len(R)} probe checks passed (all, with z-loss)")
