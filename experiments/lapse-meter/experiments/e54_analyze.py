"""Analysis for experiment 54 (E54_PREREGISTRATION.md)."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
def at(L, lv):
    for a, b in zip(L, L[1:]):
        if a["train_loss"] >= lv > b["train_loss"]:
            f = (np.log(a["train_loss"]) - np.log(lv)) / (np.log(a["train_loss"]) - np.log(b["train_loss"])); return a["transport"] + f * (b["transport"] - a["transport"])
cell = {}; rows = []
for t in ("digits", "circle-clean"):
    for c in ("plain", "cap10", "norm"):
        st = []
        for f in sorted(glob.glob(os.path.join(R, "e54", f"{t}_{c}_s*.json"))):
            r = json.load(open(f)); L = r["log"]; K = 10 if t == "digits" else 2
            lv = next((x for x in (0.03, 0.1, 0.3) if at(L, x) is not None), None); tr = at(L, lv) if lv else None
            bad = L[-1]["step"] < 6000 or L[-1]["train_loss"] > 0.5 * np.log(K) or tr is None or tr < 0.3; st.append(not bad)
        cell[t, c] = None if len(st) < 5 else sum(st) >= 3; rows.append(f"| {t} | {c} | {sum(st)} of {len(st)} healthy |")
ok = lambda t, c, want: cell[t, c] is not None and cell[t, c] == want
V = {"P54a (plain broken, both tasks)": ok("digits", "plain", False) and ok("circle-clean", "plain", False),
     "P54b (kick cap 10 healthy, both)": ok("digits", "cap10", True) and ok("circle-clean", "cap10", True),
     "P54c (per-step readout norm healthy, both)": ok("digits", "norm", True) and ok("circle-clean", "norm", True)}
out = ["# Experiment 54 results (PyTorch replication)\n", "**Verdicts:** " + "; ".join(f"{k}: {'holds' if v else 'fails'}" for k, v in V.items()) + ".\n", "| task | condition | runs |", "|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e54_analysis.md"), "w").write(t_ + "\n")
