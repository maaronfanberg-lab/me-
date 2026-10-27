"""Experiment 4: which property of a task sets the trained total tilt? See E4_PREREGISTRATION.md.
Usage: python experiments/e4.py <condition> <arch res24|plain12> <seed> out.json
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse import geometry
from lapse.nets import MLP, SGD
from lapse import data as D


def make(condition, seed):
    r = np.random.default_rng(1000 + seed)
    if condition.startswith("circle"):
        noise = {"circle-clean": 0.0, "circle-noisier": 0.30}.get(condition, 0.15)
        X, y, Xt, yt = D.circle(seed, n=1000, noise=noise)
        # test labels: always the clean rule, so accuracy measures the true boundary
        Xt_clean_lab = (np.hypot(Xt[:, 0] * 5, Xt[:, 1] * 5) < 2.5).astype(int)
        if condition == "circle-embed64":
            Q, _ = np.linalg.qr(np.random.default_rng(77).standard_normal((64, 2)))
            X, Xt = X @ Q.T * np.sqrt(32), Xt @ Q.T * np.sqrt(32)   # unit-ish scale per input
        if condition == "circle-std1":
            mu, sd = X.mean(0), X.std(0); X, Xt = (X - mu) / sd, (Xt - mu) / sd
        if condition == "circle-pad62noise":
            X = np.hstack([X, r.standard_normal((len(X), 62))])
            Xt = np.hstack([Xt, r.standard_normal((len(Xt), 62))])
        return X, y, Xt, Xt_clean_lab
    X, y, Xt, yt = D.digits(seed)
    if condition == "digits-2class":
        y, yt = (y >= 5).astype(int), (yt >= 5).astype(int)
    if condition == "digits-pca2":
        mu = X.mean(0); U, S, Vt = np.linalg.svd(X - mu, full_matrices=False)
        P = Vt[:2].T
        X, Xt = (X - mu) @ P, (Xt - mu) @ P
        s = X.std(0); X, Xt = X / s, Xt / s
    if condition == "digits-noisy":
        flip = r.random(len(y)) < 0.20
        y = y.copy(); y[flip] = r.integers(0, 10, flip.sum())
    return X, y, Xt, yt


def main(condition, arch, seed, path):
    X, y, Xt, yt = make(condition, seed)
    ncls = int(max(y.max(), yt.max()) + 1)
    residual, depth = (True, 24) if arch == "res24" else (False, 12)
    net = MLP(X.shape[1], 64, depth, ncls, act="tanh", sigma_w=1.0, residual=residual, seed=seed)
    opt, rng = SGD(0.05), np.random.default_rng(10_000 + seed)
    log = []
    for s in range(4001):
        if s in (0, 1000, 4000):
            d = net.backward(X[:256], y[:256])[3]
            g = geometry(net.geometry_deltas(d, remove_alpha=True))
            log.append(dict(step=s, Tstar=g.tilt, kappa=g.kappa, lapse=g.lapse.tolist(),
                            test_acc=net.accuracy(Xt, yt), train_loss=net.loss(X, y)))
        if s == 4000: break
        idx = rng.integers(0, len(X), 64)
        _, gW, gb, _ = net.backward(X[idx], y[idx]); opt.step(net, gW, gb)
    json.dump(dict(condition=condition, arch=arch, seed=seed, n_inputs=X.shape[1], n_classes=ncls, log=log), open(path, "w"))
    print(f"{condition} {arch} s{seed}: T* {log[0]['Tstar']:+.2f} -> {log[-1]['Tstar']:+.2f}  acc {log[-1]['test_acc']:.3f}  loss {log[-1]['train_loss']:.3f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
