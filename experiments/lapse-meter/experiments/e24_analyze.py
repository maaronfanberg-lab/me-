"""Analysis for experiment 24, applying E24_PREREGISTRATION.md."""
import os, sys, json
import numpy as np
from scipy.stats import spearmanr
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
P = json.load(open(os.path.join(HERE, "e24_predictions.json")))
def outcome(f, task):
    r = json.load(open(f)); K = 10 if task == "digits" else 2
    failed = r["log"][-1]["train_loss"] > 0.5 * np.log(K)
    lv = next((L for L in (0.03, 0.1, 0.3) if at_loss_key(r["log"], L, "ln_transport") is not None), None)
    t = at_loss_key(r["log"], lv, "ln_transport") if lv else None
    return r, failed or t is None or not np.isfinite(t) or t < 0.3, t, lv, failed
rows, by, right, n, dose = [], {}, 0, 0, {}
for p in P:
    f = os.path.join(R, "..", p["run"])
    if not os.path.exists(f): continue
    r, broken, t, lv, failed = outcome(f, p["task"]); n += 1; right += (p["kick_says"] == ("broken" if broken else "healthy"))
    by.setdefault((p["task"], p["cond"]), []).append(broken)
    if p["cond"].startswith("cap"): dose.setdefault(p["task"], []).append((np.log(p["kick"]), -1.0 if t is None else t))
    cs = r.get("capped_steps", [])
    rows.append(f"| {p['task']} | {p['cond']} | {p['seed']} | {p['kick']:.1f} | {p['kick_says']} | " + (f"{t:+.2f}" if t is not None else "–")
                + (f" (loss {lv})" if lv and lv != 0.03 else "") + f" | {'failed to train' if failed else ''} | {len(cs)}" + (f" (last {cs[-1]})" if cs else "") + f" | **{'broken' if broken else 'healthy'}** |")
def cond(c, want, tasks=("digits", "circle-clean")):
    v = []
    for t in tasks:
        b = by.get((t, c), [])
        if len(b) < 3: return "untestable"
        v.append((sum(b) >= 2) == want)
    return "holds" if all(v) else "fails"
V = {"P24a": "holds" if all(cond(f"cap{c}", False) == "holds" for c in (3, 10, 30)) else ("untestable" if any(cond(f"cap{c}", False) == "untestable" for c in (3, 10, 30)) else "fails"),
     "P24b": cond("cap1000", True, ("digits",)), "P24d": cond("zloss0.0001", True), "P24e": cond("zloss0.01", True)}
rho = {t: spearmanr([a for a, _ in d], [b for _, b in d]).statistic for t, d in dose.items() if len(d) == 18}
V["P24c"] = "holds" if len(rho) == 2 and all(v <= -0.6 for v in rho.values()) else ("untestable" if len(rho) < 2 else "fails")
p24a_any = [cond(f"cap{c}", False, (t,)) for c in (3, 10, 30) for t in ("digits", "circle-clean")]
dec = "supported (cause)" if all(V[k] == "holds" for k in ("P24a", "P24b", "P24c")) else ("refuted (correlate)" if all(cond(f"cap{c}", False, ("digits",)) == "fails" and cond(f"cap{c}", False, ("circle-clean",)) == "fails" for c in (3, 10, 30)) else "mixed")
out = ["# Experiment 24 results\n", "**Verdicts:** " + ", ".join(f"{k} {V[k]}" for k in ("P24a", "P24b", "P24c", "P24d", "P24e")) + f". Kick as a cause: **{dec}**.\n",
       "Spearman(log effective kick, transport) over the cap runs: " + ", ".join(f"{t} {v:+.2f}" for t, v in rho.items()) + ".\n",
       f"Per-run rule right in {right} of {n} runs.\n",
       "| task | condition | seed | effective step-one kick | rule says | transport | | steps the cap bound | observed |", "|---|---|---|---|---|---|---|---|---|"] + rows
t = "\n".join(out); print(t); open(os.path.join(R, "e24_analysis.md"), "w").write(t + "\n")
