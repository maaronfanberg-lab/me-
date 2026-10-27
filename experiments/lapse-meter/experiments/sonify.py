"""Train a network while logging its lapse densely, then render the measured lapse as sound.
Usage: python experiments/sonify.py <piece> out.wav     pieces: horizon | settling | residual
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse.nets import MLP, SGD
from lapse.core import lapse_profile
from lapse import data as D
from lapse.sound import render, write_wav

PIECES = {
    "horizon":  dict(act="sigmoid", sigma_w=1.0, residual=False, depth=12, steps=1500, every=10),
    "settling": dict(act="tanh", sigma_w=0.8, residual=False, depth=24, steps=3000, every=20),
    "residual": dict(act="tanh", sigma_w=1.0, residual=True, depth=24, steps=3000, every=20),
}


def main(piece, path):
    c = PIECES[piece]
    X, y, Xt, yt = D.digits(0)
    net = MLP(64, 64, c["depth"], 10, act=c["act"], sigma_w=c["sigma_w"], residual=c["residual"], seed=0)
    opt, rng = SGD(0.05), np.random.default_rng(1)
    hist, acc = [], []
    for s in range(c["steps"] + 1):
        if s % c["every"] == 0:
            d = net.backward(X[:256], y[:256])[3]
            hist.append(lapse_profile(net.geometry_deltas(d)))
            acc.append(net.accuracy(Xt, yt))
        if s == c["steps"]: break
        idx = rng.integers(0, len(X), 64)
        _, gW, gb, _ = net.backward(X[idx], y[idx]); opt.step(net, gW, gb)
    H = np.array(hist)
    audio = render(H, seconds_per_log=0.12)
    write_wav(path, audio)
    json.dump(dict(piece=piece, cfg=c, lapse=H.tolist(), test_acc=acc), open(path + ".json", "w"))
    print(f"{piece}: {len(H)} logs, {len(audio)/48000:.1f}s audio, lapse first layer {H[0,0]:.2e} -> {H[-1,0]:.2e}, acc {acc[0]:.2f} -> {acc[-1]:.2f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
