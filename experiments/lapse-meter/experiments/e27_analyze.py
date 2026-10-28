"""Analysis for experiment 27, applying E27_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
rows, by = [], {}
for task in ("digits", "circle-clean"):
    for k in (1, 2, 3, 5, 10):
        for f in sorted(glob.glob(os.path.join(R, "e27", f"{task}_until{k}_s*.json"))):
            r = json.load(open(f)); K = 10 if task == "digits" else 2; failed = r["log"][-1]["train_loss"] > 0.5 * np.log(K)
            lv = next((L for L in (0.03, 0.1, 0.3) if at_loss_key(r["log"], L, "ln_transport") is not None), None)
            t = at_loss_key(r["log"], lv, "ln_transport") if lv else None
            broken = failed or t is None or not np.isfinite(t) or t < 0.3; by.setdefault((task, k), []).append(broken)
            rows.append(f"| {task} | {k} | {r['config']['seed']} | {r.get('capped_steps', [])} | " + (f"{t:+.2f}" if t is not None else "–")
                        + (f" (loss {lv})" if lv and lv != 0.03 else "") + f" | {r['log'][-1]['train_loss']:.4f} | **{'broken' if broken else 'healthy'}** |")
def cond(k):
    v = [by.get((t, k), []) for t in ("digits", "circle-clean")]
    if any(len(b) < 3 for b in v): return "untestable"
    return "holds" if all(sum(b) <= 1 for b in v) else "fails"
V = {"P27a": cond(2), "P27b": "holds" if cond(5) == "holds" and cond(10) == "holds" else ("untestable" if "untestable" in (cond(5), cond(10)) else "fails")}
summary = " ".join(f"k={k}: digits {3 - sum(by.get(('digits', k), [0]*3))}/3 healthy, circle {3 - sum(by.get(('circle-clean', k), [0]*3))}/3;" for k in (1, 2, 3, 5, 10))
dec = "supported" if V["P27a"] == "holds" else ("refuted" if cond(10) == "fails" else "mixed")
out = ["# Experiment 27 results\n", "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in V.items()) + f". Damage in the first two readout updates: **{dec}**.\n",
       summary + "\n", "| task | window k | seed | steps the cap bound | transport | final loss | observed |", "|---|---|---|---|---|---|---|"] + rows
t = "\n".join(out); print(t); open(os.path.join(R, "e27_analysis.md"), "w").write(t + "\n")
