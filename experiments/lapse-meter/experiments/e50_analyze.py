"""Analysis for experiment 50, applying E50_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
def state(r, lm):
    L = r["log"]
    if L[-1]["step"] < r["config"]["steps"]: return "diverged", None
    K = 82 if lm else (10 if r["config"]["task"] == "digits" else 2)
    if L[-1]["train_loss"] > (3.17 if lm else 0.5 * np.log(K)): return "broken", None
    lv = next((x for x in ((1.0, 1.5, 2.0, 2.5, 3.0) if lm else (0.03, 0.1, 0.3)) if at_loss_key(L, x, "ln_transport") is not None), None)
    t = at_loss_key(L, lv, "ln_transport") if lv else None
    return ("broken" if t is None or not np.isfinite(t) or t < 0.3 else "healthy"), t
cell = {}; rows = []
for sk in ("lm10",):
    for ck in ("c256", "c1024", "c4096", "c16384"):
        st, ts, acc = [], [], []
        for f in sorted(glob.glob(os.path.join(R, "e50", f"{sk}_{ck}_s*.json"))):
            r = json.load(open(f)); s, t = state(r, sk.startswith("lm")); st.append(s); acc.append(r["test_acc"]); ts.append(t)
        cell[sk, ck] = None if len(st) < 5 else sum(s == "healthy" for s in st)
        rows.append(f"| {sk} | {ck} | {sum(s == 'healthy' for s in st)} healthy, {sum(s == 'diverged' for s in st)} diverged of {len(st)} | "
                    + (f"{np.mean([t for t in ts if t is not None]):+.2f}" if any(t is not None for t in ts) else "–") + f" | {np.mean(acc):.3f} |")
fmt = lambda v: "untestable" if v is None else ("holds" if v else "fails")
V = {"P50 (some constant gives at least 3 of 5 healthy)": None if any(cell["lm10", k] is None for k in ("c256", "c1024", "c4096", "c16384")) else any(cell["lm10", k] >= 3 for k in ("c256", "c1024", "c4096", "c16384"))}
out = ["# Experiment 50 results\n", "**Verdicts:** " + "; ".join(f"{k}: {fmt(v)}" for k, v in V.items()) + ".\n",
       "| setting | condition | runs | mean transport (healthy-rule level) | test accuracy |", "|---|---|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e50_analysis.md"), "w").write(t_ + "\n")
