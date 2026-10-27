"""A tiny character-level language model, trained here, whose depth geometry we measure.

Model: the previous CONTEXT characters, one-hot, feed an input projection, then DEPTH hidden layers
(residual or plain), then a softmax over the character set. Corpus: the plain-text software licences in
/usr/share/common-licenses (the only sizeable English text available offline in this environment).
Usage: python experiments/tiny_lm.py <residual 0|1> <opt sgd|adam> <seed> out.json
"""
import sys, os, json, glob, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse import geometry
from lapse.nets import MLP, SGD, Adam

CONTEXT, DEPTH, WIDTH, STEPS, BATCH = 16, 24, 128, 6000, 64
LOG_AT = [0, 100, 300, 1000, 2000, 4000, 6000]


def corpus():
    names = ["Apache-2.0", "GPL-3", "GFDL-1.3", "Artistic", "BSD", "MPL-2.0", "LGPL-3", "CC0-1.0"]
    txt = ""
    for n in names:
        p = os.path.join("/usr/share/common-licenses", n)
        if os.path.exists(p):
            txt += open(p, encoding="utf-8", errors="ignore").read() + "\n"
    txt = " ".join(txt.split())  # collapse whitespace
    chars = sorted(set(txt))
    return txt, chars


def encode(txt, chars):
    idx = {c: i for i, c in enumerate(chars)}
    return np.array([idx[c] for c in txt], dtype=np.int64)


def batch(ids, starts, V):
    X = np.zeros((len(starts), CONTEXT * V))
    for r, s in enumerate(starts):
        X[r, np.arange(CONTEXT) * V + ids[s:s + CONTEXT]] = 1.0
    return X, ids[starts + CONTEXT]


def sample(net, ids, chars, seed, n=240):
    V = len(chars); r = np.random.default_rng(seed)
    ctx = list(ids[:CONTEXT]); out = []
    for _ in range(n):
        X = np.zeros((1, CONTEXT * V)); X[0, np.arange(CONTEXT) * V + np.array(ctx[-CONTEXT:])] = 1
        z = net.forward(X)[1][-1][0]; p = np.exp(z - z.max()); p /= p.sum()
        c = r.choice(V, p=p); out.append(chars[c]); ctx.append(c)
    return "".join(out)


def main(residual, opt_name, seed, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)  # fail early, not after training
    txt, chars = corpus(); ids = encode(txt, chars); V = len(chars)
    split = int(0.9 * len(ids))
    tr, te = ids[:split], ids[split:]
    net = MLP(CONTEXT * V, WIDTH, DEPTH, V, act="tanh", sigma_w=1.0, residual=residual, seed=seed)
    opt = SGD(0.1) if opt_name == "sgd" else Adam(1e-3)
    rng = np.random.default_rng(seed + 99)
    probe_starts = np.random.default_rng(1).integers(0, len(te) - CONTEXT - 1, 512)
    Xp, yp = batch(te, probe_starts, V)
    log = []
    t0 = time.time()
    for s in range(STEPS + 1):
        if s in LOG_AT:
            _, _, _, d = net.backward(Xp, yp)
            g = geometry(net.geometry_deltas(d))
            log.append(dict(step=s, lapse=g.lapse.tolist(), tilt=g.tilt, kappa=g.kappa,
                            test_loss_bits=net.loss(Xp, yp) / np.log(2)))
            print(f"step {s} test {log[-1]['test_loss_bits']:.3f} bits/char  {g.summary()}", flush=True)
        if s == STEPS: break
        st = rng.integers(0, len(tr) - CONTEXT - 1, BATCH)
        X, y = batch(tr, st, V)
        _, gW, gb, _ = net.backward(X, y)
        opt.step(net, gW, gb)
    res = dict(residual=residual, opt=opt_name, seed=seed, chars=len(chars), corpus_chars=len(ids),
               log=log, sample=sample(net, te, chars, seed), seconds=time.time() - t0,
               unigram_bits=float(-(np.bincount(tr, minlength=V) / len(tr) * np.log2(np.bincount(tr, minlength=V) / len(tr) + 1e-300)).sum()))
    json.dump(res, open(path, "w"))
    print("SAMPLE:", res["sample"])


if __name__ == "__main__":
    main(bool(int(sys.argv[1])), sys.argv[2], int(sys.argv[3]), sys.argv[4])
