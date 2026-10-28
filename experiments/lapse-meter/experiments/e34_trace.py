"""Experiment 34 (exploratory, E34_PLAN.md): traces of the teardown, every step.

Usage: python experiments/e34_trace.py <task> <plain|cap10|signed> <seed>
Two runs from the same start (the training code is deterministic):
  fine    300 steps, the hook at every step: the Q1-Q3 quantities
  coarse  3,000 steps, the hook every 10 steps (its own/inherited split then spans 10 steps); Q4's depth profiles come
          from fine (steps <= 300) and coarse (later)
The script checks the two runs' shared logged steps are identical, and that the hook changes nothing (a 20-step run
with and without it). Writes results/e34/<task>_<cond>_s<seed>.json.

Quantities, on the 256-example probe batch (the runner's own diagnostic batch):
  own_rms, inh_rms     RMS over blocks/examples/units of the two exact parts of z_t - z_{t-1}:
                       own = dW h_old + db (the block's own update), inh = W_new (h_new - h_old) (its input changed)
  own_common, inh_common  share of each part's energy in its batch mean (1 = the same shift for every example)
  own_closes           fraction of gates open at t-1 that the own part alone would close (z_old > 0, z_old + own <= 0),
                       over all blocks; closes = the fraction that actually closed
  corr_own_Wm          correlation over units (all blocks pooled) of the own part's batch mean with W_old m, where
                       m is the batch-mean stream entering the block
  dbar                 |mean_i (p_i - y_i)|, the shared error; err = RMS of p_i - y_i
  stream, open         RMS last stream; fraction of gates open per example (mean over blocks)
  open_by_block, sg_by_block  per-block open fraction and log RMS stream gradient (only every 10th step and the
                       fine run's first 5 steps, to keep files small)
"""
import os, sys, json, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
from probe_run import run
warnings.filterwarnings("ignore")
rms = lambda a: float(np.sqrt(np.mean(a * a))) if a.size else 0.0


def make_hook():
    prev = {}

    def hook(net, X, y):
        h, z = net.forward(X); L = len(net.W)
        logits = z[-1]; p = np.exp(logits - logits.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
        e = p.copy(); e[np.arange(len(y)), y] -= 1.0
        out = dict(dbar=float(np.linalg.norm(e.mean(0))), err=float(np.sqrt(np.mean(np.sum(e * e, 1)))),
                   stream=float(np.sqrt(np.mean(np.sum(h[-2] ** 2, 1)))),
                   open=float(np.mean([np.mean(z[i] > 0) for i in range(1, L - 1)])))
        W = [w.copy() for w in net.W]; b = [v.copy() for v in net.b]
        if prev:
            own_e, inh_e, own_c, inh_c, nclose_own, nclose, nopen, cor_a, cor_b = 0, 0, 0, 0, 0, 0, 0, [], []
            for i in range(1, L - 1):
                ho, hn, zo = prev["h"][i], h[i], prev["z"][i]
                own = ho @ (W[i] - prev["W"][i]).T + (b[i] - prev["b"][i])
                inh = (hn - ho) @ W[i].T
                own_e += np.sum(own ** 2); inh_e += np.sum(inh ** 2)
                own_c += len(own) * np.sum(own.mean(0) ** 2); inh_c += len(inh) * np.sum(inh.mean(0) ** 2)
                op = zo > 0; nopen += op.sum()
                nclose_own += np.sum(op & (zo + own <= 0)); nclose += np.sum(op & (z[i] <= 0))
                cor_a.append(own.mean(0)); cor_b.append(prev["W"][i] @ ho.mean(0))
            n_el = sum(prev["z"][i].size for i in range(1, L - 1))
            a, bb = np.concatenate(cor_a), np.concatenate(cor_b)
            out.update(own_rms=float(np.sqrt(own_e / n_el)), inh_rms=float(np.sqrt(inh_e / n_el)),
                       own_common=float(own_c / max(own_e, 1e-300)), inh_common=float(inh_c / max(inh_e, 1e-300)),
                       own_closes=float(nclose_own / max(nopen, 1)), closes=float(nclose / max(nopen, 1)),
                       corr_own_Wm=float(np.corrcoef(a, bb)[0, 1]) if np.std(a) > 0 and np.std(bb) > 0 else None)
        prev.update(h=h, z=z, W=W, b=b); prev["n"] = prev.get("n", 0) + 1
        if prev["n"] <= 6 or prev["n"] % 10 == 1:
            r = net.backward(X, y)  # deltas: r[3][i] = dL/dz_i; stream gradient into block i's output = deltas / (alpha * gate)
            # per-block log RMS of dL/dz_i scaled back by alpha (the signal arriving at each block)
            out["sg_by_block"] = [float(np.log(rms(r[3][i] / net.alpha) + 1e-300)) for i in range(1, L - 1)]
            out["open_by_block"] = [float(np.mean(z[i] > 0)) for i in range(1, L - 1)]
        return out
    return hook


if __name__ == "__main__":
    task, cond, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    base = dict(task=task, act="relu", depth=96, seed=seed)
    base.update({"plain": {}, "cap10": dict(kick_cap=10), "signed": dict(branch_sign=True)}[cond])
    a = run(dict(base, steps=20, log_every=1)); b = run(dict(base, steps=20, log_every=1), hook=make_hook())
    hook_inert = [e["train_loss"] for e in a["log"]] == [e["train_loss"] for e in b["log"]]
    fine = run(dict(base, steps=300, log_every=1), hook=make_hook())["log"]
    coarse = run(dict(base, steps=3000, log_every=10), hook=make_hook())["log"]
    fl = {e["step"]: e["train_loss"] for e in fine}
    deterministic = all(fl[e["step"]] == e["train_loss"] for e in coarse if e["step"] in fl)
    keep = lambda lg: [{k: v for k, v in e.items() if k not in ("stream_grad", "gate", "stream_norm", "branch_ratio", "density", "dead")} for e in lg]
    out = os.path.join(HERE, "..", "results", "e34", f"{task}_{cond}_s{seed}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(config=base, hook_inert=hook_inert, deterministic=deterministic, fine=keep(fine), coarse=keep(coarse)), open(out, "w"))
    print(out, "hook inert:", hook_inert, "deterministic:", deterministic, flush=True)
