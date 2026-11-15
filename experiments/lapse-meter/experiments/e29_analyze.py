"""Analysis for experiment 29, applying E29_PREREGISTRATION.md."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
P = json.load(open(os.path.join(HERE, "e29_predictions.json"))); rows, by, right, n = [], {}, 0, 0
for p in P:
    f = os.path.join(R, "..", p["run"])
    if not os.path.exists(f): continue
    r = json.load(open(f)); K = 10 if p["task"] == "digits" else 2; failed = r["log"][-1]["train_loss"] > 0.5 * np.log(K)
    lv = next((L for L in (0.03, 0.1, 0.3) if at_loss_key(r["log"], L, "ln_transport") is not None), None)
    t = at_loss_key(r["log"], lv, "ln_transport") if lv else None
    broken = failed or t is None or not np.isfinite(t) or t < 0.3; n += 1; right += (p["kick_says"] == ("broken" if broken else "healthy"))
    by.setdefault((p["task"], p["cond"]), []).append(broken)
    rows.append(f"| {p['task']} | {p['cond']} | {p['seed']} | {p['kick']:.1f} | {p['kick_says']} | " + (f"{t:+.2f}" if t is not None else "–")
                + (f" (loss {lv})" if lv and lv != 0.03 else "") + f" | {r['log'][-1]['train_loss']:.4f} | {r['test_acc']:.3f} | **{'broken' if broken else 'healthy'}** |")
def cond(c, want):
    v = [by.get((t, c), []) for t in ("digits", "circle-clean")]
    if any(len(b) < 3 for b in v): return "untestable"
    return "holds" if all((sum(b) >= 2) == want for b in v) else "fails"
V = {"P29a": cond("center", False), "P29b": cond("center_random", True)}
none = all(sum(by.get((t, "center"), [True] * 3)) >= 2 for t in ("digits", "circle-clean"))
dec = "supported" if all(v == "holds" for v in V.values()) else ("refuted" if none and len(by) == 4 else "mixed")
out = ["# Experiment 29 results\n", "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in V.items()) + f". Common-mode kick as the damaging part: **{dec}**.\n",
       f"Per-run kick rule right in {right} of {n} runs.\n",
       "| task | condition | seed | step-one kick | rule says | transport | final loss | test acc | observed |", "|---|---|---|---|---|---|---|---|---|"] + rows
t = "\n".join(out); print(t); open(os.path.join(R, "e29_analysis.md"), "w").write(t + "\n")
