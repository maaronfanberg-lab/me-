"""Checks for experiments/e22_predictors.py against explicit Hessians. Run: python tests/test_e22_predictors.py"""
import sys, os, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "experiments")); sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
from e22_predictors import predictors, build, params, get, grads, step1_lr
R = []
def check(name, ok, detail=""):
    R.append(ok); print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else "")); assert ok, name
def explicit(cfg, e=1e-5):
    """Explicit Hessian by central differences, used as a reference only when it is the same at two step sizes
    (a step that flips a ReLU gate gives a fake curvature of order 1/eps; see CORRECTIONS 35)."""
    c, net, X, y = build(cfg); P = params(net); eta = {k: step1_lr(c, net, k) for k in P}
    def flat():
        G = grads(net, X, y); return np.concatenate([np.sqrt(eta[k]) * G[k[0]][k[1]].ravel() for k in P])
    idx = [(k, j) for k in P for j in range(get(net, k).size)]; H = np.zeros((len(idx), len(idx)))
    for col, (k, j) in enumerate(idx):
        a = get(net, k).reshape(-1); s = np.sqrt(eta[k]); a[j] += e * s; gp = flat(); a[j] -= 2 * e * s; gm = flat(); a[j] += e * s
        H[:, col] = (gp - gm) / (2 * e)
    return np.linalg.eigvalsh((H + H.T) / 2)
cases = [dict(task="circle-clean", act="tanh", depth=3, width=4, seed=0),
         dict(task="circle-clean", act="relu", depth=4, width=5, seed=1, block="two"),
         dict(task="circle-clean", act="relu", depth=3, width=4, seed=2, warmup=500, warmup_parts="out"),
         dict(task="circle-clean", act="relu", depth=4, width=8, seed=11, branch_sign=True),
         dict(task="digits", act="relu", depth=3, width=16, seed=6)]
for cfg in cases:
    ev, ev2 = explicit(cfg), explicit(cfg, 1e-6)
    stable = abs(ev.max() - ev2.max()) < 1e-4 * max(1, abs(ev.max()))
    check(f"reference is step-size stable, {cfg}", stable, f"max eig {ev.max():.5f} at 1e-5, {ev2.max():.5f} at 1e-6")
    p = predictors(cfg); got = p["sharp"]
    check(f"sharpness matches reference, {cfg}", abs(got - ev.max()) < 1e-4 * max(1, abs(ev.max())),
          f"Lanczos {got:.5f}, explicit max {ev.max():.5f} (min {ev.min():.5f}); kink failures {p['hvp_kink_failures']}")
# a case where the largest |eigenvalue| is negative must still return the most positive one
import scipy.sparse.linalg as _sl
neg = None
for sd in range(30):
    cfg = dict(task="circle-clean", act="tanh", depth=4, width=5, seed=sd, sigma_w=2.5)
    ev = explicit(cfg)
    if abs(ev.min()) > abs(ev.max()): neg = (cfg, ev); break
check("found a case whose largest-magnitude eigenvalue is negative", neg is not None)
cfg, ev = neg
check("Lanczos returns the most positive eigenvalue there", abs(predictors(cfg)["sharp"] - ev.max()) < 1e-4 * max(1, abs(ev.max())),
      f"got {predictors(cfg)['sharp']:.5f}, explicit max {ev.max():.5f}, min {ev.min():.5f}")
print(f"{sum(R)}/{len(R)} predictor checks passed")
