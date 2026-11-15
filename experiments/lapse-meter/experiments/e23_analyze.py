"""Analysis for experiment 23, applying E22_23_PREREGISTRATION.md."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
P = json.load(open(os.path.join(HERE, "e23_predictions.json")))
rows, score = [], {"kick": 0, "sharp": 0, "pileup": 0}; n = 0; by = {}
for p in P:
    f = os.path.join(R, "..", p["run"])
    if not os.path.exists(f): continue
    r = json.load(open(f)); task = p["task"]; K = 10 if task == "digits" else 2
    failed = r["log"][-1]["train_loss"] > 0.5 * np.log(K)
    level = next((L for L in (0.03, 0.1, 0.3) if at_loss_key(r["log"], L, "ln_transport") is not None), None)
    t = at_loss_key(r["log"], level, "ln_transport") if level else None
    broken = failed or t is None or not np.isfinite(t) or t < 0.3
    how = "failed to train" if failed else ("never reached 0.3" if t is None else ("collapsed" if t < 0.3 else "healthy"))
    obs = "broken" if broken else "healthy"; n += 1
    for k, key in (("kick", "kick_says"), ("sharp", "sharp_says"), ("pileup", "pileup_says")): score[k] += (p[key] == obs)
    by.setdefault((task, p["cond"]), []).append(broken)
    rows.append(f"| {task} | {p['cond']} | {p['seed']} | {p['kick']:.1f} | {p['kick_says']} | {p['sharp_says']} | {p['pileup_says']} | "
                + (f"{t:+.2f}" if t is not None and np.isfinite(t) else "–") + (f" (at loss {level})" if level and level != 0.03 else "")
                + f" | {how} | **{obs}** |")
def verdict(cond, want_broken):
    v = []
    for task in ("digits", "circle-clean"):
        b = by.get((task, cond), [])
        if len(b) < 3: return "untestable"
        v.append((sum(b) >= 2) == want_broken)
    return "holds" if all(v) else "fails"
V = {"P23a": verdict("C1", False), "P23b": verdict("C2", False), "P23c": verdict("C3", True),
     "P23d": "holds" if n == 18 and score["kick"] >= 15 and score["kick"] > score["sharp"] and score["kick"] > score["pileup"] else ("untestable" if n < 18 else "fails")}
hyp = "supported" if all(v == "holds" for v in V.values()) else ("refuted" if score["pileup"] > score["kick"] else "mixed")
out = ["# Experiment 23 results\n", "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in V.items()) + f". Readout-kick hypothesis: **{hyp}**.\n",
       f"Per-run predictions right: kick {score['kick']} of {n}, sharpness {score['sharp']} of {n}, pile-up ratio {score['pileup']} of {n}.\n",
       "| task | condition | seed | kick at init | kick says | sharpness says | pile-up says | transport | what happened | observed |",
       "|---|---|---|---|---|---|---|---|---|---|"] + rows
t = "\n".join(out); print(t); open(os.path.join(R, "e23_analysis.md"), "w").write(t + "\n")
