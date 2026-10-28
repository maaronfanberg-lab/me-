"""The explicit readout Hessian in experiments/escape_check.py against finite differences of the exact readout gradient.
Run: python tests/test_escape_check.py"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, os.path.join(HERE, "..", "experiments"))
import numpy as np
from lapse.nets import MLP
from escape_check import readout_hessian
rng = np.random.default_rng(0); X = rng.standard_normal((20, 5)); y = rng.integers(0, 3, 20)
net = MLP(5, 6, 4, 3, act="relu", residual=True, seed=1)
H = readout_hessian(net, X); K, d = 3, 7
def g():
    r = net.backward(X, y); return np.hstack([r[1][-1], r[2][-1][:, None]]).ravel()  # class-major, bias last
worst = 0.0
for j in range(K * d):
    k, c = divmod(j, d); e = 1e-6
    tgt = (net.W[-1], (k, c)) if c < d - 1 else (net.b[-1], (k,))
    o = tgt[0][tgt[1]]; tgt[0][tgt[1]] = o + e; gp = g(); tgt[0][tgt[1]] = o - e; gm = g(); tgt[0][tgt[1]] = o
    worst = max(worst, float(np.max(np.abs((gp - gm) / (2 * e) - H[:, j]))))
ok = worst < 1e-6
print(("PASS" if ok else "FAIL") + f" readout Hessian matches finite differences (max abs err {worst:.1e})")
print(f"{int(ok)}/1 escape-check checks passed"); sys.exit(0 if ok else 1)
