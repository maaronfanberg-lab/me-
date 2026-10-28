"""Experiment 30, measured before writing its pre-registration: the step-one readout kick and its common-mode share.

kick         as in e22_predictors.py: RMS over the 256-example probe batch of |dz|, the logit change from one SGD
             step on the readout alone at its step-1 learning rate.
common       the common-mode share of that change: |mean_i dz_i|^2 / mean_i |dz_i|^2. 1 = every example's logits
             move the same way (a pure bias shift); about 1/n = unrelated moves.
pile         stream growth, |h_L| / |h_1| (RMS over the batch), on the stream itself (not the readout's input).
logit0       RMS of the initial logits.
Usage: python experiments/e30_measure.py  ->  results/e30_init.json (configs from e30_jobs.txt and their references)
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
from e22_predictors import build, step1_lr
from lapse.nets_ln import MLPLN


def measure(cfg):
    c, net, X, y = build(cfg)
    L = len(net.W)
    r = net.backward(X, y); gW, gb = r[1], r[2]
    h, z = net.forward(X)
    hL = net.readout_input(X) if isinstance(net, MLPLN) else h[-2]
    eta = step1_lr(c, net, ("W", L - 1))
    dz = hL @ (-eta * gW[L - 1]).T - eta * gb[L - 1]
    kick = float(np.sqrt(np.mean(np.sum(dz * dz, 1))))
    common = float(np.sum(dz.mean(0) ** 2) / np.mean(np.sum(dz * dz, 1)))
    rms = lambda a: float(np.sqrt(np.mean(np.sum(a * a, 1))))
    last = h[-1] if isinstance(net, MLPLN) else h[-2]  # the last stream, before any readout offset or LayerNorm
    pile = rms(last) / rms(h[1])
    return dict(kick=kick, common=common, pile=pile, logit0=rms(z[-1]))


if __name__ == "__main__":
    out = {}
    cfgs = [json.loads(l.split("\t")[0]) for l in open(os.path.join(HERE, "e30_jobs.txt")) if l.strip()]
    refs = []
    for t in ("digits", "circle-clean"):
        for s in range(3):
            refs += [dict(task=t, depth=96, seed=s, act="relu"), dict(task=t, depth=96, seed=s, act="relu", branch_sign=True),
                     dict(task=t, depth=96, seed=s, act="relu", block="ln", ln="center")]
    for cfg in refs + cfgs:
        k = json.dumps(cfg, sort_keys=True)
        if k in out: continue
        out[k] = measure(cfg); print(k, {a: round(b, 3) for a, b in out[k].items()}, flush=True)
    os.makedirs(os.path.join(HERE, "..", "results"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "..", "results", "e30_init.json"), "w"), indent=1)
