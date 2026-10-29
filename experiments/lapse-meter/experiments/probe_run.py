"""One configurable residual-network run with full diagnostics (lapse/probe.py), for experiments 8 onward.
With default settings it trains exactly the experiment-7 network (tests/test_probe_run.py checks the T* log is
bit-identical to results/e7). Usage: python experiments/probe_run.py '<json config>' out.json
Config keys (defaults in DEFAULTS): task, act, depth, seed, width, lr, steps, alpha, sigma_w, opt, freeze,
warmup (steps of linear learning-rate warm-up; 0 = none), zero_out (start the output layer at zero),
branch_sign (fixed random +-1 sign on each block's output units; True = even odds, a number q = probability
of +1; see lapse/nets.py), warmup_parts ("all", "out" = output layer only, "blocks" = residual blocks only),
block ("one" = h + alpha*act(Wh), the default; "two" = h + alpha*V act(Wh), lapse/nets2.py; "ln" = one-matrix
blocks with LayerNorm placed by `ln`: none | final | pre | pre_final | post, lapse/nets_ln.py),
out_lr_mult (learning-rate multiplier on the readout; SGD only; permanent unless out_lr_mult_until = k, experiment 30, limits it to steps 0 .. k-1), input_scale (inputs multiplied by it),
block_nomean (experiment 35: each block's update is projected so it cannot move the minibatch-mean pre-activation), detach (experiment 33: None, "mean" or "random"; see lapse.nets.MLP.detach; logged diagnostics always use the true gradient), block_lr_mult (experiment 32: learning-rate multiplier on the residual blocks 1..L-2, SGD; permanent unless block_lr_mult_until = k limits it to steps 0 .. k-1), zloss (coefficient of an auxiliary z-loss, gradient only; logged loss stays cross-entropy), kick_cap_until (experiment 27: the cap applies only to steps 0 .. kick_cap_until-1), kick_cap (SGD only: at each step the readout's update is scaled down, if needed, so the RMS change it makes to the
minibatch's logits is at most this; the blocks' updates are untouched; capped_steps lists the steps it bound).
freeze: list of parts held at their initial values: "out" (output layer), "blocks" (all residual blocks).
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from lapse.nets import MLP, SGD, Adam, Momentum
from lapse.probe import diagnose, diagnose2, diagnose_ln
from lapse.nets_ln import MLPLN
from lapse.nets2 import MLP2
import e4

DEFAULTS = dict(task="digits", act="relu", depth=24, seed=0, width=64, lr=0.05, steps=6000, alpha=None,
                sigma_w=1.0, opt="sgd", freeze=[], log_every=50, layers_every=500, warmup=0, zero_out=False, branch_sign=False, warmup_parts="all", block="one", out_lr_mult=1.0, input_scale=1.0, kick_cap=None, kick_cap_until=None, zloss=0.0, ln="none", out_lr_mult_until=None, block_lr_mult=1.0, block_lr_mult_until=None, detach=None, block_nomean=False, out_bias_prior=False)


def run(cfg, path=None, hook=None):
    """hook (experiment 31): optional f(net, X, y) -> dict, called at every logged step; its entries join that log line."""
    c = {**DEFAULTS, **cfg}
    if path: os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    X, y, Xt, yt = e4.make(c["task"], c["seed"])
    if c["input_scale"] != 1.0: X, Xt = X * c["input_scale"], Xt * c["input_scale"]  # experiment 23
    ncls = int(max(y.max(), yt.max()) + 1)
    if c["block"] == "ln":
        assert c["opt"] == "sgd" and not c["zloss"]
        net = MLPLN(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], alpha=c["alpha"],
                    seed=c["seed"], ln=c["ln"], branch_sign=c["branch_sign"])
        if c["ln"].startswith("center"): net.set_center(X, seed=c["seed"])
        if c["ln"] == "offset": net.set_offset(X, c["width"], c["depth"], sigma_w=c["sigma_w"], alpha=c["alpha"], seed=c["seed"])  # experiment 30
    elif c["block"] == "two":
        assert not c["branch_sign"] and c["opt"] == "sgd", "two-matrix blocks: SGD, no branch signs"
        net = MLP2(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], alpha=c["alpha"], seed=c["seed"])
    else:
        net = MLP(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], residual=True,
                  alpha=c["alpha"], seed=c["seed"], branch_sign=c["branch_sign"])
    if c["zloss"]: net.zloss = c["zloss"]
    diag = {"two": diagnose2, "ln": diagnose_ln}.get(c["block"], diagnose)
    if c["zero_out"]: net.W[-1][:] = 0.0
    if c.get("out_bias_prior"):  # experiment 47: readout bias = log class frequencies of the training set (predictions start at the priors)
        net.b[-1][:] = np.log(np.bincount(y, minlength=ncls) / len(y) + 1e-12)  # output layer starts at zero: initial logits are all zero
    opt = {"sgd": lambda: SGD(c["lr"]), "adam": lambda: Adam(c["lr"]), "rmsprop": lambda: Adam(c["lr"], b1=0.0),
           "momentum": lambda: Momentum(c["lr"])}[c["opt"]]()  # rmsprop = Adam without momentum (experiment 21)
    rng = np.random.default_rng(10_000 + c["seed"])
    L = len(net.W); frozen = set()
    if "out" in c["freeze"]: frozen.add(L - 1)
    if "blocks" in c["freeze"]: frozen.update(range(1, L - 1))
    if "in" in c["freeze"]: frozen.add(0)  # experiment 39: the input layer
    log = []; capped = []
    if c["detach"]:  # experiment 33: training gradients lose their readout-to-stream part along one direction
        assert c["block"] == "one" and c["opt"] == "sgd"; net.detach = c["detach"]
    for s in range(c["steps"] + 1):
        if s % c["log_every"] == 0:
            saved = getattr(net, "detach", None); net.detach = None  # diagnostics measure the true gradient
            dg, _ = diag(net, X[:256], y[:256])
            e = dict(step=s, train_loss=net.loss(X, y), **{k: dg[k] for k in ("Tstar", "ln_out", "ln_transport", "ln_gate", "Wout")})
            if hook is not None: e.update(hook(net, X[:256], y[:256]))
            if s % c["layers_every"] == 0 or s == c["steps"]:
                e.update({k: dg[k] for k in ("stream_grad", "gate", "stream_norm", "branch_ratio", "density", "dead")})
            log.append(e); net.detach = saved
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
        if c["kick_cap"] is not None and (c["kick_cap_until"] is None or s < c["kick_cap_until"]):  # experiments 24, 27
            assert c["opt"] == "sgd" and not c["warmup"] and c["out_lr_mult"] == 1.0
            hb = net.readout_input(X[idx]) if c["block"] == "ln" else net.forward(X[idx])[0][-2]
            dzb = hb @ (-opt.lr * gW[L - 1]).T - opt.lr * gb[L - 1]
            kb = float(np.sqrt(np.mean(np.sum(dzb * dzb, 1))))
            if kb > c["kick_cap"]:
                f_ = c["kick_cap"] / kb; gW[L - 1] = gW[L - 1] * f_; gb[L - 1] = gb[L - 1] * f_
                capped.append(s)
        if c["out_lr_mult"] != 1.0 and (c["out_lr_mult_until"] is None or s < c["out_lr_mult_until"]):  # experiment 23 (permanent); 30 (steps 0 .. until-1)
            gW[L - 1] = gW[L - 1] * c["out_lr_mult"]; gb[L - 1] = gb[L - 1] * c["out_lr_mult"]
        if c["block_nomean"]:  # experiment 35: no block update may shift its batch-mean pre-activation (dW hbar = 0, db = 0)
            assert c["block"] == "one" and c["opt"] == "sgd"
            hs = net.forward(X[idx])[0]
            for i in range(0 if c["block_nomean"] == "all" else 1, L - 1):  # "all" (experiment 36) adds the input layer
                hb_ = hs[i].mean(0); u = hb_ / np.linalg.norm(hb_)
                gW[i] = gW[i] - np.outer(gW[i] @ u, u); gb[i] = np.zeros_like(gb[i])
        if c["block_lr_mult"] != 1.0 and (c["block_lr_mult_until"] is None or s < c["block_lr_mult_until"]):  # experiment 32
            assert c["opt"] == "sgd" and c["block"] != "two"
            for i in range(1, L - 1): gW[i] = gW[i] * c["block_lr_mult"]; gb[i] = gb[i] * c["block_lr_mult"]
        opt.step(net, gW, gb)
        if c["block"] == "two":  # the blocks' second matrices, same SGD step (warm-up included via opt.lr)
            k = min(1.0, (s + 1) / c["warmup"]) if (c["warmup"] and c["warmup_parts"] == "blocks") else 1.0
            for i in range(1, L - 1): net.V[i] -= opt.lr * k * bw[4][i]
    res = dict(config=c, test_acc=net.accuracy(Xt, yt), test_loss=net.loss(Xt, yt), log=log, capped_steps=capped)
    if path: json.dump(res, open(path, "w"))
    return res


if __name__ == "__main__":
    cfg = json.loads(sys.argv[1]); r = run(cfg, sys.argv[2]); z = r["log"][-1]
    print(f"{sys.argv[2]}: T* {r['log'][0]['Tstar']:+.2f} -> {z['Tstar']:+.2f} (out {z['ln_out']:+.2f} transport {z['ln_transport']:+.2f} gate {z['ln_gate']:+.2f}) loss {z['train_loss']:.4f}", flush=True)
