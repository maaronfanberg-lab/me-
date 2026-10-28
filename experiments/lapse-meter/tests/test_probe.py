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
