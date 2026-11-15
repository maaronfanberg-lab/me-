"""Exploratory follow-up to experiment 29 (written after its results; nothing here was pre-registered).

Three traces of the first steps, digits, 96 layers, seed 0 (the circle runs fit within 25 steps and say little):
  A. plain ReLU vs fixed centering: stream size, the readout input's shared and example-specific parts, logits.
     Question: why does centering, which shrinks the step-one kick 14-fold, diverge or nearly diverge?
  B. plain vs kick cap 10 vs signed twin: fraction of gates open per example, units dead for every example,
     stream size, transport. Question: what does the shock do to the blocks?
  C. how many runs in all results reach loss 0.03 by their first logged step after 0 (the transport reading then
     reflects the network a few steps after initialization).
Writes results/e29_followup.md. Every trace uses probe_run.py with a read-only hook, so the runs are the
pre-registered ones exactly.
"""
import os, sys, json, glob, collections, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
from probe_run import run
from e8_analyze import at_loss_key, R
warnings.filterwarnings("ignore")
rms = lambda a: float(np.sqrt(np.mean(np.sum(a * a, 1))))


def hook_a(net, X, y):
    h, z = net.forward(X); ri = net.readout_input(X); lz = z[-1]
    return dict(xh=rms(h[-1]), ri_mean=float(np.linalg.norm(ri.mean(0))), ri_spec=rms(ri - ri.mean(0)),
                lrms=rms(lz), lcommon=float(np.linalg.norm(lz.mean(0))))


def hook_b(net, X, y):
    h, z = net.forward(X); L = len(net.W); blocks = range(1, L - 1)
    return dict(xdead=float(np.mean([np.mean(np.all(z[i] <= 0, axis=0)) for i in blocks])),
                xopen=float(np.mean([np.mean(z[i] > 0) for i in blocks])), xh=rms(h[-2]))


out = ["# Experiment 29 follow-up (exploratory, after the results)\n"]
out += ["## A. Plain ReLU against fixed centering, digits seed 0, first 20 steps\n",
        "| step | plain: loss | plain: last stream | plain: shared logits | center: loss | center: last stream | center: readout input, shared part | center: shared logits |",
        "|---|---|---|---|---|---|---|---|"]
A = {k: run(dict(task="digits", depth=96, act="relu", block="ln", ln=k, seed=0, steps=20, log_every=1), hook=hook_a)["log"] for k in ("none", "center")}
for p, c in zip(A["none"], A["center"]):
    out.append(f"| {p['step']} | {p['train_loss']:.3g} | {p['xh']:.0f} | {p['lcommon']:.3g} | {c['train_loss']:.3g} | {c['xh']:.0f} | {c['ri_mean']:.0f} | {c['lcommon']:.3g} |")
out += ["\n## B. What the first steps do to the blocks, digits seed 0\n",
        "| condition | step | gates open per example | units dead for every example | last stream | transport |", "|---|---|---|---|---|---|"]
for name, cfg in (("plain", {}), ("kick cap 10", dict(kick_cap=10)), ("signed twin", dict(branch_sign=True))):
    for e in run(dict(task="digits", depth=96, act="relu", seed=0, steps=200, log_every=1, **cfg), hook=hook_b)["log"]:
        if e["step"] in (0, 1, 2, 3, 5, 10, 20, 50, 100, 200):
            out.append(f"| {name} | {e['step']} | {e['xopen']:.2f} | {e['xdead']:.2f} | {e['xh']:.0f} | {e['ln_transport']:+.2f} |")
out += ["\n## C. Runs whose loss-0.03 reading falls at or before their first logged step after 0\n"]
rows = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(R, "e*", "*.json"))):
    try: r = json.load(open(f))
    except Exception: continue
    if not isinstance(r, dict) or not r.get("log") or "ln_transport" not in r["log"][0]: continue
    L = r["log"]; st = next((e["step"] for e in L if e["train_loss"] < 0.03), None)
    if st is None: continue
    rows[(f.split(os.sep)[-2], os.path.basename(f).rsplit("_s", 1)[0])].append((st, L[1]["step"] if len(L) > 1 else None))
fast = sorted(k for k, v in rows.items() if any(s <= first for s, first in v if first))
out.append(f"{len(fast)} of {len(rows)} conditions that reach loss 0.03: " + ", ".join(f"{a}/{b}" for a, b in fast) + ".")
t = "\n".join(out); print(t); open(os.path.join(R, "e29_followup.md"), "w").write(t + "\n")
