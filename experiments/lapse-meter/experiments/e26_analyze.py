"""Analysis for experiment 26, applying E26_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
from e9_12_analyze_lib import above, fmt
def load(pat): return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(R, "e26", pat)))]
def failed(rs, task): return sum(r["log"][-1]["train_loss"] > 0.5 * np.log(10 if task == "digits" else 2) for r in rs)
def at(rs, L):
    v = [at_loss_key(r["log"], L, "ln_transport") for r in rs]; v = np.array([x for x in v if x is not None and np.isfinite(x)]); return v, len(rs)
out = ["# Experiment 26 results\n"]; V = {}
lab = {"final": "P26a", "pre": "P26b", "pre_final": "P26c", "post": "P26d"}
out.append("| task | placement | level | ReLU transport | signed twin transport | ReLU below twin? (gap / threshold) | failed to train, ReLU / twin | final loss, ReLU / twin | test acc, ReLU / twin | healthy? |")
out.append("|---|---|---|---|---|---|---|---|---|---|")
for ln in ("final", "pre", "pre_final", "post"):
    res = []
    for task in ("digits", "circle-clean"):
        a, b = load(f"{task}_{ln}_relu_s*.json"), load(f"{task}_{ln}_signed_s*.json")
        if len(a) < 3 or len(b) < 3: res.append(None); continue
        L = next((L for L in (0.03, 0.1, 0.3) if len(at(a, L)[0]) >= 2 and len(at(b, L)[0]) >= 2), None)
        if L is None: res.append(False); out.append(f"| {task} | {ln} | – | – | – | – | {failed(a, task)} / {failed(b, task)} | – | – | **no (levels not reached)** |"); continue
        va, vb = at(a, L), at(b, L); below, gap, thr = above(vb[0], va[0])
        ok = (not below) and failed(a, task) <= failed(b, task); res.append(ok)
        fl = lambda rs: np.mean([r["log"][-1]["train_loss"] for r in rs]); ta = lambda rs: np.mean([r["test_acc"] for r in rs])
        out.append(f"| {task} | {ln} | {L} | {fmt(*va)} | {fmt(*vb)} | {'yes' if below else 'no'} ({-gap:+.2f} / {thr:.2f}) | {failed(a, task)} / {failed(b, task)} | {fl(a):.4f} / {fl(b):.4f} | {ta(a):.3f} / {ta(b):.3f} | **{'yes' if ok else 'no'}** |")
    V[lab[ln]] = "untestable" if None in res else ("holds" if all(res) else "fails")
out.append("\n**Stress case, 192 layers, ReLU (reported, not tested):**\n")
out.append("| task | placement | transport at loss 0.03 | failed to train | final loss | test acc |\n|---|---|---|---|---|---|")
for task in ("digits", "circle-clean"):
    for ln in ("pre", "pre_final"):
        rs = load(f"{task}_{ln}_relu_d192_s*.json")
        if rs: out.append(f"| {task} | {ln} | {fmt(*at(rs, 0.03))} | {failed(rs, task)} of {len(rs)} | {np.mean([r['log'][-1]['train_loss'] for r in rs]):.4f} | {np.mean([r['test_acc'] for r in rs]):.3f} |")
fa = [V.get("P26a"), V.get("P26b")]
dec = "supported" if fa == ["holds", "holds"] else "mixed"
out.insert(1, "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in V.items()) + f". Kick account of normalization: **{dec}** (refuted only if P26a fails on both tasks; see table).\n")
t = "\n".join(out); print(t); open(os.path.join(R, "e26_analysis.md"), "w").write(t + "\n")
