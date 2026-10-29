"""Analysis for experiment 53 (E53_PREREGISTRATION.md): per-run predictions in e53_predictions.json, fixed before any run."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
P = json.load(open(os.path.join(HERE, "e53_predictions.json"))); n = a = b = dis = dis_a = 0
for p in P:
    f = os.path.join(R, "..", p["run"])
    if not os.path.exists(f): continue
    r = json.load(open(f)); d = r["log"][-1]["step"] < r["config"]["steps"]; n += 1
    a += p["product_says"] == d; b += p["kick_says"] == d
    if p["product_says"] != p["kick_says"]: dis += 1; dis_a += p["product_says"] == d
out = ["# Experiment 53 results\n", f"Runs: {n}. Product rule right in {a} ({a/max(n,1):.0%}); kick-alone rule right in {b} ({b/max(n,1):.0%}). Where they disagree ({dis} runs), the product rule is right in {dis_a}.\n",
       f"**P53a (product rule at least 85% right): {'holds' if n and a / n >= 0.85 else 'fails'}. P53b (product beats kick alone): {'holds' if a > b else 'fails'}.**"]
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e53_analysis.md"), "w").write(t_ + "\n")
