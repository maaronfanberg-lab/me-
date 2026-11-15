"""Analysis for experiment 31 (exploratory), using the signature fixed in E31_PLAN.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
K = ("ln_transport", "tr_specific", "tr_shared", "share_top", "share_bot", "mshare_bot")
out = ["# Experiment 31 results (exploratory)\n", "Read at the first logged step with training loss below 0.03; means ± sd over 3 seeds.\n",
       "| task | network | step | transport | example-specific transport | shared transport | shared share, top | shared share, bottom | bottom energy along m |",
       "|---|---|---|---|---|---|---|---|---|"]
gaps = {}
for task in ("digits", "circle-clean"):
    M = {}
    for kind in ("relu", "signed"):
        V = []
        for f in sorted(glob.glob(os.path.join(R, "e31", f"{task}_final_{kind}_s*.json"))):
            lg = json.load(open(f))["log"]; e = next(x for x in lg if x["train_loss"] < 0.03); V.append([e["step"]] + [e[k] for k in K])
        if not V: continue
        V = np.array(V); M[kind] = V[:, 1:].mean(0)
        out.append(f"| {task} | {kind} | {V[:,0].mean():.0f} | " + " | ".join(f"{V[:,i].mean():+.2f} ± {V[:,i].std(ddof=1) if len(V) > 1 else 0:.2f}" for i in range(1, len(K) + 1)) + " |")
    if len(M) == 2: gaps[task] = (M["relu"][0] - M["signed"][0], M["relu"][1] - M["signed"][1])
out.append("")
for t, (gt, gs) in gaps.items(): out.append(f"- {t}: total gap {gt:+.2f}, example-specific gap {gs:+.2f} (ratio {gs / gt:.2f})")
if len(gaps) == 2:
    r = [gs / gt for gt, gs in gaps.values()]
    ans = "shared" if all(x < 0.5 for x in r) else ("specific" if all(x >= 1.0 for x in r) else "mixed")
    out.append(f"\n**Answer (signature in E31_PLAN.md): {ans}.**")
t = "\n".join(out); print(t); open(os.path.join(R, "e31_analysis.md"), "w").write(t + "\n")
