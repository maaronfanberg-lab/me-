"""Checks for lapse/nets_ln.py. Run: python tests/test_nets_ln.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from lapse.nets import MLP
from lapse.nets_ln import MLPLN, ln_fwd, ln_bwd
R = []
def check(name, ok, detail=""):
    R.append(ok); print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else "")); assert ok, name
rng = np.random.default_rng(0); X = rng.standard_normal((25, 6)); y = rng.integers(0, 3, 25)
# LayerNorm backward alone
x = rng.standard_normal((5, 7)); dy = rng.standard_normal((5, 7)); _, c = ln_fwd(x); dx = ln_bwd(dy, c); e = 1e-6; worst = 0.0
for j in range(7):
    xp = x.copy(); xp[2, j] += e; xm = x.copy(); xm[2, j] -= e
    fd = (np.sum(ln_fwd(xp)[0] * dy) - np.sum(ln_fwd(xm)[0] * dy)) / (2 * e); worst = max(worst, abs(fd - dx[2, j]))
check("LayerNorm backward matches finite differences", worst < 1e-7, f"max abs err {worst:.1e}")
for ln in ("none", "final", "pre", "pre_final", "post", "center", "center_random", "offset", "dyt", "bcenter"):
    for act, signed in (("tanh", False), ("relu", True)):   # tanh: no kinks, so finite differences are exact; relu signed too
        net = MLPLN(6, 8, 5, 3, act=act, ln=ln, seed=2, branch_sign=signed)
        if ln.startswith("center"): net.set_center(X)
        if ln == "offset": net.set_offset(X, 8, 5, seed=2)
        _, gW, gb, _, _ = net.backward(X, y); worst = 0.0
        for i in range(len(net.W)):
            for _ in range(3):
                j, k = rng.integers(0, net.W[i].shape[0]), rng.integers(0, net.W[i].shape[1]); o = net.W[i][j, k]
                net.W[i][j, k] = o + 1e-6; lp = net.loss(X, y); net.W[i][j, k] = o - 1e-6; lm = net.loss(X, y); net.W[i][j, k] = o
                fd = (lp - lm) / 2e-6; worst = max(worst, abs(fd - gW[i][j, k]) / max(1e-8, abs(fd) + abs(gW[i][j, k])))
            j = rng.integers(0, net.b[i].shape[0]); o = net.b[i][j]
            net.b[i][j] = o + 1e-6; lp = net.loss(X, y); net.b[i][j] = o - 1e-6; lm = net.loss(X, y); net.b[i][j] = o
            fd = (lp - lm) / 2e-6; worst = max(worst, abs(fd - gb[i][j]) / max(1e-8, abs(fd) + abs(gb[i][j])))
        check(f"ln={ln}, {act}{' signed' if signed else ''}: gradients match finite differences", worst < 1e-5, f"worst rel err {worst:.1e}")
# ln="none" must be the library's MLP exactly
a = MLPLN(6, 8, 5, 3, act="relu", ln="none", seed=4); b = MLP(6, 8, 5, 3, act="relu", residual=True, seed=4)
ra, rb = a.backward(X, y), b.backward(X, y)
check('ln="none" equals lapse.nets.MLP (weights, loss, every delta)', all(np.array_equal(u, v) for u, v in zip(a.W, b.W)) and ra[0] == rb[0]
      and all(np.allclose(u, v, rtol=0, atol=1e-14) for u, v in zip(ra[3], rb[3])))
a = MLPLN(6, 8, 5, 3, act="relu", ln="none", seed=4, branch_sign=True); b = MLP(6, 8, 5, 3, act="relu", residual=True, seed=4, branch_sign=True)
check("branch signs equal lapse.nets.MLP's", all(np.array_equal(u, v) for u, v in zip(a.S[1:-1], b.S[1:-1])))
c1 = MLPLN(6, 8, 5, 3, act="relu", ln="center", seed=4); c1.set_center(X)
check("center: the readout input averages to zero over X at initialisation", np.max(np.abs(c1.readout_input(X).mean(0))) < 1e-12)
c2 = MLPLN(6, 8, 5, 3, act="relu", ln="center_random", seed=4); c2.set_center(X)
check("center_random: offset has m0's norm", abs(np.linalg.norm(c2.center) - np.linalg.norm(c1.center)) < 1e-9)
c3 = MLPLN(6, 8, 5, 3, act="relu", ln="offset", seed=4, branch_sign=True); c3.set_offset(X, 8, 5, seed=4)
check("offset: equals minus the plain ReLU twin's mean last stream", np.allclose(c3.center, -c1.center, rtol=0, atol=1e-12))
c4 = MLPLN(6, 8, 5, 3, act="relu", ln="none", seed=4, branch_sign=True)
h3, z3 = c3.forward(X); h4, z4 = c4.forward(X)
check("offset: the stream is untouched and the logits move by exactly W_out m_relu",
      all(np.array_equal(u, v) for u, v in zip(h3, h4)) and np.allclose(z3[-1] - z4[-1], -c3.center @ c3.W[-1].T, rtol=0, atol=1e-12))
print(f"{sum(R)}/{len(R)} LayerNorm-network checks passed")
