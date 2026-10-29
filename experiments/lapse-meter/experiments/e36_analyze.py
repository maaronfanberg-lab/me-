"""Analysis for experiment 36, applying E36_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
rows, S = [], {}
for t in ("digits", "circle-clean"):
    K = 10 if t == "digits" else 2
    for c in ("nomeanall", "nomeanall_cap10"):
        for s in range(5):
            f = os.path.join(R, "e36", f"{t}_{c}_s{s}_run.json")
            if not os.path.exists(f): continue
            r = json.load(open(f)); L = r["log"]; steps = r["config"]["steps"]
            diverged = L[-1]["step"] < steps
            failed = diverged or L[-1]["train_loss"] > 0.5 * np.log(K)
            lv = next((x for x in (0.03, 0.1, 0.3) if at_loss_key(L, x, "ln_transport") is not None), None)
            tr = at_loss_key(L, lv, "ln_transport") if lv else None
            broken = failed or tr is None or not np.isfinite(tr) or tr < 0.3
            tf = os.path.join(R, "e36", f"{t}_{c}_s{s}.json")
            td = None
            if os.path.exists(tf):
                fine = json.load(open(tf))["fine"]; st = {e["step"]: e["stream"] for e in fine}
                td = (st.get(5, np.nan) / st[0]) if 0 in st else None
            state = "diverged" if diverged else ("broken" if broken else "healthy")
            S.setdefault((t, c), []).append((state, td))
            rows.append(f"| {t} | {c} | {s} | {'–' if td is None else f'{td:.3f}'} | {'–' if tr is None else f'{tr:+.2f}'} | {L[-1]['step']} | {L[-1]['train_loss']:.4g} | **{state}** |")
def maj(t, c, f):
    v = S.get((t, c), []); return None if len(v) < 5 else sum(f(x) for x in v) >= 3
teardown = lambda x: x[1] is not None and x[1] < 0.25
V = {}
V["P36a (nomean prevents the teardown, both tasks)"] = all(maj(t, "nomeanall", lambda x: not teardown(x)) for t in ("digits", "circle-clean"))
V["P36b (nomean diverges on digits)"] = maj("digits", "nomeanall", lambda x: x[0] == "diverged")
V["P36c (nomean + cap 10 healthy, both tasks)"] = all(maj(t, "nomeanall_cap10", lambda x: x[0] == "healthy") for t in ("digits", "circle-clean"))
prevented = V["P36a (nomean prevents the teardown, both tasks)"]
if not prevented: dec = "void (the teardown is carried by the inherited part)"
elif maj("digits", "nomeanall", lambda x: x[0] == "diverged"): dec = "the escape"
elif maj("digits", "nomeanall", lambda x: x[0] == "healthy"): dec = "the damage"
else: dec = "neither (nomean breaks without diverging)"
out = ["# Experiment 36 results\n", "**Verdicts:** " + "; ".join(f"{k}: {'holds' if v else ('untestable' if v is None else 'fails')}" for k, v in V.items()) + ".\n",
       f"**Decision (digits):** the teardown is {dec}.\n",
       "| task | condition | seed | stream step 5 / step 0 | transport | last step | final loss | state |", "|---|---|---|---|---|---|---|---|"] + rows
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e36_analysis.md"), "w").write(t_ + "\n")
