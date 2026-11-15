"""Residual MLP with two-matrix blocks, the form used in ResNets and transformer feed-forward layers:

    z_l = W_l h_{l-1} + b_l,   h_l = h_{l-1} + alpha * V_l act(z_l)

with an input projection (layer 0, h_0 = act(W_0 x + b_0), no V) and a linear output layer, softmax cross-entropy.
Same interface as lapse.nets.MLP where experiments need it: forward, loss, backward, accuracy, alpha, act, W, b,
plus V (index 0 and the last index are None). Used from experiment 17. tests/test_nets2.py checks every gradient
against finite differences."""
from __future__ import annotations
import numpy as np
from .nets import ACTS


class MLP2:
    residual = True
    S = None  # no branch signs; keeps lapse.probe-style code paths simple

    def __init__(self, din, width, depth, dout, act="relu", sigma_w=1.0, alpha=None, seed=0, sigma_v=1.0):
        self.act = act
        self.alpha = 1.0 / np.sqrt(depth) if alpha is None else alpha
        rng = np.random.default_rng(seed)
        dims = [din] + [width] * depth + [dout]
        self.W, self.b = [], []
        for i in range(len(dims) - 1):
            self.W.append(rng.standard_normal((dims[i + 1], dims[i])) * sigma_w / np.sqrt(dims[i]))
            self.b.append(np.zeros(dims[i + 1]))
        vrng = np.random.default_rng(seed + 5_555_555)  # separate generator: W and b are exactly MLP's
        self.V = [None] + [vrng.standard_normal((width, width)) * sigma_v / np.sqrt(width) for _ in range(depth - 1)] + [None]

    def forward(self, X):
        f, _ = ACTS[self.act]
        h, z, a = [X], [], []
        L = len(self.W)
        for i in range(L):
            zi = h[-1] @ self.W[i].T + self.b[i]; z.append(zi)
            if i == L - 1:
                h.append(zi); a.append(None)
            elif i == 0:
                h.append(f(zi)); a.append(None)
            else:
                ai = f(zi); a.append(ai)
                h.append(h[-1] + self.alpha * ai @ self.V[i].T)
        self._a = a
        return h, z

    def loss(self, X, y):
        out = self.forward(X)[1][-1]
        out = out - out.max(1, keepdims=True)
        lp = out - np.log(np.exp(out).sum(1, keepdims=True))
        return float(-lp[np.arange(len(y)), y].mean())

    def backward(self, X, y, return_stream=False):
        """Returns (loss, gW, gb, deltas, gV); deltas[i] = dL/dz_i. With return_stream, also g (dL/dh after block i)."""
        _, df = ACTS[self.act]
        h, z = self.forward(X); a = self._a
        n, L = len(X), len(self.W)
        out = z[-1] - z[-1].max(1, keepdims=True)
        p = np.exp(out); p /= p.sum(1, keepdims=True)
        loss = float(-np.log(p[np.arange(n), y] + 1e-300).mean())
        d = p.copy(); d[np.arange(n), y] -= 1.0; d /= n
        deltas, gV, g = [None] * L, [None] * L, [None] * L
        deltas[-1] = d
        gh = d @ self.W[-1]
        for i in range(L - 2, -1, -1):
            g[i] = gh
            if i > 0:
                ga = self.alpha * gh @ self.V[i]          # dL/d act(z_i)
                gV[i] = self.alpha * gh.T @ a[i]
                deltas[i] = ga * df(z[i])
                gh = gh + deltas[i] @ self.W[i]
            else:
                deltas[i] = gh * df(z[i]); gh = deltas[i] @ self.W[i]
        gW = [deltas[i].T @ h[i] for i in range(L)]
        gb = [deltas[i].sum(0) for i in range(L)]
        return (loss, gW, gb, deltas, gV, g) if return_stream else (loss, gW, gb, deltas, gV)

    def accuracy(self, X, y):
        return float((self.forward(X)[1][-1].argmax(1) == y).mean())
