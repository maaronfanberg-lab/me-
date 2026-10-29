"""Analysis for experiment 40, applying E40_PREREGISTRATION.md."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
D = {}
for tag in ("A", "A3", "B", "Astd1"):
    v = []
    for s in range(5):
        f = os.path.join(R, "e40", f"{tag}_s{s}.json")
        if os.path.exists(f):
            r = json.load(open(f)); v.append((r["log"][-1]["step"] < r["config"]["steps"], r["log"][-1]["step"], r["log"][-1]["train_loss"]))
    D[tag] = v
div = lambda t: None if len(D[t]) < 5 else sum(x[0] for x in D[t]) >= 3
a, a3 = div("A"), div("A3")
fmt = lambda v: "untestable" if v is None else ("holds" if v else "fails")
out = ["# Experiment 40 results\n", f"**Verdicts:** P40a (readout alone diverges at ×10): {fmt(a)}; P40b (A3 does not diverge): {fmt(None if a3 is None else not a3)}. Route: **{'untestable' if a is None else ('readout alone' if a else 'the blocks')}**.\n",
       "| condition | diverged | last steps | final losses |", "|---|---|---|---|"]
for t, v in D.items(): out.append(f"| {t} | {sum(x[0] for x in v)} of {len(v)} | {', '.join(str(x[1]) for x in v)} | {', '.join(f'{x[2]:.3g}' for x in v)} |")
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e40_analysis.md"), "w").write(t_ + "\n")
