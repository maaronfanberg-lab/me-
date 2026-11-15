"""Analysis for experiment 37, applying E37_PREREGISTRATION.md. Kicks: step-one kick of plain ReLU (results/e30_init.json,
seeds 0-2) or recomputed (seeds 3-4) times m; nomean does not change the step-one kick (it changes only the blocks)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
from e30_measure import measure
rows, pts = [], []
for t in ("digits", "circle-clean"):
    for s in range(5):
        k0 = measure(dict(task=t, depth=96, seed=s, act="relu"))["kick"]
        for m in (0.1, 0.3, 1, 3, 10):
            f = os.path.join(R, "e37", f"{t}_m{m}_s{s}.json")
            if not os.path.exists(f): continue
            r = json.load(open(f)); L = r["log"]; div = L[-1]["step"] < r["config"]["steps"]
            pts.append((t, m, s, k0 * m, div)); rows.append(f"| {t} | {m} | {s} | {k0*m:.0f} | {L[-1]['step']} | {L[-1]['train_loss']:.4g} | **{'diverged' if div else 'trained'}** |")
def maj(t, m): v = [d for (tt, mm, _, _, d) in pts if tt == t and mm == m]; return None if len(v) < 5 else sum(v) >= 3
a = maj("digits", 0.1); b = maj("circle-clean", 10)
ks = sorted({k for *_, k, _ in pts}); best = (0, None)
for c in ks:
    n = sum((k > c) == d for *_, k, d in pts)
    if n > best[0]: best = (n, c)
V = {"P37a (digits m=0.1 does not diverge)": None if a is None else not a, "P37b (circle m=10 diverges)": b,
     "P37c (one kick cutoff right in >= 45 of 50)": best[0] >= 45 if len(pts) == 50 else None}
fmt = lambda v: "untestable" if v is None else ("holds" if v else "fails")
dec = "supported" if all(V.values()) else ("refuted" if V["P37a (digits m=0.1 does not diverge)"] is False and V["P37b (circle m=10 diverges)"] is False else "mixed")
out = ["# Experiment 37 results\n", "**Verdicts:** " + "; ".join(f"{k}: {fmt(v)}" for k, v in V.items()) + f". Reading: **{dec}**.\n",
       f"Best single kick cutoff: diverge above {best[1]:.0f}, right in {best[0]} of {len(pts)} runs.\n",
       "| task | m | seed | step-one kick | last step | final loss | outcome |", "|---|---|---|---|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e37_analysis.md"), "w").write(t_ + "\n")
