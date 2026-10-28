"""Analysis for experiment 30, applying E30_PREREGISTRATION.md."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
P = json.load(open(os.path.join(HERE, "e30_predictions.json"))); rows, by, right, n = [], {}, 0, 0
for p in P:
    f = os.path.join(R, "..", p["run"])
    if not os.path.exists(f): continue
    r = json.load(open(f)); K = 10 if p["task"] == "digits" else 2; failed = r["log"][-1]["train_loss"] > 0.5 * np.log(K)
    lv = next((L for L in (0.03, 0.1, 0.3) if at_loss_key(r["log"], L, "ln_transport") is not None), None)
    t = at_loss_key(r["log"], lv, "ln_transport") if lv else None
    broken = failed or t is None or not np.isfinite(t) or t < 0.3; n += 1; right += (p["kick_says"] == ("broken" if broken else "healthy"))
    by.setdefault((p["task"], p["cond"]), []).append(broken)
    rows.append(f"| {p['task']} | {p['cond']} | {p['seed']} | {p['kick']:.1f} | {p['common']:.3f} | {p['kick_says']} | "
                + (f"{t:+.2f}" if t is not None else "–") + (f" (loss {lv})" if lv and lv != 0.03 else "")
                + (" failed to train" if failed else "") + f" | {r['log'][-1]['train_loss']:.4f} | {r['test_acc']:.3f} | "
                + f"{len(r.get('capped_steps', []))} | **{'broken' if broken else 'healthy'}** |")
def state(task, c):
    b = by.get((task, c), [])
    return None if len(b) < 3 else ("broken" if sum(b) >= 2 else "healthy")
so, cm, cap = state("digits", "signed_offset"), state("digits", "center_mult"), state("digits", "signed_offset_cap10")
ACC = {("broken", "broken"): "K (total kick size)", ("broken", "healthy"): "C (shared part of the kick)",
       ("healthy", "broken"): "A (kick amplified by a piled-up stream)", ("healthy", "healthy"): "C+A (both needed)"}
acc = ACC.get((so, cm), "untestable")
V = {"P30a (signed + offset broken, digits)": "untestable" if so is None else ("holds" if so == "broken" else "fails"),
     "P30b (center + multiplier broken, digits)": "untestable" if cm is None else ("holds" if cm == "broken" else "fails"),
     "P30c (signed + offset + cap 10 healthy, both tasks)": "untestable" if None in (cap, state("circle-clean", "signed_offset_cap10"))
     else ("holds" if cap == "healthy" == state("circle-clean", "signed_offset_cap10") else "fails")}
void = V["P30c (signed + offset + cap 10 healthy, both tasks)"] == "fails"
out = ["# Experiment 30 results\n", "**Verdicts:** " + "; ".join(f"{k}: {v}" for k, v in V.items()) + ".\n",
       f"**Account supported on digits:** {acc}" + (" (but P30c failed, so the offset condition's reading is void)" if void else "") + ".\n",
       f"Per-run kick rule right in {right} of {n} runs (reported, not tested).\n",
       "| task | condition | seed | effective step-one kick | common-mode share | rule says | transport | final loss | test acc | steps capped | observed |",
       "|---|---|---|---|---|---|---|---|---|---|---|"] + rows
t = "\n".join(out); print(t); open(os.path.join(R, "e30_analysis.md"), "w").write(t + "\n")
