"""Analysis for experiment 55 (E55_PREREGISTRATION.md)."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
rows = []
for D in (8, 32):
    for c in ("plain", "cap10", "norm", "finalln"):
        L = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(R, "e55", f"tf{D}_{c}_s*.json")))]
        if not L: continue
        fl = [r["log"][-1]["train_loss"] for r in L]; tr = [r["log"][-1]["transport"] for r in L]; dv = sum(r["log"][-1]["step"] < 6000 for r in L)
        rows.append(f"| {D} | {c} | {len(L)} | {dv} | {np.mean(fl):.3f} | {np.mean([r['test_loss'] for r in L]):.3f} | {np.mean(tr):+.2f} |")
out = ["# Experiment 55 results (transformer, exploratory)\n", "| depth | condition | runs | diverged | final train loss | test loss | final transport |", "|---|---|---|---|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e55_analysis.md"), "w").write(t_ + "\n")
