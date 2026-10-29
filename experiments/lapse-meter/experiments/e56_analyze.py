"""Analysis for experiment 56, applying E56_PREREGISTRATION.md."""
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
for sk in ("d96", "c96", "lm10", "d192"):
    for ck in ("dyt", "bcenter"):
        st, ts, acc = [], [], []
        for f in sorted(glob.glob(os.path.join(R, "e56", f"{sk}_{ck}_s*.json"))):
            r = json.load(open(f)); s, t = state(r, sk == "lm10"); st.append(s); acc.append(r["test_acc"]); ts.append(t)
        cell[sk, ck] = None if len(st) < 5 else sum(s == "healthy" for s in st) >= 3
        rows.append(f"| {sk} | {ck} | {sum(s == 'healthy' for s in st)} healthy, {sum(s == 'diverged' for s in st)} diverged of {len(st)} | "
                    + (f"{np.mean([t for t in ts if t is not None]):+.2f}" if any(t is not None for t in ts) else "–") + f" | {np.mean(acc):.3f} |")
fmt = lambda v: "untestable" if v is None else ("holds" if v else "fails")
g = lambda k, c: cell.get((k, c))
A = None if None in (g("d96","bcenter"), g("c96","bcenter"), g("lm10","bcenter"), g("d192","bcenter")) else (g("d96","bcenter") and g("c96","bcenter") and g("lm10","bcenter") and not g("d192","bcenter"))
B = None if g("d96","dyt") is None else not g("d96","dyt")
out = ["# Experiment 56 results\n", f"**Verdicts:** P56a (bcenter healthy at 96 layers, broken at 192): {fmt(A)}; P56b (dyt broken on digits 96): {fmt(B)}.\n",
       "| setting | condition | runs | mean transport (healthy-rule level) | test accuracy |", "|---|---|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e56_analysis.md"), "w").write(t_ + "\n")
