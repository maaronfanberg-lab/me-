"""Experiment 6: tilt against training loss, logged densely. See E6_PREREGISTRATION.md.
Usage: python experiments/e6.py <condition> <seed> out.json
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from lapse import geometry
from lapse.nets import MLP, SGD
from lapse import data as D
import e4


def make(condition, seed):
    if condition in ("digits-5class", "digits-3class"):
        X, y, Xt, yt = D.digits(seed)
        f = (lambda v: v // 2) if condition == "digits-5class" else (lambda v: v % 3)
        return X, f(y), Xt, f(yt)
    return e4.make(condition, seed)


def main(condition, seed, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)  # fail early, not after training
    X, y, Xt, yt = make(condition, seed)
    ncls = int(max(y.max(), yt.max()) + 1)
    net = MLP(X.shape[1], 64, 24, ncls, act="tanh", sigma_w=1.0, residual=True, seed=seed)
    opt, rng = SGD(0.05), np.random.default_rng(10_000 + seed)
    log = []
    for s in range(6001):
        if s % 100 == 0:
            d = net.backward(X[:256], y[:256])[3]
            g = geometry(net.geometry_deltas(d, remove_alpha=True))
            log.append(dict(step=s, Tstar=g.tilt, train_loss=net.loss(X, y), test_acc=net.accuracy(Xt, yt)))
        if s == 6000: break
        idx = rng.integers(0, len(X), 64)
        _, gW, gb, _ = net.backward(X[idx], y[idx]); opt.step(net, gW, gb)
    json.dump(dict(condition=condition, seed=seed, n_classes=ncls, log=log), open(path, "w"))
    print(f"{condition} s{seed}: T* {log[0]['Tstar']:+.2f} -> {log[-1]['Tstar']:+.2f}  loss {log[-1]['train_loss']:.4f}  acc {log[-1]['test_acc']:.3f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
