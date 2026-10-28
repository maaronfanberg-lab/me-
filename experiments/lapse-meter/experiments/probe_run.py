"""One configurable residual-network run with full diagnostics (lapse/probe.py), for experiments 8 onward.
With default settings it trains exactly the experiment-7 network (tests/test_probe_run.py checks the T* log is
bit-identical to results/e7). Usage: python experiments/probe_run.py '<json config>' out.json
Config keys (defaults in DEFAULTS): task, act, depth, seed, width, lr, steps, alpha, sigma_w, opt, freeze,
warmup (steps of linear learning-rate warm-up; 0 = none), zero_out (start the output layer at zero),
branch_sign (fixed random +-1 sign on each block's output units; True = even odds, a number q = probability
of +1; see lapse/nets.py), warmup_parts ("all", "out" = output layer only, "blocks" = residual blocks only),
block ("one" = h + alpha*act(Wh), the default; "two" = h + alpha*V act(Wh), lapse/nets2.py).
freeze: list of parts held at their initial values: "out" (output layer), "blocks" (all residual blocks).
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from lapse.nets import MLP, SGD, Adam
from lapse.probe import diagnose, diagnose2
from lapse.nets2 import MLP2
import e4

DEFAULTS = dict(task="digits", act="relu", depth=24, seed=0, width=64, lr=0.05, steps=6000, alpha=None,
                sigma_w=1.0, opt="sgd", freeze=[], log_every=50, layers_every=500, warmup=0, zero_out=False, branch_sign=False, warmup_parts="all", block="one")


def run(cfg, path=None):
    c = {**DEFAULTS, **cfg}
    if path: os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    X, y, Xt, yt = e4.make(c["task"], c["seed"])
    ncls = int(max(y.max(), yt.max()) + 1)
    if c["block"] == "two":
        assert not c["branch_sign"] and c["opt"] == "sgd", "two-matrix blocks: SGD, no branch signs"
        net = MLP2(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], alpha=c["alpha"], seed=c["seed"])
    else:
        net = MLP(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], residual=True,
                  alpha=c["alpha"], seed=c["seed"], branch_sign=c["branch_sign"])
    diag = diagnose2 if c["block"] == "two" else diagnose
    if c["zero_out"]: net.W[-1][:] = 0.0  # output layer starts at zero: initial logits are all zero
    opt = SGD(c["lr"]) if c["opt"] == "sgd" else Adam(c["lr"])
    rng = np.random.default_rng(10_000 + c["seed"])
    L = len(net.W); frozen = set()
    if "out" in c["freeze"]: frozen.add(L - 1)
    if "blocks" in c["freeze"]: frozen.update(range(1, L - 1))
    log = []
    for s in range(c["steps"] + 1):
        if s % c["log_every"] == 0:
            dg, _ = diag(net, X[:256], y[:256])
            e = dict(step=s, train_loss=net.loss(X, y), **{k: dg[k] for k in ("Tstar", "ln_out", "ln_transport", "ln_gate", "Wout")})
            if s % c["layers_every"] == 0 or s == c["steps"]:
                e.update({k: dg[k] for k in ("stream_grad", "gate", "stream_norm", "branch_ratio", "density", "dead")})
            log.append(e)
        if s == c["steps"]: break
        idx = rng.integers(0, len(X), 64)
        bw = net.backward(X[idx], y[idx]); gW, gb = bw[1], bw[2]
        if not all(np.all(np.isfinite(w)) for w in gW): break
        for i in frozen: gW[i] = np.zeros_like(gW[i]); gb[i] = np.zeros_like(gb[i])
        if c["warmup"] and c["warmup_parts"] == "all": opt.lr = c["lr"] * min(1.0, (s + 1) / c["warmup"])  # linear warm-up to lr
        elif c["warmup"]:  # warm-up on one part only, by scaling that part's gradients (exactly equivalent for SGD)
            k = min(1.0, (s + 1) / c["warmup"])
            for i in ([L - 1] if c["warmup_parts"] == "out" else range(1, L - 1)):
                gW[i] = gW[i] * k; gb[i] = gb[i] * k
        opt.step(net, gW, gb)
        if c["block"] == "two":  # the blocks' second matrices, same SGD step (warm-up included via opt.lr)
            k = min(1.0, (s + 1) / c["warmup"]) if (c["warmup"] and c["warmup_parts"] == "blocks") else 1.0
            for i in range(1, L - 1): net.V[i] -= opt.lr * k * bw[4][i]
    res = dict(config=c, test_acc=net.accuracy(Xt, yt), log=log)
    if path: json.dump(res, open(path, "w"))
    return res


if __name__ == "__main__":
    cfg = json.loads(sys.argv[1]); r = run(cfg, sys.argv[2]); z = r["log"][-1]
    print(f"{sys.argv[2]}: T* {r['log'][0]['Tstar']:+.2f} -> {z['Tstar']:+.2f} (out {z['ln_out']:+.2f} transport {z['ln_transport']:+.2f} gate {z['ln_gate']:+.2f}) loss {z['train_loss']:.4f}", flush=True)
