"""Experiment 5 (closes CORRECTIONS entry 10): does error/activity alignment explain weight-motion spread?

For a batch, layer l's weight gradient is G_l = delta_l^T h_l. Its size factors exactly as
    ||G_l||_F = A_l * ||delta_l||_F * ||h_l||_F,      0 <= A_l <= 1 (alignment)
The earlier prediction used ||delta|| * ||h|| and so assumed A_l is the same in every layer.
Here we measure A_l per layer, and check that lr*||G_l||/||W_l|| on a batch reproduces the measured motion.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse.nets import MLP
from lapse import data as D

R = os.path.join(os.path.dirname(__file__), "..", "results")
CFGS = {"plain-tanh-0.8": dict(act="tanh", sigma_w=0.8, residual=False),
        "plain-tanh-1.0": dict(act="tanh", sigma_w=1.0, residual=False),
        "res-tanh": dict(act="tanh", sigma_w=1.0, residual=True)}
rg = lambda v: float(v.max() / v.min())
rows = []
print("| network | seed | measured motion spread | predicted by ‖δ‖·‖h‖/‖W‖ | predicted by actual gradient ‖δᵀh‖/‖W‖ | alignment A spread | A first → last layer |")
print("|---|---|---|---|---|---|---|")
for name, c in CFGS.items():
    for s in range(3):
        d = json.load(open(os.path.join(R, "e2", f"{name}_sgd_s{s}.json")))
        X, y, _, _ = D.digits(s)
        net = MLP(64, 64, 24, 10, seed=s, **c)
        rng = np.random.default_rng(10_000 + s)          # same batch stream as the run
        G, P, A = [], [], []
        for _ in range(20):                               # average over the run's first 20 batches
            idx = rng.integers(0, len(X), 64)
            h, _ = net.forward(X[idx]); _, gW, _, dl = net.backward(X[idx], y[idx])
            k = len(net.W) - 1
            G.append([np.linalg.norm(gW[i]) / np.linalg.norm(net.W[i]) for i in range(k)])
            P.append([np.linalg.norm(dl[i]) * np.linalg.norm(h[i]) / np.linalg.norm(net.W[i]) for i in range(k)])
            A.append([np.linalg.norm(gW[i]) / (np.linalg.norm(dl[i]) * np.linalg.norm(h[i])) for i in range(k)])
        G, P, A = (np.mean(np.array(v), 0) for v in (G, P, A))
        m = np.array(d["clock"]["motion"])[:len(G)]
        rows.append(dict(net=name, seed=s, motion=rg(m), prox=rg(P), grad=rg(G), align=rg(A),
                         corr_grad=float(np.corrcoef(np.log(G), np.log(m))[0, 1])))
        print(f"| {name} | {s} | ×{rg(m):.1f} | ×{rg(P):.1f} | ×{rg(G):.1f} | ×{rg(A):.1f} | {A[0]:.3f} → {A[-1]:.3f} |")
json.dump(rows, open(os.path.join(R, "e5_alignment.json"), "w"), indent=1)
print("\ncorrelation of log(actual-gradient prediction) with log(measured motion) across layers:",
      ", ".join(f"{r['net']} s{r['seed']}: {r['corr_grad']:.2f}" for r in rows))


# ---- Part 2: the same quantities measured at every step of the actual 200-step run (one time base) ----
from lapse.nets import SGD
print("\nPart 2: every quantity measured on the same steps (the 200 steps of the clock run, same batches).\n")
print("| network | seed | measured motion spread | ‖δ‖·‖h‖/‖W‖ spread | lr·‖δᵀh‖/‖W‖ spread | alignment spread | max error, lr·‖δᵀh‖/‖W‖ vs motion |")
print("|---|---|---|---|---|---|---|")
rows2 = []
for name, c in CFGS.items():
    for s in range(3):
        X, y, _, _ = D.digits(s)
        net = MLP(64, 64, 24, 10, seed=s, **c); opt = SGD(0.05)
        rng = np.random.default_rng(10_000 + s)
        k = len(net.W) - 1
        M = np.zeros(k); P = np.zeros(k); G = np.zeros(k); A = np.zeros(k)
        for step in range(200):
            idx = rng.integers(0, len(X), 64)
            h, _ = net.forward(X[idx]); _, gW, gb, dl = net.backward(X[idx], y[idx])
            Wn = np.array([np.linalg.norm(net.W[i]) for i in range(k)])
            before = [w.copy() for w in net.W[:k]]
            opt.step(net, gW, gb)
            M += np.array([np.linalg.norm(net.W[i] - before[i]) for i in range(k)]) / Wn
            P += np.array([np.linalg.norm(dl[i]) * np.linalg.norm(h[i]) for i in range(k)]) / Wn
            G += 0.05 * np.array([np.linalg.norm(gW[i]) for i in range(k)]) / Wn
            A += np.array([np.linalg.norm(gW[i]) / (np.linalg.norm(dl[i]) * np.linalg.norm(h[i])) for i in range(k)])
        M, P, G, A = M / 200, P / 200, G / 200, A / 200
        err = float(np.max(np.abs(G / M - 1)))
        rows2.append(dict(net=name, seed=s, motion=rg(M), prox=rg(P), grad=rg(G), align=rg(A), identity_err=err))
        print(f"| {name} | {s} | ×{rg(M):.2f} | ×{rg(P):.2f} | ×{rg(G):.2f} | ×{rg(A):.2f} | {err:.1e} |")
json.dump(dict(part1=rows, part2=rows2), open(os.path.join(R, "e5_alignment.json"), "w"), indent=1)


# ---- Part 3: re-check the README's cancellation claim on one time base ----
print("\nPart 3: lapse and input activity, each averaged over the same 200 steps (direction: first layer vs last).\n")
print("| network | seed | lapse spread | lapse first/last | activity spread | activity first/last | product spread |")
print("|---|---|---|---|---|---|---|")
rows3 = []
for name, c in CFGS.items():
    for s in range(3):
        X, y, _, _ = D.digits(s)
        net = MLP(64, 64, 24, 10, seed=s, **c); opt = SGD(0.05)
        rng = np.random.default_rng(10_000 + s); k = len(net.W) - 1
        Nl = np.zeros(k); Ac = np.zeros(k)
        for step in range(200):
            idx = rng.integers(0, len(X), 64)
            h, _ = net.forward(X[idx]); _, gW, gb, dl = net.backward(X[idx], y[idx])
            out = np.linalg.norm(dl[-1])
            Nl += np.array([np.linalg.norm(dl[i]) / out for i in range(k)])
            Ac += np.array([np.linalg.norm(h[i]) for i in range(k)])
            opt.step(net, gW, gb)
        Nl, Ac = Nl / 200, Ac / 200
        rows3.append(dict(net=name, seed=s, lapse=rg(Nl), lapse_dir=float(Nl[0] / Nl[-1]), act=rg(Ac), act_dir=float(Ac[0] / Ac[-1]), prod=rg(Nl * Ac)))
        print(f"| {name} | {s} | ×{rg(Nl):.1f} | {Nl[0]/Nl[-1]:.3g} | ×{rg(Ac):.1f} | {Ac[0]/Ac[-1]:.3g} | ×{rg(Nl*Ac):.2f} |")
json.dump(dict(part1=rows, part2=rows2, part3=rows3), open(os.path.join(R, "e5_alignment.json"), "w"), indent=1)
