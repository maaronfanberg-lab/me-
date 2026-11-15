"""Experiment 25 (exploratory): what the readout kick does, step by step, in the first 200 steps.
Same network, data, batches and update rule as probe_run.py (checked: the logged loss trajectory is identical to
probe_run's for the same config). Logged every step to 50, then every 5, on the 256-example probe batch:
  loss, logit RMS, softmax saturation (mean largest probability), this step's readout kick (on the minibatch)
  M1 catapult:    eta * lambda_max of the preconditioned Hessian (Lanczos, e22_predictors) at steps 0,1,2,5,10,20,50,100,200
  M2 shared dir.: m = the batch-mean of the last stream (the shared vector of the pile-up), m_hat = m/|m|;
                  share of the readout weights' energy along m_hat, |W_out m_hat|^2 / |W_out|_F^2 (1/width for no preference);
                  share of the stream gradient g_L's energy along m_hat (per example, averaged)
  M3 gates:       fraction of ReLU gates (examples x units) changed since step 0, in block 1 and over all blocks
  and the tilt parts (transport, gate, output).
Usage: python experiments/e25_trace.py '<json config>' out.json
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import numpy as np
import e4
from lapse.nets import MLP, SGD
from lapse.probe import diagnose
import e22_predictors as P22

SHARP_AT = {0, 1, 2, 5, 10, 20, 50, 100, 200}


def sharp_now(net, c, X, y):
    """Preconditioned top Hessian eigenvalue of the CURRENT network (reuses the validated e22 machinery)."""
    orig_build = P22.build
    saved = [w.copy() for w in net.W], [v.copy() for v in net.b]   # Hessian-vector products nudge the weights;
    P22.build = lambda cfg: (dict({**P22.DEFAULTS, **cfg}), net, X, y)  # restore them exactly afterwards
    try:
        return P22.predictors(c)["sharp"]
    finally:
        P22.build = orig_build
        for i in range(len(net.W)): net.W[i][...] = saved[0][i]; net.b[i][...] = saved[1][i]


def main(cfg, path, steps=200):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    c = {**P22.DEFAULTS, **cfg}
    X, y, Xt, yt = e4.make(c["task"], c["seed"])
    ncls = int(max(y.max(), yt.max()) + 1)
    net = MLP(X.shape[1], c["width"], c["depth"], ncls, act=c["act"], sigma_w=c["sigma_w"], residual=True, alpha=c["alpha"],
              seed=c["seed"], branch_sign=c["branch_sign"])
    opt, rng = SGD(c["lr"]), np.random.default_rng(10_000 + c["seed"]); L = len(net.W)
    Xp, yp = X[:256], y[:256]
    g0 = None; log = []
    for s in range(steps + 1):
        idx = rng.integers(0, len(X), 64) if s < steps else None
        if s <= 50 or s % 5 == 0:
            h, z = net.forward(Xp)
            gates = np.concatenate([(zz > 0).ravel() for zz in z[1:-1]]); gates1 = (z[1] > 0).ravel()
            if g0 is None: g0, g10 = gates.copy(), gates1.copy()
            out = z[-1] - z[-1].max(1, keepdims=True); p = np.exp(out); p /= p.sum(1, keepdims=True)
            hL = h[-2]; m = hL.mean(0); mh = m / (np.linalg.norm(m) + 1e-300)
            dg, _ = diagnose(net, Xp, yp)
            r = net.backward(Xp, yp); d = r[3][-1]; gL = d @ net.W[-1]
            share_g = float(np.mean((gL @ mh) ** 2 / (np.sum(gL * gL, 1) + 1e-300)))
            share_W = float(np.sum((net.W[-1] @ mh) ** 2) / np.sum(net.W[-1] ** 2))
            e = dict(step=s, loss=net.loss(X, y), logit_rms=float(np.sqrt(np.mean(np.sum(z[-1] ** 2, 1)))), saturation=float(p.max(1).mean()),
                     share_W=share_W, share_g=share_g, flips_all=float(np.mean(gates != g0)), flips_b1=float(np.mean(gates1 != g10)),
                     transport=dg["ln_transport"], gate=dg["ln_gate"], out=dg["ln_out"], Wout=dg["Wout"])
            if s in SHARP_AT:
                w = c["warmup"]; lr_now = c["lr"] * (min(1.0, (s + 1) / w) if w else 1.0)
                e["eta_sharp"] = sharp_now(net, dict(cfg, warmup=0, lr=lr_now), Xp, yp)
            log.append(e)
        if s == steps: break
        _, gW, gb, _ = net.backward(X[idx], y[idx])
        if c["warmup"]: opt.lr = c["lr"] * min(1.0, (s + 1) / c["warmup"])
        hb = net.forward(X[idx])[0][-2]; dzb = hb @ (-opt.lr * gW[L - 1]).T - opt.lr * gb[L - 1]
        kb = float(np.sqrt(np.mean(np.sum(dzb * dzb, 1))))       # this step's proposed readout kick, on the minibatch
        applied = kb
        if c.get("kick_cap") is not None and kb > c["kick_cap"]:
            f_ = c["kick_cap"] / kb; gW[L - 1] = gW[L - 1] * f_; gb[L - 1] = gb[L - 1] * f_; applied = c["kick_cap"]
        if log and log[-1]["step"] == s: log[-1]["kick_proposed"], log[-1]["kick_applied"] = kb, applied
        opt.step(net, gW, gb)
    json.dump(dict(config=c, log=log), open(path, "w"))
    a, b = log[0], log[-1]
    print(f"{path}: loss {a['loss']:.2f}->{b['loss']:.3f} transport {a['transport']:+.2f}->{b['transport']:+.2f} share_W {a['share_W']:.3f}->{b['share_W']:.3f} share_g {a['share_g']:.3f}->{b['share_g']:.3f} flips {b['flips_all']:.2f}", flush=True)


if __name__ == "__main__":
    main(json.loads(sys.argv[1]), sys.argv[2])
