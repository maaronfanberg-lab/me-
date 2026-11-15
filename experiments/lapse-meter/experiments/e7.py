"""Experiment 7: tilt against training loss at several depths. See E7_PREREGISTRATION.md.
Usage: python experiments/e7.py <task digits|circle-clean> <act tanh|relu> <depth> <seed> out.json
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from lapse import geometry
from lapse.nets import MLP, SGD
import e4


def main(task, act, depth, seed, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)  # fail early, not after training
    X, y, Xt, yt = e4.make(task, seed)
    ncls = int(max(y.max(), yt.max()) + 1)
    net = MLP(X.shape[1], 64, depth, ncls, act=act, sigma_w=1.0, residual=True, seed=seed)
    opt, rng = SGD(0.05), np.random.default_rng(10_000 + seed)
    log = []
    for s in range(6001):
        if s % 50 == 0:
            d = net.backward(X[:256], y[:256])[3]
            g = geometry(net.geometry_deltas(d, remove_alpha=True))
            log.append(dict(step=s, Tstar=g.tilt, train_loss=net.loss(X, y)))
        if s == 6000: break
        idx = rng.integers(0, len(X), 64)
        _, gW, gb, _ = net.backward(X[idx], y[idx])
        if not all(np.all(np.isfinite(w)) for w in gW):
            break
        opt.step(net, gW, gb)
    json.dump(dict(task=task, act=act, depth=depth, seed=seed, test_acc=net.accuracy(Xt, yt), log=log), open(path, "w"))
    print(f"{task} {act} d{depth} s{seed}: T* {log[0]['Tstar']:+.2f} -> {log[-1]['Tstar']:+.2f}  loss {log[-1]['train_loss']:.4f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
