"""Independent replication of the core results of experiments 8-14, sharing NO code with the lapse library.

Written 2026-10-28 and pushed to GitHub before it was run. Everything is reimplemented from scratch here: data
preparation, network, backward pass, the transport measure, the training loop. Only numpy and scikit-learn's
bundled digits images are used. Several choices deliberately differ from the library's, so a result that
depended on one of them would show up as a failure to replicate:

  - digits: pixels scaled to [0, 1] and centred by their mean only (the library also divides by each pixel's
    standard deviation); an 80/20 split instead of 1,400 / 397
  - circle: newly generated, inner disc of radius 1 against an outer ring from 1.4 to 2.0, 600 points, with
    inputs up to 2 in size (the library's circle is scaled to under 1)
  - seeds 100-102, never used by the library

Network: input layer h0 = relu(W0 x + b0); 95 residual blocks h_l = h_{l-1} + a * f(W_l h_{l-1} + b_l) with
a = 1/sqrt(96); linear readout; softmax cross-entropy. Weights N(0, 1/fan_in), biases 0, width 64. SGD lr 0.05,
batch 64, 6,000 steps. This is the same architecture as the library's, written independently.

Transport = ln( RMS_examples |dL/dh_1| / RMS_examples |dL/dh_95| ), on 256 fixed training examples, read at the
first log where full training loss is below 0.03 (no interpolation, unlike the library, another deliberate
difference).

PREDICTIONS, from experiments 8-14, fixed before running. For each task, 3 seeds:
  R1  plain ReLU:                     mean transport below +0.30 (experiments 8: +0.12 digits, +0.07 circle)
  R2  ReLU with a 50-step warm-up:    mean above +0.50
  R3  ReLU, warm-up on readout only:  mean above +0.50 (500 steps, readout gradient scaled, blocks at full lr)
  R4  signed ReLU (random fixed +-1 per block and unit): mean above +0.50
  R5  the gradient check below passes (relative error < 1e-5), or no result counts
Each prediction holds or fails per task; there is no partial credit.

Usage: python independent/replicate.py <task digits|circle> <cond plain|warm50|warmout|signed> <seed> out.json
       python independent/replicate.py gradcheck
"""
import sys, os, json
import numpy as np


def data(task, seed):
    rng = np.random.default_rng(seed)
    if task == "digits":
        from sklearn.datasets import load_digits
        d = load_digits(); X = d.data / 16.0; y = d.target
        X = X - X.mean(0)
    else:
        n = 600; inner = rng.random(n) < 0.5
        r = np.where(inner, rng.random(n), 1.4 + 0.6 * rng.random(n)); t = rng.random(n) * 2 * np.pi
        X = np.stack([r * np.cos(t), r * np.sin(t)], 1); y = inner.astype(int)
    p = rng.permutation(len(X)); X, y = X[p], y[p]; k = int(0.8 * len(X))
    return X[:k], y[:k], X[k:], y[k:]


class Net:
    def __init__(self, din, dout, seed, width=64, blocks=95, signed=False):
        g = np.random.default_rng(seed)
        self.a = 1 / np.sqrt(blocks + 1)
        self.Ws = [g.normal(0, 1 / np.sqrt(din), (din, width))] + \
                  [g.normal(0, 1 / np.sqrt(width), (width, width)) for _ in range(blocks)] + \
                  [g.normal(0, 1 / np.sqrt(width), (width, dout))]          # stored input-by-output
        self.bs = [np.zeros(w.shape[1]) for w in self.Ws]
        s = np.random.default_rng(seed + 31337)
        self.sign = [s.choice([-1.0, 1.0], width) if signed else np.ones(width) for _ in range(blocks)]

    def run(self, X, y):
        """Forward and backward. Returns loss, gradients, and dL/dh after the first and last block."""
        n = len(X); pre, hs = [], []
        u = X @ self.Ws[0] + self.bs[0]; pre.append(u); h = np.maximum(u, 0); hs.append(h)
        for l in range(len(self.sign)):
            hs_in = h
            u = h @ self.Ws[l + 1] + self.bs[l + 1]; pre.append(u)
            h = hs_in + self.a * self.sign[l] * np.maximum(u, 0); hs.append(h)
        z = h @ self.Ws[-1] + self.bs[-1]
        z = z - z.max(1, keepdims=True); e = np.exp(z); P = e / e.sum(1, keepdims=True)
        loss = -np.mean(np.log(P[np.arange(n), y]))
        dz = P; dz[np.arange(n), y] -= 1; dz /= n
        gW = [None] * len(self.Ws); gb = [None] * len(self.Ws)
        gW[-1] = hs[-1].T @ dz; gb[-1] = dz.sum(0)
        dh = dz @ self.Ws[-1].T; stream = {len(self.sign): dh}
        for l in range(len(self.sign) - 1, -1, -1):          # block l maps hs[l] -> hs[l+1]
            du = dh * self.a * self.sign[l] * (pre[l + 1] > 0)
            gW[l + 1] = hs[l].T @ du; gb[l + 1] = du.sum(0)
            dh = dh + du @ self.Ws[l + 1].T
            stream[l] = dh                                      # dL/dh after block l-1 (l=0: after input layer)
        du = dh * (pre[0] > 0); gW[0] = X.T @ du; gb[0] = du.sum(0)
        return loss, gW, gb, stream


def transport(net, X, y):
    _, _, _, st = net.run(X, y)
    rms = lambda a: np.sqrt(np.mean(np.sum(a * a, 1)))
    return float(np.log(rms(st[1]) / rms(st[len(net.sign)])))   # after block 1 vs after the last block


def gradcheck():
    rng = np.random.default_rng(0); X = rng.normal(size=(20, 5)); y = rng.integers(0, 3, 20)
    worst = 0.0
    for signed in (False, True):
        net = Net(5, 3, 4, width=8, blocks=6, signed=signed)
        _, gW, gb, _ = net.run(X, y)
        for i in range(len(net.Ws)):
            for _ in range(4):
                j, k = rng.integers(0, net.Ws[i].shape[0]), rng.integers(0, net.Ws[i].shape[1])
                o = net.Ws[i][j, k]
                net.Ws[i][j, k] = o + 1e-6; lp = net.run(X, y)[0]
                net.Ws[i][j, k] = o - 1e-6; lm = net.run(X, y)[0]; net.Ws[i][j, k] = o
                fd = (lp - lm) / 2e-6
                worst = max(worst, abs(fd - gW[i][j, k]) / max(1e-9, abs(fd) + abs(gW[i][j, k])))
    print(f"gradient check: worst relative error {worst:.1e}", "PASS" if worst < 1e-5 else "FAIL")
    return worst < 1e-5


def main(task, cond, seed, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    X, y, Xt, yt = data(task, seed)
    net = Net(X.shape[1], int(y.max()) + 1, seed, signed=(cond == "signed"))
    rng = np.random.default_rng(seed + 99)
    log = []
    for s in range(6001):
        if s % 50 == 0:
            log.append(dict(step=s, loss=float(net.run(X, y)[0]), transport=transport(net, X[:256], y[:256])))
        if s == 6000: break
        b = rng.integers(0, len(X), 64)
        _, gW, gb, _ = net.run(X[b], y[b])
        k_all = min(1.0, (s + 1) / 50) if cond == "warm50" else 1.0
        k_out = min(1.0, (s + 1) / 500) if cond == "warmout" else 1.0
        for i in range(len(net.Ws)):
            k = k_all * (k_out if i == len(net.Ws) - 1 else 1.0)
            net.Ws[i] -= 0.05 * k * gW[i]; net.bs[i] -= 0.05 * k * gb[i]
    hit = next((e["transport"] for e in log if e["loss"] < 0.03), None)
    zt = Xt  # test accuracy
    h = np.maximum(zt @ net.Ws[0] + net.bs[0], 0)
    for l in range(len(net.sign)):
        h = h + net.a * net.sign[l] * np.maximum(h @ net.Ws[l + 1] + net.bs[l + 1], 0)
    acc = float(((h @ net.Ws[-1] + net.bs[-1]).argmax(1) == yt).mean())
    json.dump(dict(task=task, cond=cond, seed=seed, transport_at_0_03=hit, test_acc=acc, log=log), open(path, "w"))
    print(f"{task} {cond} s{seed}: transport at loss 0.03 = {hit}, final loss {log[-1]['loss']:.4f}, test acc {acc:.3f}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "gradcheck":
        sys.exit(0 if gradcheck() else 1)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
