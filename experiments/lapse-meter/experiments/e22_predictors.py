"""Experiment 22: four candidate predictors of the early collapse, measured at initialization (before any step).

For one run configuration (the probe_run.py config keys), builds exactly the network that run started from and
measures, on its 256-example probe batch:
  kick        readout kick: RMS over examples of |dz|, the change in logits from one SGD step on the readout
              (weights and bias) alone, at the readout's step-1 learning rate. The mu-P argument (Yang 2022): one
              SGD step on the readout moves the logits in proportion to eta * |h_L|^2.
  sharp       preconditioned sharpness: the top eigenvalue of P^1/2 H P^1/2, where H is the Hessian of the probe-batch
              loss over all parameters and P holds each parameter's step-1 learning rate. Gradient descent on a
              quadratic is unstable above 2 (Gilmer 2022; Kalra & Barkeshli 2024). Lanczos (largest algebraic
              eigenvalue) on Hessian-vector products by central differences of the exact gradient (eps = 1e-4 in
              scaled coordinates). sharp_out is the same restricted to the readout's parameters.
  corr        gradient coherence: |mean_i g_i|^2 / mean_i |g_i|^2 for the per-example readout-weight gradients
              g_i = delta_i h_i^T; 1 = every example asks for the same update, ~1/n = unrelated (Kosson 2024).
  blockstep   mean over residual blocks of eta_l * |dL/dW_l| / |W_l| at step 1: the relative size of the blocks' first
              update (Kosson 2024's measure of effective update size).
Usage: from e22_predictors import predictors; predictors(cfg)  ->  dict
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import numpy as np
from lapse.nets import MLP
from lapse.nets2 import MLP2
from lapse.nets_ln import MLPLN
from probe_run import DEFAULTS
import e4


def build(cfg):
    c = {**DEFAULTS, **cfg}
    X, y, Xt, yt = e4.make(c["task"], c["seed"])
    if c["input_scale"] != 1.0: X = X * c["input_scale"]
    ncls = int(max(y.max(), yt.max()) + 1)  # exactly as probe_run.py
    if c["block"] == "ln":
        net = MLPLN(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], alpha=c["alpha"], seed=c["seed"],
                    ln=c["ln"], branch_sign=c["branch_sign"])
        if c["ln"].startswith("center"): net.set_center(X, seed=c["seed"])
        if c["ln"] == "offset": net.set_offset(X, c["width"], c["depth"], sigma_w=c["sigma_w"], alpha=c["alpha"], seed=c["seed"])  # experiment 30
    elif c["block"] == "two":
        net = MLP2(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], alpha=c["alpha"], seed=c["seed"])
    else:
        net = MLP(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], residual=True,
                  alpha=c["alpha"], seed=c["seed"], branch_sign=c["branch_sign"])
    if c["zero_out"]: net.W[-1][:] = 0.0
    if c.get("out_bias_prior"):  # experiment 47: readout bias = log class frequencies of the training set (predictions start at the priors)
        net.b[-1][:] = np.log(np.bincount(y, minlength=ncls) / len(y) + 1e-12)
    if c.get("zloss"): net.zloss = c["zloss"]
    return c, net, X[:256], y[:256]


def params(net):
    P = [("W", i) for i in range(len(net.W))] + [("b", i) for i in range(len(net.b))]
    if isinstance(net, MLP2): P += [("V", i) for i in range(1, len(net.W) - 1)]
    return P


def get(net, k):
    return getattr(net, k[0])[k[1]]


def grads(net, X, y):
    r = net.backward(X, y)
    G = {"W": r[1], "b": r[2]}
    if isinstance(net, MLP2): G["V"] = r[4]
    return G


def step1_lr(c, net, k):
    """Learning rate each parameter group gets at step 1, as probe_run.py applies it."""
    L = len(net.W); lr = c["lr"]; i = k[1]
    w = c["warmup"]
    if w and c["warmup_parts"] == "all": return lr / w
    if w and c["warmup_parts"] == "out" and i == L - 1 and k[0] != "V": return lr / w
    if w and c["warmup_parts"] == "blocks" and (1 <= i <= L - 2): return lr / w
    if i == L - 1 and k[0] != "V": return lr * c["out_lr_mult"]
    if 1 <= i <= L - 2 and k[0] != "V": return lr * c.get("block_lr_mult", 1.0)
    return lr


def predictors(cfg):
    c, net, X, y = build(cfg)
    assert c["opt"] == "sgd", "SGD runs only"
    L = len(net.W); P = params(net)
    eta = {k: step1_lr(c, net, k) for k in P}
    G = grads(net, X, y)
    # readout kick
    h, z = net.forward(X); hL = net.readout_input(X) if isinstance(net, MLPLN) else h[-2]
    dW = -eta[("W", L - 1)] * G["W"][L - 1]; db = -eta[("b", L - 1)] * G["b"][L - 1]
    dz = hL @ dW.T + db
    kick = float(np.sqrt(np.mean(np.sum(dz * dz, 1))))
    # gradient coherence (signal-to-noise) of per-example readout-weight gradients g_i = d_i h_i^T:
    # |mean_i g_i|^2 / mean_i |g_i|^2, which is 1 when every example asks for the same update and about 1/n when
    # their requests are unrelated. (A mean pairwise cosine was tried first and rejected before any analysis: with
    # two balanced classes the per-class signs cancel it to about 0 whatever the network does.)
    d = net.backward(X, y)[3][-1] * len(X); n = len(X)
    mean_g = d.T @ hL / n
    corr = float(np.sum(mean_g ** 2) / np.mean(np.sum(d ** 2, 1) * np.sum(hL ** 2, 1)))
    # block relative step
    bl = [eta[("W", i)] * np.linalg.norm(G["W"][i]) / np.linalg.norm(net.W[i]) for i in range(1, L - 1)]
    blockstep = float(np.mean(bl))
    # preconditioned sharpness by power iteration, all parameters and readout only
    def flat_grad(keys):
        G2 = grads(net, X, y)
        return np.concatenate([np.sqrt(eta[k]) * getattr_g(G2, k).ravel() for k in keys])
    def getattr_g(G2, k): return G2[k[0]][k[1]]
    def shift(keys, v, s):
        o = 0
        for k in keys:
            a = get(net, k); m = a.size
            a += s * np.sqrt(eta[k]) * v[o:o + m].reshape(a.shape); o += m
    # For piecewise-linear activations the Hessian is defined only away from the kinks. A finite-difference step that
    # flips any gate turns the gradient's jump into a fake curvature of order 1/eps (found in validation, CORRECTIONS
    # 35). So each Hessian-vector product checks that no gate on the batch flips, and shrinks eps until none does: the
    # result is then the gate-frozen ("almost everywhere") Hessian that automatic differentiation computes.
    piecewise = c["act"] == "relu" or c["act"].startswith(("shrink", "leaky"))
    from lapse.nets import ACTS
    dfun = ACTS[c["act"]][1]
    gates = lambda: np.concatenate([dfun(zz).ravel() for zz in net.forward(X)[1][:-1]])
    base_gates = gates() if piecewise else None
    flips = [0]
    def hvp(keys, v, eps=1e-4):
        while True:
            shift(keys, v, eps); ok = (not piecewise) or np.array_equal(gates(), base_gates); gp = flat_grad(keys)
            shift(keys, v, -2 * eps); ok = ok and ((not piecewise) or np.array_equal(gates(), base_gates)); gm = flat_grad(keys)
            shift(keys, v, eps)
            if ok or eps < 1e-9: break
            eps /= 10
        if not ok: flips[0] += 1
        return (gp - gm) / (2 * eps)
    def top_eig(keys):
        """Most positive (largest algebraic) eigenvalue, by Lanczos (scipy eigsh, which='LA') on Hessian-vector
        products. Plain power iteration finds the largest |eigenvalue|, which can be negative; it was tried first
        and rejected after a validation against explicit Hessians failed (CORRECTIONS 35)."""
        from scipy.sparse.linalg import LinearOperator, eigsh
        n_ = sum(get(net, k).size for k in keys)
        op = LinearOperator((n_, n_), matvec=lambda v: hvp(keys, np.asarray(v).ravel()), dtype=np.float64)
        v0 = np.random.default_rng(0).standard_normal(n_)
        if not np.any(hvp(keys, v0)):  # Hessian exactly zero along v0 (softmax saturated to exact one-hot in floating
            return 0.0                 # point); ARPACK cannot start from a zero image. Found in experiment 25.
        return float(eigsh(op, k=1, which="LA", v0=v0, tol=1e-6, maxiter=2000)[0][0])
    sharp = top_eig(P)
    sharp_out = top_eig([("W", L - 1), ("b", L - 1)])
    return dict(kick=kick, sharp=sharp, sharp_out=sharp_out, corr=corr, blockstep=blockstep, hvp_kink_failures=flips[0],
                stream_growth=float(np.sqrt(np.mean(np.sum(hL ** 2, 1))) / np.sqrt(np.mean(np.sum(h[2] ** 2, 1)))))
