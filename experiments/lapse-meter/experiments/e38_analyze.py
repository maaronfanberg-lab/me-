"""Analysis for experiment 38, applying E38_PREREGISTRATION.md. Kicks: step-one kick of plain ReLU (results/e30_init.json,
seeds 0-2) or recomputed (seeds 3-4) times m; nomean does not change the step-one kick (it changes only the blocks)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
from e30_measure import measure
rows, pts = [], []
for t in ("digits-2class", "circle-embed64"):
    for s in range(5):
        k0 = measure(dict(task=t, depth=96, seed=s, act="relu"))["kick"]
        for m in (1, 3, 10):
            f = os.path.join(R, "e38", f"{t}_m{m}_s{s}.json")
            if not os.path.exists(f): continue
            r = json.load(open(f)); L = r["log"]; div = L[-1]["step"] < r["config"]["steps"]
            pts.append((t, m, s, k0 * m, div)); rows.append(f"| {t} | {m} | {s} | {k0*m:.0f} | {L[-1]['step']} | {L[-1]['train_loss']:.4g} | **{'diverged' if div else 'trained'}** |")
def maj(t, m): v = [d for (tt, mm, _, _, d) in pts if tt == t and mm == m]; return None if len(v) < 5 else sum(v) >= 3
d2, c64 = maj("digits-2class", 10), maj("circle-embed64", 10)
dec = "untestable" if None in (d2, c64) else {(False, False): "class count (or both needed)", (True, True): "input size", (True, False): "mixed", (False, True): "mixed"}[(d2, c64)]
fmt = lambda v: "untestable" if v is None else ("diverges" if v else "does not diverge")
out = ["# Experiment 38 results\n", f"**At ×10:** digits-2class {fmt(d2)}; circle-embed64 {fmt(c64)}. Account supported: **{dec}**.\n",
       "| task | m | seed | step-one kick | last step | final loss | outcome |", "|---|---|---|---|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e38_analysis.md"), "w").write(t_ + "\n")
