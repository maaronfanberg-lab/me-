"""Analysis for experiments 41-46, applying E41_46_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
P = {"E41a": False, "E41b": True, "E42a": True, "E42b": False, "E43a": False, "E43b": True, "E46a": True, "E46b": False}
out = ["# Experiments 41–46 results\n", "| condition | diverged | needed | predicted | result |", "|---|---|---|---|---|"]; held = n = 0
for tag, want in P.items():
    fs = sorted(glob.glob(os.path.join(R, "e41_46", f"{tag}_s*.json"))); runs = [json.load(open(f)) for f in fs]
    d = sum(r["log"][-1]["step"] < r["config"]["steps"] for r in runs); need = 8 if tag.startswith("E46") else 3
    tot = 10 if tag.startswith("E46") else 5
    if len(runs) < tot: out.append(f"| {tag} | {d} of {len(runs)} | – | {'diverges' if want else 'trains'} | untestable |"); continue
    got = d >= need if want else (len(runs) - d) >= need; held += got; n += 1
    out.append(f"| {tag} | {d} of {len(runs)} | {need} | {'diverges' if want else 'trains'} | **{'holds' if got else 'fails'}** |")
dec = "supported" if held >= 7 else ("refuted" if n - held >= 4 else "mixed")
out.insert(1, f"**{held} of {n} predictions held. Rule: {dec}.**\n")
out += ["\n## E45 (exploratory): blocks route, digits, input frozen, readout ×10\n", "| condition | runs diverged | last stream before divergence or at 300 (median) | max own-part closes, steps 1–20 (median) |", "|---|---|---|---|"]
for c in ("frozen", "slow"):
    L = [json.load(open(f))["log"] for f in sorted(glob.glob(os.path.join(R, "e41_46", f"E45_{c}_s*.json")))]
    if not L: continue
    dv = sum(l[-1]["step"] < 300 for l in L)
    st = np.median([next((e["stream"] for e in reversed(l) if np.isfinite(e.get("stream", np.nan))), np.nan) for l in L])
    oc = np.median([max([e.get("own_closes") or 0 for e in l if 1 <= e["step"] <= 20] or [0]) for l in L])
    out.append(f"| {c} | {dv} of {len(L)} | {st:.3g} | {oc:.3f} |")
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e41_46_analysis.md"), "w").write(t_ + "\n")
