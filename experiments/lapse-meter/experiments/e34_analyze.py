"""Analysis for experiment 34 (exploratory), reading each question exactly as E34_PLAN.md fixed it.
Means ± sd over seeds; writes results/e34_analysis.md and figures/e34_teardown.png."""
import os, sys, json, glob
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R, FIG
TASKS, CONDS = ("digits", "circle-clean"), ("plain", "cap10", "signed")
D = {(t, c): [json.load(open(f)) for f in sorted(glob.glob(os.path.join(R, "e34", f"{t}_{c}_s*.json")))] for t in TASKS for c in CONDS}
ms = lambda v: (f"{np.mean(v):.3g} ± {np.std(v, ddof=1):.2g}" if len(v) > 1 else f"{v[0]:.3g}") if len(v) else "–"
def at(run, key, step, which="fine"):
    e = next((x for x in run[which] if x["step"] == step), None)
    return None if e is None else e.get(key)
out = ["# Experiment 34 results (exploratory)\n"]
out.append("Checks: " + ", ".join(f"{t}/{c}: {len(D[t, c])} runs, hook inert {all(r['hook_inert'] for r in D[t, c])}, deterministic {all(r['deterministic'] for r in D[t, c])}" for t in TASKS for c in CONDS) + "\n")
out.append("## Q1, Q2: what moves the pre-activations, steps 1–5\n")
out.append("| task | condition | step | stream | gates open | own RMS | inherited RMS | own: shared share | inherited: shared share | closed by own part alone | closed in fact | corr(own, −W·m)… see note |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for t in TASKS:
    for c in CONDS:
        for s in (1, 2, 3, 5):
            g = lambda k: [v for v in (at(r, k, s) for r in D[t, c]) if v is not None]
            out.append(f"| {t} | {c} | {s} | {ms(g('stream'))} | {ms(g('open'))} | {ms(g('own_rms'))} | {ms(g('inh_rms'))} | {ms(g('own_common'))} | {ms(g('inh_common'))} | {ms(g('own_closes'))} | {ms(g('closes'))} | {ms(g('corr_own_Wm'))} |")
out.append("\nThe last column is corr(own part's batch mean, W·m) over units; negative = the own update pushes each unit against the shared stream's contribution to it.\n")
out.append("## Q3: does the teardown end when the shared error is corrected?\n")
out.append("Per run: the peak of |d̄| over steps 0–50, the first step after the peak with |d̄| below half of it, and the first step from which the stream shrinks by less than 10% per step for 5 steps running. Read as in the plan: 'yes' if the second is within one step of the first.\n")
out.append("| task | condition | seed | peak |d̄| (step) | |d̄| below half from step | shrink under 10%/step from step | within one step? |")
out.append("|---|---|---|---|---|---|---|")
for t in TASKS:
    for c in ("plain", "cap10"):
        for r in D[t, c]:
            f = [e for e in r["fine"] if e["step"] <= 60]
            db = np.array([e["dbar"] for e in f]); st = np.array([e["stream"] for e in f])
            pk = int(np.argmax(db[:51])); half = next((i for i in range(pk, len(db)) if db[i] < db[pk] / 2), None)
            sh = np.r_[np.nan, 1 - st[1:] / st[:-1]]
            calm = next((i for i in range(1, len(sh) - 5) if all(abs(sh[j]) < 0.10 for j in range(i, i + 5))), None)
            ok = None if half is None or calm is None else abs(calm - half) <= 1
            out.append(f"| {t} | {c} | {r['config']['seed']} | {db[pk]:.3f} ({pk}) | {half if half is not None else '–'} | {calm if calm is not None else '–'} | {ok if ok is not None else '–'} |")
out.append("\n## Q4: where in depth the backward signal stops\n")
out.append("Mean over seeds of per-block log RMS signal arriving at each block (dL/dz / α) and gate-open fraction, for blocks 1, 24, 48, 72, 95.\n")
out.append("| task | condition | step | signal at blocks 1 / 24 / 48 / 72 / 95 | open at blocks 1 / 24 / 48 / 72 / 95 |")
out.append("|---|---|---|---|---|")
pick = [0, 23, 47, 71, 94]
def prof(r, key, step):
    for w in ("fine", "coarse"):
        e = next((x for x in r[w] if x["step"] == step and key in x), None)
        if e: return e[key]
for t in TASKS:
    for c in CONDS:
        for s in (2, 20, 100, 500, 2000):
            P = [p for p in (prof(r, "sg_by_block", s) for r in D[t, c]) if p]; O = [p for p in (prof(r, "open_by_block", s) for r in D[t, c]) if p]
            if not P: continue
            mp, mo = np.mean(P, 0), np.mean(O, 0)
            out.append(f"| {t} | {c} | {s} | " + " / ".join(f"{mp[i]:+.1f}" for i in pick) + " | " + " / ".join(f"{mo[i]:.2f}" for i in pick) + " |")
t_ = "\n".join(out); print(t_); open(os.path.join(R, "e34_analysis.md"), "w").write(t_ + "\n")
fig, axs = plt.subplots(2, 4, figsize=(18, 7))
for row, t in enumerate(TASKS):
    for c, col in zip(CONDS, ("C3", "C0", "0.5")):
        for r in D[t, c]:
            f = [e for e in r["fine"] if e["step"] <= 100]; st = [e["step"] for e in f]
            for ax, k in zip(axs[row], ("stream", "open", "dbar", "own_closes")):
                ax.plot(st, [e.get(k, np.nan) if e.get(k) is not None else np.nan for e in f], color=col, lw=0.9, alpha=0.7, label=c if r is D[t, c][0] else None)
    for ax, k in zip(axs[row], ("last stream RMS", "gates open per example", "shared error |d̄|", "open gates closed by own update")):
        ax.set_title(f"{t}: {k}", fontsize=9); ax.set_xlabel("step")
    axs[row][0].set_yscale("log"); axs[row][0].legend(fontsize=8)
fig.tight_layout(); os.makedirs(FIG, exist_ok=True); fig.savefig(os.path.join(FIG, "e34_teardown.png"), dpi=110)
