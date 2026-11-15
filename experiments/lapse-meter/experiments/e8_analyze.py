"""Analysis for experiment 8 (exploratory): which part of T* moves with depth, for tanh and ReLU.
Also used by later experiments: `at_loss_key` and `load`."""
import json, glob, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "results"); FIG = os.path.join(HERE, "..", "figures")
PARTS = ["Tstar", "ln_out", "ln_transport", "ln_gate"]


def at_loss_key(log, L, key):
    """Value of `key` at the first crossing of training loss below L, linear in log-loss (rule of experiments 6-7)."""
    for a, b in zip(log, log[1:]):
        if a["train_loss"] >= L > b["train_loss"] and np.isfinite(b["train_loss"]):
            w = (np.log(a["train_loss"]) - np.log(L)) / (np.log(a["train_loss"]) - np.log(b["train_loss"]))
            return a[key] + w * (b[key] - a[key])
    if log[0]["train_loss"] < L:
        return log[0][key]
    return None


def load(name):
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(R, name, "*.json")))]


def summary(runs, L=0.01, group=("task", "act", "depth")):
    """Mean ± sd of each part at loss L, grouped by config keys. Returns {group tuple: {part: (mean, sd, n)}}."""
    out = {}
    for r in runs:
        k = tuple(r["config"][g] for g in group)
        out.setdefault(k, []).append(r)
    res = {}
    for k, rs in sorted(out.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        row = {}
        for p in PARTS + ["final_" + q for q in PARTS]:
            if p.startswith("final_"):
                v = [r["log"][-1][p[6:]] for r in rs]
            else:
                v = [at_loss_key(r["log"], L, p) for r in rs]
            v = np.array([x for x in v if x is not None])
            row[p] = (v.mean() if len(v) else np.nan, v.std(ddof=1) if len(v) > 1 else np.nan, len(v), len(rs))
        res[k] = row
    return res


if __name__ == "__main__":
    runs = load("e8")
    lines = ["# Experiment 8 results (exploratory)\n",
             "Each cell: mean ± sd over seeds (runs reaching the loss level / runs). T* = out + transport + gate exactly.\n"]
    for L in (0.1, 0.01, "final"):
        lines.append(f"\n## {'At the end of training (step 6000)' if L == 'final' else f'At training loss {L}'}\n")
        lines.append("| task | act | depth | T* | out | transport | gate |")
        lines.append("|---|---|---|---|---|---|---|")
        S = summary(runs, 0.01 if L == "final" else L)
        for (task, act, depth), row in sorted(S.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
            pre = "final_" if L == "final" else ""
            cells = [f"{row[pre + p][0]:+.2f} ± {row[pre + p][1]:.2f}" for p in PARTS]
            lines.append(f"| {task} | {act} | {depth} | " + " | ".join(cells) + f" ({row[pre + 'Tstar'][2]}/{row[pre + 'Tstar'][3]}) |")
    # per-layer picture at the end of training, depth 96
    fig, axs = plt.subplots(2, 4, figsize=(15, 6.5))
    keys = [("stream_grad", "ln RMS stream gradient (vs output delta)"), ("gate", "ln gate factor"),
            ("density", "fraction of gates open"), ("stream_norm", "RMS stream size")]
    for i, task in enumerate(["digits", "circle-clean"]):
        for j, (k, lab) in enumerate(keys):
            ax = axs[i][j]
            for act, col in (("tanh", "C0"), ("relu", "C3")):
                for r in runs:
                    c = r["config"]
                    if c["task"] == task and c["act"] == act and c["depth"] == 96:
                        e = [x for x in r["log"] if k in x][-1]
                        ax.plot(np.arange(1, len(e[k]) + 1), e[k], color=col, lw=1, alpha=0.8,
                                label=act if c["seed"] == 0 else None)
            ax.set_title(f"{task}: {lab}", fontsize=9); ax.set_xlabel("block")
            if k == "stream_norm": ax.set_yscale("log")
    axs[0][0].legend(fontsize=8); fig.tight_layout()
    os.makedirs(FIG, exist_ok=True); fig.savefig(os.path.join(FIG, "e8_layers_d96.png"), dpi=120); plt.close(fig)
    # parts through training, depth 96
    fig, axs = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for i, act in enumerate(["tanh", "relu"]):
        for j, task in enumerate(["digits", "circle-clean"]):
            ax = axs[i][j]
            for r in runs:
                c = r["config"]
                if c["task"] == task and c["act"] == act and c["depth"] == 96:
                    st = [e["step"] for e in r["log"]]
                    for p, col in zip(PARTS, ["k", "C1", "C2", "C4"]):
                        ax.plot(st, [e[p] for e in r["log"]], color=col, lw=1, alpha=0.7, label=p if c["seed"] == 0 else None)
            ax.set_title(f"residual {act}, {task}, 96 layers", fontsize=10); ax.axhline(0, color="0.7", lw=0.5)
    axs[0][0].legend(fontsize=8); axs[1][0].set_xlabel("step"); axs[1][1].set_xlabel("step"); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "e8_parts_d96.png"), dpi=120); plt.close(fig)
    text = "\n".join(lines); print(text)
    open(os.path.join(R, "e8_analysis.md"), "w").write(text + "\n")
