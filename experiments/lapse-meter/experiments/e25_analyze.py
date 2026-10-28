"""Analysis for experiment 25 (exploratory), using the signatures fixed in E25_PLAN.md."""
import os, sys, json, glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R, FIG
CONDS = ["plain", "cap10", "warm50", "signed"]; TASKS = ["digits", "circle-clean"]


def runs(task, cond):
    return [json.load(open(f))["log"] for f in sorted(glob.glob(os.path.join(R, "e25", f"{task}_{cond}_s*.json")))]


def series(logs, key):
    steps = [e["step"] for e in logs[0] if key in e]
    vals = np.array([[e[key] for e in lg if key in e] for lg in logs])
    return np.array(steps), vals


out = ["# Experiment 25 results (exploratory)\n", "Means over 3 seeds; ranges in brackets. Signatures as fixed in E25_PLAN.md.\n"]
for task in TASKS:
    out.append(f"\n## {task}\n")
    out.append("| condition | step-0 kick (proposed) | max η·λ over steps 0–20 | loss at step 0 → max over 1–20 | share_W, step 0 → max 1–20 | share_g, step 0 → max 1–20 | gate flips block 1 at step 10 | all-block flips at step 10 | transport, step 0 → 200 |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for cond in CONDS:
        L = runs(task, cond)
        if not L: continue
        def at(key, s): return np.array([next(e[key] for e in lg if e["step"] == s) for lg in L])
        def mx(key, a, b): return np.array([max(e[key] for e in lg if a <= e["step"] <= b and key in e) for lg in L])
        k0 = at("kick_proposed", 0); es = mx("eta_sharp", 0, 20); l0 = at("loss", 0); lm = mx("loss", 1, 20)
        sw0, swm = at("share_W", 0), mx("share_W", 1, 20); sg0, sgm = at("share_g", 0), mx("share_g", 1, 20)
        f1, fa = at("flips_b1", 10), at("flips_all", 10); t0, t2 = at("transport", 0), at("transport", 200)
        rng = lambda v: f"[{v.min():.3g}–{v.max():.3g}]"
        out.append(f"| {cond} | {k0.mean():.3g} {rng(k0)} | {es.mean():.3g} {rng(es)} | {l0.mean():.2f} → {lm.mean():.2f} | {sw0.mean():.3f} → {swm.mean():.3f} | "
                   f"{sg0.mean():.3f} → {sgm.mean():.3f} | {f1.mean():.2f} {rng(f1)} | {fa.mean():.2f} | {t0.mean():+.2f} → {t2.mean():+.2f} |")
    fig, axs = plt.subplots(1, 5, figsize=(19, 3.6))
    for cond, col in zip(CONDS, ["C3", "C0", "C2", "0.5"]):
        L = runs(task, cond)
        if not L: continue
        for ax, key, lab in zip(axs, ["loss", "eta_sharp", "share_g", "flips_b1", "transport"],
                                ["training loss", "η·λmax (preconditioned)", "stream gradient share along shared direction", "gate flips since step 0, block 1", "transport"]):
            st, v = series(L, key)
            ax.plot(st, v.mean(0), color=col, lw=1.6, label=cond, marker="o" if key == "eta_sharp" else None, ms=3)
            ax.set_title(lab, fontsize=9); ax.set_xlabel("step")
            if key in ("loss", "eta_sharp"): ax.set_yscale("log")
    axs[1].axhline(2, color="0.6", lw=0.8, ls="--"); axs[0].legend(fontsize=8)
    fig.suptitle(f"Experiment 25, {task}: the first 200 steps of 96-layer residual ReLU", fontsize=10); fig.tight_layout()
    fig.savefig(os.path.join(FIG, f"e25_{task}.png"), dpi=115); plt.close(fig)
t = "\n".join(out); print(t); open(os.path.join(R, "e25_analysis.md"), "w").write(t + "\n")
