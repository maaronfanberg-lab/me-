"""Residual MLP with LayerNorm in a chosen position (experiment 26).

Blocks are the one-matrix kind used in experiments 8-24, f = act (optionally with a fixed random +-1 sign per unit):
  ln = "none"       h_l = h_{l-1} + a f(W_l h_{l-1} + b_l);                logits = W_out h_L + b_out
  ln = "final"      as "none", but logits = W_out LN(h_L) + b_out
  ln = "pre"        h_l = h_{l-1} + a f(W_l LN(h_{l-1}) + b_l);            logits = W_out h_L + b_out
  ln = "pre_final"  "pre" blocks and a final LN before the readout (the usual Pre-LN transformer arrangement)
  ln = "post"       h_l = LN(h_{l-1} + a f(W_l h_{l-1} + b_l));            logits = W_out h_L + b_out (Post-LN)
  ln = "center"     as "none", but logits = W_out (h_L - m0) + b_out, m0 a fixed vector (set_center; experiment 29)
  ln = "center_random"  the same with a random fixed vector of m0's norm (the control)
  ln = "offset"     as "none", but logits = W_out (h_L + m_relu) + b_out, m_relu the mean last stream of the plain
                    ReLU network with the same seed (set_offset; experiment 30): a pile-up-sized shared readout input
                    on a network whose stream need not pile up (used with branch_sign=True)
LN(x) = (x - mean(x)) / sqrt(var(x) + 1e-5) per example, without a learned gain or bias (a simplification: real
transformers learn both). The input layer h_0 = act(W_0 x + b_0) is shared by all variants, a = 1/sqrt(depth).
backward returns (loss, gW, gb, deltas, g) with deltas[i] = dL/dz_i and g[i] = dL/dh_i (the stream after block i,
as the readout or the next block sees it). tests/test_nets_ln.py checks every gradient by finite differences.
"""
from __future__ import annotations
import numpy as np
from .nets import ACTS

EPS = 1e-5


def ln_fwd(x):
    mu = x.mean(1, keepdims=True); xc = x - mu; s = np.sqrt((xc * xc).mean(1, keepdims=True) + EPS)
    return xc / s, (xc / s, s)


def ln_bwd(dy, cache):
    xh, s = cache
    return (dy - dy.mean(1, keepdims=True) - xh * (dy * xh).mean(1, keepdims=True)) / s


class MLPLN:
    residual = True

    def __init__(self, din, width, depth, dout, act="relu", sigma_w=1.0, alpha=None, seed=0, ln="final", branch_sign=False):
        assert ln in ("none", "final", "pre", "pre_final", "post", "center", "center_random", "offset", "dyt", "bcenter")
        self.center = None  # experiment 29: a fixed vector subtracted from the readout's input (see set_center)
        self.act, self.ln = act, ln
        self.alpha = 1.0 / np.sqrt(depth) if alpha is None else alpha
        rng = np.random.default_rng(seed)
        dims = [din] + [width] * depth + [dout]
        self.W = [rng.standard_normal((dims[i + 1], dims[i])) * sigma_w / np.sqrt(dims[i]) for i in range(len(dims) - 1)]
        self.b = [np.zeros(dims[i + 1]) for i in range(len(dims) - 1)]
        self.S = None
        if branch_sign:  # same generator and draw as lapse.nets.MLP(branch_sign=True), so twins share their signs
            srng = np.random.default_rng(seed + 7_777_777)
            self.S = [None] + [srng.choice([-1.0, 1.0], size=width) for _ in range(depth - 1)] + [None]

    def _sign(self, i):
        return 1.0 if self.S is None else self.S[i]

    def forward(self, X):
        f, _ = ACTS[self.act]
        L = len(self.W); h = [X]; z = []; self._c = {}
        z0 = X @ self.W[0].T + self.b[0]; z.append(z0); h.append(f(z0))
        for i in range(1, L - 1):
            hin = h[-1]
            if self.ln in ("pre", "pre_final"):
                u, self._c[("pre", i)] = ln_fwd(hin)
            else:
                u = hin
            zi = u @ self.W[i].T + self.b[i]; z.append(zi)
            nxt = hin + self.alpha * self._sign(i) * f(zi)
            if self.ln == "post":
                nxt, self._c[("post", i)] = ln_fwd(nxt)
            h.append(nxt)
        top = h[-1]
        if self.ln in ("final", "pre_final"):
            top, self._c["final"] = ln_fwd(top)
        elif self.ln in ("center", "center_random", "offset"):
            top = top - self.center
        elif self.ln == "dyt":  # experiment 56: tanh(h_L) before the readout (DyT with alpha = 1, Zhu et al. 2025)
            top = np.tanh(top)
        elif self.ln == "bcenter":  # experiment 56: subtract the current batch's mean readout input (mean-only batch norm)
            top = top - top.mean(0, keepdims=True)
        self._top = top
        zo = top @ self.W[-1].T + self.b[-1]; z.append(zo)
        return h, z

    def loss(self, X, y):
        out = self.forward(X)[1][-1]; out = out - out.max(1, keepdims=True)
        lp = out - np.log(np.exp(out).sum(1, keepdims=True))
        return float(-lp[np.arange(len(y)), y].mean())

    def backward(self, X, y):
        _, df = ACTS[self.act]
        h, z = self.forward(X); L, n = len(self.W), len(X)
        out = z[-1] - z[-1].max(1, keepdims=True); p = np.exp(out); p /= p.sum(1, keepdims=True)
        loss = float(-np.log(p[np.arange(n), y] + 1e-300).mean())
        d = p.copy(); d[np.arange(n), y] -= 1.0; d /= n
        deltas, g = [None] * L, [None] * L
        gW, gb = [None] * L, [None] * L
        deltas[-1] = d; gW[-1] = d.T @ self._top; gb[-1] = d.sum(0)
        gh = d @ self.W[-1]
        if self.ln in ("final", "pre_final"): gh = ln_bwd(gh, self._c["final"])
        elif self.ln == "dyt": gh = gh * (1.0 - self._top ** 2)
        elif self.ln == "bcenter": gh = gh - gh.mean(0, keepdims=True)
        for i in range(L - 2, 0, -1):
            g[i] = gh                                  # dL/dh_i: gradient on the stream after block i
            if self.ln == "post": gh = ln_bwd(gh, self._c[("post", i)])   # through h_i = LN(sum)
            di = gh * self.alpha * self._sign(i) * df(z[i]); deltas[i] = di
            if self.ln in ("pre", "pre_final"):
                u = self._c[("pre", i)][0]; gW[i] = di.T @ u; gb[i] = di.sum(0)
                gh = gh + ln_bwd(di @ self.W[i], self._c[("pre", i)])
            else:
                gW[i] = di.T @ h[i]; gb[i] = di.sum(0)
                gh = gh + di @ self.W[i]
        g[0] = gh
        d0 = gh * df(z[0]); deltas[0] = d0; gW[0] = d0.T @ X; gb[0] = d0.sum(0)
        return loss, gW, gb, deltas, g

    def set_center(self, X, seed=0):
        """Experiment 29. "center": subtract m0, the mean of the last stream over X at the current weights, held fixed.
        "center_random": subtract a random vector with the same norm as m0 (the control). The stream itself is unchanged.
        What the readout sees changes, so its update changes, and so do the initial logits (by -W_out m0) and through
        them the backward pass's starting error. (Corrected: an earlier version said the gradient into the stream was
        unchanged; it is not, because the logits move. CORRECTIONS 48.)"""
        saved = self.ln; self.ln = "none"; self.forward(X); m0 = self._top.mean(0); self.ln = saved
        if self.ln == "center":
            self.center = m0
        else:
            r = np.random.default_rng(seed + 4_242_424).standard_normal(m0.shape)
            self.center = r / np.linalg.norm(r) * np.linalg.norm(m0)

    def set_offset(self, X, width, depth, sigma_w=1.0, alpha=None, seed=0):
        """Experiment 30. "offset": add to the readout's input the mean last stream m_relu of the plain residual ReLU
        network built from the same seed (no branch signs, no LayerNorm), held fixed. The stream itself is unchanged.
        The readout's input changes, so its update changes, and so do the initial logits (by W_out m_relu), and through
        them the error the backward pass starts from. The plain ReLU network has that same logit offset."""
        twin = MLPLN(X.shape[1], width, depth, self.W[-1].shape[0], act="relu", sigma_w=sigma_w, alpha=alpha, seed=seed, ln="none")
        twin.forward(X); self.center = -twin._top.mean(0)

    def readout_input(self, X):
        self.forward(X); return self._top

    def accuracy(self, X, y):
        return float((self.forward(X)[1][-1].argmax(1) == y).mean())
