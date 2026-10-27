"""Analysis for experiment 6, applying the rules fixed in E6_PREREGISTRATION.md."""
import json, glob, os
import numpy as np
from scipy.stats import spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
R = os.path.join(HERE, "..", "results")
FIG = os.path.join(HERE, "..", "figures")
LEVELS = [0.3, 0.1, 0.03, 0.01]
CONDS = ["circle-clean", "circle", "circle-noisier", "digits", "digits-5class", "digits-3class", "digits-2class", "digits-noisy"]
runs = [json.load(open(f)) for f in glob.glob(os.path.join(R, "e6", "*.json"))]
out = []


def at_loss(log, L):
    """T* at the first crossing of training loss below L, interpolated linearly in log-loss. None if never reached."""
    for a, b in zip(log, log[1:]):
        if a["train_loss"] >= L > b["train_loss"]:
            la, lb, lL = np.log(a["train_loss"]), np.log(b["train_loss"]), np.log(L)
            w = (la - lL) / (la - lb)
            return a["Tstar"] + w * (b["Tstar"] - a["Tstar"])
    if log[0]["train_loss"] < L:
        return log[0]["Tstar"]
    return None


def cell(cond, L):
    v = [at_loss(r["log"], L) for r in runs if r["condition"] == cond]
    v = np.array([x for x in v if x is not None])
    return v


def persists(a, b):
    if len(a) < 2 or len(b) < 2:
        return None, None
    d = a.mean() - b.mean(); thr = 2 * np.sqrt(a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2)
    return d, thr


# 1. within-run direction
neg = 0; rows = []
for r in sorted(runs, key=lambda r: (CONDS.index(r["condition"]), r["seed"])):
    T = [e["Tstar"] for e in r["log"]]; L = [np.log(e["train_loss"]) for e in r["log"]]
    rho = spearmanr(T, L).statistic
    neg += rho < 0; rows.append((r["condition"], r["seed"], rho))
out.append("## Within runs: does the tilt rise as training loss falls?\n")
out.append(f"Spearman correlation of T* with log training loss, per run. Negative = steeper as loss falls. "
           f"Pre-registered pass: negative in at least 20 of 24 runs. **Result: {neg} of {len(runs)}.**\n")
out.append("| condition | seed 0 | seed 1 | seed 2 |\n|---|---|---|---|")
for c in CONDS:
    v = {s: rho for cc, s, rho in rows if cc == c}
    out.append(f"| {c} | " + " | ".join(f"{v.get(s, float('nan')):+.2f}" for s in range(3)) + " |")

# 2. matched-loss table
out.append("\n## T* at matched training loss (mean ± sd over seeds; runs reaching that loss)\n")
out.append("| condition | classes | " + " | ".join(f"loss {L}" for L in LEVELS) + " | final loss |")
out.append("|---|---|" + "---|" * (len(LEVELS) + 1))
for c in CONDS:
    rs = [r for r in runs if r["condition"] == c]
    cells = []
    for L in LEVELS:
        v = cell(c, L)
        cells.append(f"{v.mean():+.2f} ± {v.std(ddof=1):.2f} ({len(v)})" if len(v) >= 2 else (f"{v[0]:+.2f} (1)" if len(v) == 1 else "not reached"))
    out.append(f"| {c} | {rs[0]['n_classes']} | " + " | ".join(cells) + f" | {np.mean([r['log'][-1]['train_loss'] for r in rs]):.4f} |")

# 3. H1 comparisons
out.append("\n## H1: do task differences persist at matched loss?\n")
out.append("Pre-registered: H1 fails if two or more of these comparisons persist at any level where both are present.\n")
out.append("| comparison | " + " | ".join(f"loss {L}" for L in LEVELS) + " | persists anywhere? |")
out.append("|---|" + "---|" * (len(LEVELS) + 1))
n_persist = 0
for a, b in [("circle-clean", "circle"), ("circle", "circle-noisier"), ("circle-clean", "circle-noisier"), ("digits-noisy", "digits")]:
    cells, any_p = [], False
    for L in LEVELS:
        d, thr = persists(cell(a, L), cell(b, L))
        if d is None:
            cells.append("–"); continue
        p = abs(d) > thr; any_p |= p
        cells.append(f"{d:+.2f} / {thr:.2f}" + (" **persists**" if p else ""))
    n_persist += any_p
    out.append(f"| {a} − {b} | " + " | ".join(cells) + f" | {'**yes**' if any_p else 'no'} |")
out.append(f"\n**{n_persist} of 4 comparisons persist. H1 {'fails' if n_persist >= 2 else 'holds'} by the pre-registered rule.**")

# 4. H2
out.append("\n## H2: does class count set the tilt at matched loss?\n")
out.append("| loss level | T* by classes (2, 3, 5, 10) | monotone 2 > 3 > 5 > 10? | 2 − 10 difference / threshold | persists? |")
out.append("|---|---|---|---|---|")
h2 = []
for L in LEVELS:
    m = {k: cell(c, L) for k, c in [(2, "digits-2class"), (3, "digits-3class"), (5, "digits-5class"), (10, "digits")]}
    if any(len(v) < 2 for v in m.values()):
        out.append(f"| {L} | some conditions did not reach this loss | – | – | – |"); continue
    means = [m[k].mean() for k in (2, 3, 5, 10)]
    mono = all(x > y for x, y in zip(means, means[1:]))
    d, thr = persists(m[2], m[10]); p = abs(d) > thr; h2.append(p)
    out.append(f"| {L} | " + ", ".join(f"{x:+.2f}" for x in means) + f" | {'yes' if mono else 'no'} | {d:+.2f} / {thr:.2f} | {'**yes**' if p else 'no'} |")
verdict = "holds at every level tested" if h2 and all(h2) else ("holds at some levels" if any(h2) else "fails")
out.append(f"\n**H2 {verdict}** (2-vs-10 difference persisting at {sum(h2)} of {len(h2)} levels where all four conditions reached the loss).")

text = "\n".join(out)
print(text)
open(os.path.join(R, "e6_analysis.md"), "w").write("# Experiment 6 results\n\n" + text + "\n")

# figure
fig, ax = plt.subplots(figsize=(7, 4.5))
for c in CONDS:
    for i, r in enumerate([r for r in runs if r["condition"] == c]):
        L = [e["train_loss"] for e in r["log"]]; T = [e["Tstar"] for e in r["log"]]
        ax.plot(L, T, lw=1, alpha=0.8, color=f"C{CONDS.index(c)}", label=c if i == 0 else None)
ax.set_xscale("log"); ax.invert_xaxis()
ax.set_xlabel("training loss (decreasing →)"); ax.set_ylabel("T* (α removed)")
ax.set_title("Tilt against training loss, every run"); ax.legend(fontsize=7, ncol=2)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "e6_tilt_vs_loss.png"), dpi=130); plt.close(fig)
