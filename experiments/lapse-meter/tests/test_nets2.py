"""Checks for lapse/nets2.py (two-matrix residual blocks). Run: python tests/test_nets2.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from lapse.nets import MLP
from lapse.nets2 import MLP2
from lapse.probe import diagnose2
R = []
def check(name, ok, detail=""):
    R.append(ok); print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else "")); assert ok, name

rng = np.random.default_rng(0); X = rng.standard_normal((30, 6)); y = rng.integers(0, 3, 30)
for act in ("relu", "tanh"):
    net = MLP2(6, 8, 5, 3, act=act, seed=2)
    loss, gW, gb, deltas, gV = net.backward(X, y)
    worst = 0.0
    for name, P, G in (("W", net.W, gW), ("b", net.b, gb), ("V", net.V, gV)):
        for i in range(len(P)):
            if P[i] is None: continue
            for _ in range(3):
                idx = tuple(rng.integers(0, s) for s in P[i].shape)
                old = P[i][idx]; P[i][idx] = old + 1e-6; lp = net.loss(X, y); P[i][idx] = old - 1e-6; lm = net.loss(X, y); P[i][idx] = old
                worst = max(worst, abs((lp - lm) / 2e-6 - G[i][idx]) / max(1e-8, abs(G[i][idx]) + abs((lp - lm) / 2e-6)))
    check(f"{act}: every gradient matches finite differences", worst < 1e-5, f"worst relative error {worst:.1e}")
    dg, dl = diagnose2(net, X, y)
    check(f"{act}: diagnose2 deltas equal backward", max(np.max(np.abs(u - v)) for u, v in zip(dl, deltas)) == 0.0)
    s = dg["ln_out"] + dg["ln_transport"] + dg["ln_gate"]
    check(f"{act}: three parts add to T*", abs(s - dg["Tstar"]) < 1e-12)
a, b = MLP2(6, 8, 5, 3, seed=7), MLP(6, 8, 5, 3, act="relu", residual=True, seed=7)
check("W and b at initialisation are exactly MLP's", all(np.array_equal(u, v) for u, v in zip(a.W, b.W)))
print(f"{sum(R)}/{len(R)} two-matrix checks passed")
