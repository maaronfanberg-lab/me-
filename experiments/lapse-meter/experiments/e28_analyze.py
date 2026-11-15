"""Analysis for experiment 28, applying E28_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
from e9_12_analyze_lib import above, fmt
FAIL = 3.17
def load(name): return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(R, "e28", f"lm_{name}_s*.json")))]
def at(rs, L):
    v = [at_loss_key(r["log"], L, "ln_transport") for r in rs]; v = np.array([x for x in v if x is not None and np.isfinite(x)]); return v, len(rs)
def failed(rs): return sum(r["log"][-1]["train_loss"] > FAIL for r in rs)
pairs = [("P28a", "relu_x1", "signed_x1", False), ("P28b", "relu_x10", "signed_x10", True), ("P28c", "relu_x10_cap10", "signed_x10", False),
         ("P28d", "relu_x10_finalLN", "signed_x10_finalLN", False)]
out = ["# Experiment 28 results (language model)\n"]; V = {}
out.append("| prediction | ReLU condition | twin | level (nats) | ReLU transport | twin transport | ReLU below twin? (gap / threshold) | failed, ReLU / twin | final train loss, ReLU / twin | final test loss, ReLU / twin | observed | predicted |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for key, a_, b_, want_broken in pairs:
    a, b = load(a_), load(b_)
    if len(a) < 3 or len(b) < 3: V[key] = "untestable"; continue
    L = next((L for L in (1.0, 1.5, 2.0, 2.5, 3.0) if len(at(a, L)[0]) >= 2 and len(at(b, L)[0]) >= 2), None)
    if L is None:
        broken = True; cells = "– | – | – | –"
    else:
        va, vb = at(a, L), at(b, L); below, gap, thr = above(vb[0], va[0]); broken = below or failed(a) > failed(b)
        cells = f"{L} | {fmt(*va)} | {fmt(*vb)} | {'yes' if below else 'no'} ({-gap:+.2f} / {thr:.2f})"
    fl = lambda rs: np.mean([r["log"][-1]["train_loss"] for r in rs])
    tl = lambda rs: np.mean([r.get("test_loss", float("nan")) for r in rs])
    V[key] = "holds" if broken == want_broken else "fails"
    out.append(f"| {key} | {a_} | {b_} | {cells} | {failed(a)} / {failed(b)} | {fl(a):.3f} / {fl(b):.3f} | {tl(a):.3f} / {tl(b):.3f} | **{'broken' if broken else 'healthy'}** | {'broken' if want_broken else 'healthy'} |")
# per-run rule: a run is broken if it failed to train, or if its transport at its pair's level lies more than 2 twin
# standard deviations below the twin's mean (fixed before any run)
P = json.load(open(os.path.join(HERE, "e28_predictions.json"))); right = n = 0
twin_of = {a_: b_ for _, a_, b_, _ in pairs}; twin_of.update({b_: b_ for _, a_, b_, _ in pairs})
for p in P:
    f = os.path.join(R, "..", p["run"])
    if not os.path.exists(f): continue
    r = json.load(open(f)); tw = load(twin_of[p["cond"]])
    L = next((L for L in (1.0, 1.5, 2.0, 2.5, 3.0) if len(at(tw, L)[0]) >= 2), None)
    t = at_loss_key(r["log"], L, "ln_transport") if L else None
    tv = at(tw, L)[0] if L else np.array([])
    broken = r["log"][-1]["train_loss"] > FAIL or t is None or (len(tv) >= 2 and t < tv.mean() - 2 * tv.std(ddof=1))
    n += 1; right += (p["kick_says"] == ("broken" if broken else "healthy"))
out.append(f"\nPer-run rule (kick above 124 = broken) right in {right} of {n} runs.")
dec = "carries over" if all(V.get(k) == "holds" for k in ("P28a", "P28b", "P28c", "P28d")) else ("fails to carry over" if "fails" in (V.get("P28a"), V.get("P28b")) else "mixed")
out.insert(1, "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in V.items()) + f". Kick account on language modelling: **{dec}**.\n")
t = "\n".join(out); print(t); open(os.path.join(R, "e28_analysis.md"), "w").write(t + "\n")
