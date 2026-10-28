"""Small numpy networks that expose every layer's error signal, for measuring depth geometry.

Plain MLP:     z_l = W_l h_{l-1} + b_l,  h_l = act(z_l)
Residual MLP:  z_l = W_l h_{l-1} + b_l,  h_l = h_{l-1} + alpha * act(z_l)     (hidden width fixed)
Both have an input projection (layer 0) and a linear output layer; loss is softmax cross-entropy.
`backward` returns dL/dz for every layer, which is exactly what lapse.core consumes.
"""
from __future__ import annotations
import numpy as np

ACTS = {
    "tanh": (np.tanh, lambda z: 1.0 - np.tanh(z) ** 2),
    "relu": (lambda z: np.maximum(z, 0.0), lambda z: (z > 0).astype(np.float64)),
    "sigmoid": (lambda z: 1.0 / (1.0 + np.exp(-z)), lambda z: (1.0 / (1.0 + np.exp(-z))) * (1.0 - 1.0 / (1.0 + np.exp(-z)))),
    "linear": (lambda z: z, lambda z: np.ones_like(z)),
}


def _shrink(th):
    """Soft threshold: odd (zero-mean output), with ReLU-like hard 0/1 gates, open where |z| > th."""
    return (lambda z: np.sign(z) * np.maximum(np.abs(z) - th, 0.0), lambda z: (np.abs(z) > th).astype(np.float64))


def _leaky(a):
    return (lambda z: np.where(z > 0, z, a * z), lambda z: np.where(z > 0, 1.0, a))


# Added for experiments 9 onward (existing entries above are unchanged):
ACTS.update({
    "tanh+1": (lambda z: np.tanh(z) + 1.0, lambda z: 1.0 - np.tanh(z) ** 2),  # tanh's derivative exactly, positive mean
    "shrink0.4": _shrink(0.4),    # threshold giving about half the gates open at initialisation on digits
    "shrink0.12": _shrink(0.12),  # the same on the clean circle (its pre-activations are smaller)
    "leaky0.1": _leaky(0.1), "leaky0.3": _leaky(0.3), "leaky0.6": _leaky(0.6),
})


class MLP:
    def __init__(self, din, width, depth, dout, act="tanh", sigma_w=1.0, residual=False, alpha=None,
                 seed=0, orthogonal=False, branch_sign=False):
        self.act, self.residual = act, residual
        self.alpha = (1.0 / np.sqrt(depth)) if (residual and alpha is None) else (alpha or 1.0)
        rng = np.random.default_rng(seed)
        dims = [din] + [width] * depth + [dout]
        self.W, self.b = [], []
        for i in range(len(dims) - 1):
            fin, fout = dims[i], dims[i + 1]
            if orthogonal and fin == fout:
                q, _ = np.linalg.qr(rng.standard_normal((fin, fin)))
                W = sigma_w * q
            else:
                W = rng.standard_normal((fout, fin)) * sigma_w / np.sqrt(fin)
            self.W.append(W)
            self.b.append(np.zeros(fout))
        # branch_sign (experiments 10 onward): each residual block's output is multiplied unit-wise by a fixed random
        # +-1 sign, drawn separately for every block from its own generator, so the init weights above are unchanged.
        # The activation derivative's magnitude is untouched; only the direction each block writes into the stream varies.
        self.S = None
        if branch_sign:
            srng = np.random.default_rng(seed + 7_777_777)
            self.S = [None] + [srng.choice([-1.0, 1.0], size=width) for _ in range(depth - 1)] + [None]

    @property
    def depth(self):
        return len(self.W) - 1  # hidden layers including the input projection

    def forward(self, X):
        f, _ = ACTS[self.act]
        h = [X]
        z = []
        L = len(self.W)
        for i in range(L):
            zi = h[-1] @ self.W[i].T + self.b[i]
            z.append(zi)
            if i == L - 1:
                h.append(zi)
            elif self.residual and i > 0:
                h.append(h[-1] + self.alpha * (f(zi) if self.S is None else self.S[i] * f(zi)))
            else:
                h.append(f(zi))
        return h, z

    def loss(self, X, y):
        out = self.forward(X)[1][-1]
        out = out - out.max(1, keepdims=True)
        lp = out - np.log(np.exp(out).sum(1, keepdims=True))
        return float(-lp[np.arange(len(y)), y].mean())

    def backward(self, X, y):
        """Returns (loss, grads_W, grads_b, deltas) with deltas[i] = dL/dz_i (rows = examples)."""
        _, df = ACTS[self.act]
        h, z = self.forward(X)
        n, L = len(X), len(self.W)
        out = z[-1] - z[-1].max(1, keepdims=True)
        p = np.exp(out); p /= p.sum(1, keepdims=True)
        loss = float(-np.log(p[np.arange(n), y] + 1e-300).mean())
        d = p.copy(); d[np.arange(n), y] -= 1.0; d /= n
        deltas = [None] * L
        deltas[-1] = d
        gh = d @ self.W[-1]                      # dL/dh_{L-1}
        for i in range(L - 2, -1, -1):
            if self.residual and i > 0:
                deltas[i] = gh * self.alpha * df(z[i]) * (1.0 if self.S is None else self.S[i])
                gh = gh + deltas[i] @ self.W[i]  # skip path + block path
            else:
                deltas[i] = gh * df(z[i])
                gh = deltas[i] @ self.W[i]
        gW = [deltas[i].T @ h[i] for i in range(L)]
        gb = [deltas[i].sum(0) for i in range(L)]
        return loss, gW, gb, deltas

    def geometry_deltas(self, deltas, remove_alpha=False):
        """The deltas to measure. Plain nets: every hidden layer, then the output.
        Residual nets: the residual blocks only (layer 0 is the un-scaled input projection, and including it
        would put a step of size alpha into the profile), then the output.

        remove_alpha: every residual block's delta carries the architectural factor alpha (= 1/sqrt(depth)
        by default) that the output layer does not. With remove_alpha=True the block deltas are divided by
        alpha, so the profile measures the signal arriving at each block, not the fixed scale the architecture
        applies to it. Use this when comparing residual networks of different depths; leave it False when the
        question is how fast each block's weights actually move."""
        if self.residual:
            if remove_alpha:
                return [d / self.alpha for d in deltas[1:-1]] + [deltas[-1]]
            return deltas[1:]
        return deltas

    def accuracy(self, X, y):
        return float((self.forward(X)[1][-1].argmax(1) == y).mean())


class SGD:
    def __init__(self, lr):
        self.lr = lr

    def step(self, net, gW, gb):
        for i in range(len(net.W)):
            net.W[i] -= self.lr * gW[i]
            net.b[i] -= self.lr * gb[i]


class Adam:
    def __init__(self, lr, b1=0.9, b2=0.999, eps=1e-8):
        self.lr, self.b1, self.b2, self.eps, self.t, self.m, self.v = lr, b1, b2, eps, 0, None, None

    def step(self, net, gW, gb):
        g = gW + gb
        p = net.W + net.b
        if self.m is None:
            self.m = [np.zeros_like(x) for x in p]
            self.v = [np.zeros_like(x) for x in p]
        self.t += 1
        for i, (pi, gi) in enumerate(zip(p, g)):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * gi
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * gi * gi
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            pi -= self.lr * mh / (np.sqrt(vh) + self.eps)
