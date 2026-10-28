"""Diagnostics for residual networks: an exact split of the corrected tilt T* into three parts.

For a residual block l:  h_l = h_{l-1} + alpha * f(z_l),  z_l = W_l h_{l-1} + b_l.
Let g_l = dL/dh_l (the gradient on the residual stream just after block l). Then the block's delta is
    delta_l = alpha * g_l * f'(z_l).
T* = ln( RMS(delta_1 / alpha) / RMS(delta_out) ) splits exactly into
    ln_out       = ln( RMS(g_L) / RMS(delta_out) )      the output layer turning the loss signal into a stream gradient
    ln_transport = ln( RMS(g_1) / RMS(g_L) )            the stream carrying it back from the last block to the first
    ln_gate      = ln( RMS(g_1 * f'(z_1)) / RMS(g_1) )  the first block's activation derivative letting it through
(L = last block). The three add up to T* to rounding; tests/test_probe.py checks this and that every delta
here equals MLP.backward's.
"""
import numpy as np
from .nets import ACTS
from .core import _rms_norm as rms


def _lr(a, b):
    """ln(a / b), nan when either is zero (e.g. an output layer started at zero passes no gradient back)."""
    return float(np.log(a / b)) if a > 0 and b > 0 else float("nan")


def diagnose(net, X, y):
    assert net.residual, "residual networks only"
    f, df = ACTS[net.act]
    h, z = net.forward(X)
    n, L = len(X), len(net.W)
    out = z[-1] - z[-1].max(1, keepdims=True)
    p = np.exp(out); p /= p.sum(1, keepdims=True)
    d = p.copy(); d[np.arange(n), y] -= 1.0; d /= n
    g = [None] * L; deltas = [None] * L; deltas[-1] = d
    gh = d @ net.W[-1]
    for i in range(L - 2, -1, -1):
        g[i] = gh
        if i > 0:
            deltas[i] = gh * net.alpha * df(z[i]) * (1.0 if net.S is None else net.S[i])
            gh = gh + deltas[i] @ net.W[i]
        else:
            deltas[i] = gh * df(z[i]); gh = deltas[i] @ net.W[i]
    blocks = range(1, L - 1)
    r_out = rms(d)
    ln_out = _lr(rms(g[L - 2]), r_out)
    ln_transport = _lr(rms(g[1]), rms(g[L - 2]))
    ln_gate = _lr(rms(deltas[1] / net.alpha), rms(g[1]))  # a +-1 branch sign leaves RMS unchanged
    dens = [float(np.mean(df(z[i]) > 0)) if net.act == "relu" else float(np.mean(df(z[i]))) for i in blocks]
    dead = [float(np.mean(np.all(z[i] <= 0, axis=0))) for i in blocks] if net.act == "relu" else None
    return dict(
        Tstar=_lr(rms(deltas[1] / net.alpha), r_out),
        ln_out=float(ln_out), ln_transport=float(ln_transport), ln_gate=float(ln_gate),
        stream_grad=[_lr(rms(g[i]), r_out) for i in blocks],       # ln RMS g_l, relative to output delta
        gate=[_lr(rms(deltas[i] / net.alpha), rms(g[i])) for i in blocks],
        stream_norm=[float(rms(h[i + 1])) for i in blocks],                     # forward residual-stream size
        branch_ratio=[float(rms(net.alpha * f(z[i])) / rms(h[i])) if rms(h[i]) > 0 else float("nan") for i in blocks],  # block update vs stream before it
        density=dens, dead=dead,
        Wout=float(np.linalg.norm(net.W[-1])),
    ), deltas


def diagnose2(net, X, y):
    """The same split for two-matrix blocks (lapse.nets2.MLP2). The block delta is alpha * (g_l V_l) * f'(z_l),
    so the gate part here also includes the block's second matrix V_1."""
    f, _ = ACTS[net.act]
    loss, gW, gb, deltas, gV, g = net.backward(X, y, return_stream=True)
    h, z = net.forward(X)
    L = len(net.W); blocks = range(1, L - 1); r_out = rms(deltas[-1])
    return dict(
        Tstar=_lr(rms(deltas[1] / net.alpha), r_out),
        ln_out=_lr(rms(g[L - 2]), r_out), ln_transport=_lr(rms(g[1]), rms(g[L - 2])),
        ln_gate=_lr(rms(deltas[1] / net.alpha), rms(g[1])),
        stream_grad=[_lr(rms(g[i]), r_out) for i in blocks],
        gate=[_lr(rms(deltas[i] / net.alpha), rms(g[i])) for i in blocks],
        stream_norm=[float(rms(h[i + 1])) for i in blocks],
        branch_ratio=[float(rms(h[i + 1] - h[i]) / rms(h[i])) if rms(h[i]) > 0 else float("nan") for i in blocks],
        density=[float(np.mean(z[i] > 0)) if net.act == "relu" else float("nan") for i in blocks],
        dead=[float(np.mean(np.all(z[i] <= 0, axis=0))) for i in blocks] if net.act == "relu" else None,
        Wout=float(np.linalg.norm(net.W[-1])),
    ), deltas
