"""Analysis for experiment 7, applying the rules fixed in E7_PREREGISTRATION.md."""
import json, glob, os, sys, itertools
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
R = os.path.join(HERE, "..", "results"); FIG = os.path.join(HERE, "..", "figures")


def at_loss(log, L):
    """Same rule as experiment 6: T* at the first crossing of training loss below L, linear in log-loss."""
    for a, b in zip(log, log[1:]):
        if a["train_loss"] >= L > b["train_loss"] and np.isfinite(b["train_loss"]):
            w = (np.log(a["train_loss"]) - np.log(L)) / (np.log(a["train_loss"]) - np.log(b["train_loss"]))
            return a["Tstar"] + w * (b["Tstar"] - a["Tstar"])
    if log[0]["train_loss"] < L:
        return log[0]["Tstar"]
    return None


LEVELS = [0.3, 0.1, 0.03, 0.01]; DEPTHS = [6, 12, 24, 48, 96]; TEST = [12, 24, 48, 96]
runs = [json.load(open(f)) for f in glob.glob(os.path.join(R, "e7", "*.json"))]
out = []


def cell(task, act, depth, L):
    v = [at_loss(r["log"], L) for r in runs if r["task"] == task and r["act"] == act and r["depth"] == depth]
    return np.array([x for x in v if x is not None and np.isfinite(x)]), sum(1 for r in runs if r["task"] == task and r["act"] == act and r["depth"] == depth)


verdicts = {}
for act in ["tanh", "relu"]:
    tag = "confirmatory" if act == "tanh" else "exploratory, no prediction"
    for task in ["digits", "circle-clean"]:
        out.append(f"\n### Residual {act}, {task} ({tag})\n")
        out.append("| loss level | " + " | ".join(f"depth {d}" for d in DEPTHS) + " | largest pair gap / its threshold (12–96) | slope of T* per doubling of depth (12–96) |")
        out.append("|---|" + "---|" * (len(DEPTHS) + 2))
        task_ok = True; any_level = False
        for L in LEVELS:
            cells, stats = [], {}
            for d in DEPTHS:
                v, n = cell(task, act, d, L)
                cells.append(f"{v.mean():+.2f} ± {v.std(ddof=1):.2f} ({len(v)}/{n})" if len(v) >= 2 else (f"{len(v)}/{n} reached"))
                if len(v) >= 2: stats[d] = v
            if all(d in stats for d in TEST):
                any_level = True
                worst = max(((abs(stats[a].mean() - stats[b].mean()), 2 * np.sqrt(stats[a].std(ddof=1) ** 2 + stats[b].std(ddof=1) ** 2), a, b)
                             for a, b in itertools.combinations(TEST, 2)), key=lambda t: t[0] - t[1])
                gap, thr, a, b = worst; exceeds = gap > thr; task_ok &= not exceeds
                xs = np.concatenate([[np.log2(d)] * len(stats[d]) for d in TEST]); ys = np.concatenate([stats[d] for d in TEST])
                slope = np.polyfit(xs, ys, 1)[0]
                pair = f"{gap:.2f} / {thr:.2f} (depths {a} vs {b})" + (" **exceeds**" if exceeds else "")
                out.append(f"| {L} | " + " | ".join(cells) + f" | {pair} | {slope:+.3f} |")
            else:
                out.append(f"| {L} | " + " | ".join(cells) + " | not all depths reached this loss | – |")
        if act == "tanh":
            verdicts[task] = ("holds" if task_ok else "fails") if any_level else "untestable"
            out.append(f"\n**Prediction {verdicts[task]} for {task}.**")
out.insert(0, "Pre-registered test (tanh): no pair of depths 12–96 differs by more than 2 × combined seed spread at any loss level. "
              + "Verdicts: " + ", ".join(f"{k}: **{v}**" for k, v in verdicts.items()) + ".")
text = "\n".join(out); print(text)
open(os.path.join(R, "e7_analysis.md"), "w").write("# Experiment 7 results\n\n" + text + "\n")

fig, axs = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
for i, act in enumerate(["tanh", "relu"]):
    for j, task in enumerate(["digits", "circle-clean"]):
        ax = axs[i][j]
        for k, d in enumerate(DEPTHS):
            for n, r in enumerate([r for r in runs if r["task"] == task and r["act"] == act and r["depth"] == d]):
                L = [e["train_loss"] for e in r["log"]]; T = [e["Tstar"] for e in r["log"]]
                ax.plot(L, T, color=f"C{k}", lw=1, alpha=0.8, label=f"{d} layers" if n == 0 else None)
        ax.set_xscale("log"); ax.set_title(f"residual {act}, {task}"); ax.set_ylabel("T*")
        if i == 1: ax.set_xlabel("training loss")
axs[0][0].invert_xaxis(); axs[0][0].legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "e7_depth_at_matched_loss.png"), dpi=130); plt.close(fig)
