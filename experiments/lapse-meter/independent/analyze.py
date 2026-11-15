"""Verdicts for independent/replicate.py, using the predictions fixed in its header."""
import json, glob, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); out = []
rule = {"plain": ("R1", lambda m: m < 0.30, "below +0.30"), "warm50": ("R2", lambda m: m > 0.50, "above +0.50"),
        "warmout": ("R3", lambda m: m > 0.50, "above +0.50"), "signed": ("R4", lambda m: m > 0.50, "above +0.50")}
out.append("| task | condition | transport at loss 0.03, per seed | mean | prediction | holds? | test accuracy |\n|---|---|---|---|---|---|---|")
for task in ("digits", "circle"):
    for cond, (rid, ok, txt) in rule.items():
        rs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(H, "results", f"{task}_{cond}_s*.json")))]
        v = [r["transport_at_0_03"] for r in rs]; vv = [x for x in v if x is not None]
        m = np.mean(vv) if vv else float("nan")
        verdict = "untestable" if len(vv) < 2 else ("holds" if ok(m) else "fails")
        cells = ", ".join("never reached" if x is None else f"{x:+.2f}" for x in v)
        out.append(f"| {task} | {cond} | {cells} | {m:+.2f} | {rid}: {txt} | **{verdict}** | {np.mean([r['test_acc'] for r in rs]):.3f} |")
t = "\n".join(out); print(t); open(os.path.join(H, "results.md"), "w").write("# Independent replication results\n\n" + t + "\n")
