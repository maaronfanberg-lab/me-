"""Analysis for experiment 39, applying E39_PREREGISTRATION.md."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
TAGS = ["circle-embed64u", "circle-std1", "digits-pca2", "circle-pad62noise", "digits_frozenin", "circle-embed64_frozenin"]
D = {}
for tag in TAGS:
    for m in (1, 3, 10):
        v = []
        for s in range(5):
            f = os.path.join(R, "e39", f"{tag}_m{m}_s{s}.json")
            if os.path.exists(f):
                r = json.load(open(f)); v.append(r["log"][-1]["step"] < r["config"]["steps"])
        D[tag, m] = v
div = lambda tag, m: None if len(D[tag, m]) < 5 else sum(D[tag, m]) >= 3
fmt = lambda v: "untestable" if v is None else ("holds" if v else "fails")
a = div("circle-embed64u", 10); b = div("circle-pad62noise", 10); c1, c2 = div("digits_frozenin", 1), div("circle-embed64_frozenin", 3)
V = {"P39a (circle-embed64u does not diverge at ×10)": None if a is None else not a,
     "P39b (circle-pad62noise diverges at ×10)": b,
     "P39c (frozen input layer prevents divergence)": None if None in (c1, c2) else (not c1 and not c2)}
acc = "untestable" if a is None else ("scale" if not a else "dimension")
out = ["# Experiment 39 results\n", "**Verdicts:** " + "; ".join(f"{k}: {fmt(v)}" for k, v in V.items()) + f". Account supported: **{acc}**.\n",
       "| condition | diverged at ×1 | at ×3 | at ×10 |", "|---|---|---|---|"]
for tag in TAGS: out.append(f"| {tag} | " + " | ".join(f"{sum(D[tag, m])} of {len(D[tag, m])}" for m in (1, 3, 10)) + " |")
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e39_analysis.md"), "w").write(t_ + "\n")
