"""Turn results/ into the README's tables and figures. Every number printed here comes from the JSON files."""
import json, glob, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = os.path.join(os.path.dirname(__file__), "..", "results")
FIG = os.path.join(os.path.dirname(__file__), "..", "figures")
os.makedirs(FIG, exist_ok=True)
DEPTHS = [3, 6, 12, 24, 48, 96]
ARCHS = ["plain-tanh", "plain-relu", "res-tanh", "res-relu"]
TRAINED = 0.8  # test accuracy that counts as "learned" on both tasks


def load_e1():
    rows = []
    for f in glob.glob(os.path.join(R, "e1", "*.json")):
        d = json.load(open(f)); c = d["cfg"]; name = os.path.basename(f).split("_")
        a, z = d["log"][0], d["log"][-1]
        rows.append(dict(task=c["task"], arch=name[1], depth=c["depth"], seed=c["seed"],
                         T0=a["tilt"], T=z["tilt"], k=z["kappa"], acc=z["test_acc"],
                         diverged="diverged_at" in d, lapse=z["lapse"], log=d["log"]))
    return rows


def e1(rows):
    print("\n## Experiment 1: total tilt T = ln N_first, by depth (mean over seeds; trained runs only for T_end)\n")
    out = {}
    for task in ["digits", "circle"]:
        print(f"### {task}\n")
        print("| architecture | " + " | ".join(f"depth {d}" for d in DEPTHS) + " |")
        print("|---|" + "---|" * len(DEPTHS))
        for arch in ARCHS:
            cells = []
            for dep in DEPTHS:
                rs = [r for r in rows if r["task"] == task and r["arch"] == arch and r["depth"] == dep]
                ok = [r for r in rs if (not r["diverged"]) and r["acc"] >= TRAINED and r["T"] is not None]
                out[(task, arch, dep)] = (rs, ok)
                if not rs:
                    cells.append("–"); continue
                if not ok:
                    cells.append(f"failed ({len(rs)})"); continue
                T = np.mean([r["T"] for r in ok]); T0 = np.mean([r["T0"] for r in ok])
                cells.append(f"{T0:+.1f} → **{T:+.2f}** ({len(ok)}/{len(rs)})")
            print(f"| {arch} | " + " | ".join(cells) + " |")
        print()
    # the law: regress T_end on depth for trained runs, per arch/task
    print("Fit over trained runs: T_end = a + b·depth (a law of conserved total tilt predicts b ≈ 0; a law of conserved per-layer slope predicts T_end ∝ depth)\n")
    print("| task | architecture | depths trained | a | b per layer | T_end spread (max−min of depth means) |")
    print("|---|---|---|---|---|---|")
    fits = {}
    for task in ["digits", "circle"]:
        for arch in ARCHS:
            pts = [(dep, r["T"]) for dep in DEPTHS for r in out[(task, arch, dep)][1]]
            deps = sorted(set(p[0] for p in pts))
            if len(deps) < 3:
                print(f"| {task} | {arch} | {deps} | – | – | – |"); continue
            x = np.array([p[0] for p in pts], float); yv = np.array([p[1] for p in pts])
            b, a = np.polyfit(x, yv, 1)
            means = [np.mean([p[1] for p in pts if p[0] == d]) for d in deps]
            fits[(task, arch)] = (deps, means)
            print(f"| {task} | {arch} | {deps} | {a:+.2f} | {b:+.4f} | {max(means)-min(means):.2f} |")
    # figure: T_end vs depth
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, task in zip(axs, ["digits", "circle"]):
        for arch in ARCHS:
            if (task, arch) in fits:
                deps, means = fits[(task, arch)]
                ax.plot(deps, means, marker="o", label=arch)
        ax.set_xscale("log"); ax.set_xticks(DEPTHS); ax.set_xticklabels(DEPTHS)
        ax.axhline(0, color="0.6", lw=0.8, ls="--")
        ax.set_title(f"{task}: total tilt after training"); ax.set_xlabel("hidden layers")
    axs[0].set_ylabel("T = ln(first-layer lapse)"); axs[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "e1_tilt_vs_depth.png"), dpi=130); plt.close(fig)
    # figure: final lapse profiles for res-tanh on digits at each depth
    fig, ax = plt.subplots(figsize=(6, 4))
    for dep in DEPTHS:
        ok = out[("digits", "res-tanh", dep)][1]
        if ok:
            prof = np.exp(np.mean([np.log(r["lapse"]) for r in ok], 0))
            ax.plot(np.linspace(0, 1, len(prof)), prof, label=f"{dep} layers")
    ax.set_yscale("log"); ax.axhline(1, color="0.6", lw=0.8, ls="--")
    ax.set_xlabel("position in depth (0 = first hidden, 1 = last)"); ax.set_ylabel("lapse N")
    ax.set_title("digits, residual tanh: trained lapse profiles"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "e1_profiles.png"), dpi=130); plt.close(fig)
    return out


def e1_corrected(rows):
    """Residual blocks carry the architectural factor alpha = 1/sqrt(depth); the output layer does not.
    T* = T - ln(alpha) removes it (exactly what lapse.nets.MLP.geometry_deltas(remove_alpha=True) does).
    For plain nets T* = T."""
    print("\n### Corrected total tilt T* (residual blocks' fixed α factor removed; plain nets unchanged)\n")
    for task in ["digits", "circle"]:
        print(f"**{task}**\n")
        print("| architecture | " + " | ".join(f"depth {d}" for d in DEPTHS) + " | spread over depths ≥ 12 |")
        print("|---|" + "---|" * (len(DEPTHS) + 1))
        for arch in ARCHS:
            cells, means = [], {}
            for dep in DEPTHS:
                ok = [r for r in rows if r["task"] == task and r["arch"] == arch and r["depth"] == dep
                      and not r["diverged"] and r["acc"] >= TRAINED and r["T"] is not None]
                if not ok:
                    cells.append("failed"); continue
                corr = 0.0 if arch.startswith("plain") else -np.log(1 / np.sqrt(dep))
                v = np.mean([r["T"] + corr for r in ok]); means[dep] = v
                cells.append(f"{v:+.2f}")
            deep = [means[d] for d in DEPTHS if d >= 12 and d in means]
            spread = f"{max(deep)-min(deep):.2f} over {len(deep)} depths" if len(deep) >= 2 else "–"
            print(f"| {arch} | " + " | ".join(cells) + f" | {spread} |")
        print()
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, task in zip(axs, ["digits", "circle"]):
        for arch in ARCHS:
            xs, ys = [], []
            for dep in DEPTHS:
                ok = [r for r in rows if r["task"] == task and r["arch"] == arch and r["depth"] == dep
                      and not r["diverged"] and r["acc"] >= TRAINED and r["T"] is not None]
                if ok:
                    corr = 0.0 if arch.startswith("plain") else -np.log(1 / np.sqrt(dep))
                    xs.append(dep); ys.append(np.mean([r["T"] + corr for r in ok]))
            ax.plot(xs, ys, marker="o", label=arch)
        ax.set_xscale("log"); ax.set_xticks(DEPTHS); ax.set_xticklabels(DEPTHS)
        ax.set_title(f"{task}: corrected total tilt T* after training"); ax.set_xlabel("hidden layers")
    axs[0].set_ylabel("T* = ln(first-layer lapse), α removed"); axs[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "e1_tilt_corrected.png"), dpi=130); plt.close(fig)


def e2_ranges():
    from lapse.nets import MLP
    from lapse import data as D
    cfgs = {"plain-tanh-0.8": dict(act="tanh", sigma_w=0.8, residual=False),
            "plain-tanh-1.0": dict(act="tanh", sigma_w=1.0, residual=False),
            "res-tanh": dict(act="tanh", sigma_w=1.0, residual=True)}
    print("\nRanges across layers (max/min), SGD runs. Motion under SGD is lr·‖δᵀh‖/‖W‖, so it should follow"
          " lapse × input activity; it follows the lapse alone only when activity is uniform.\n")
    print("| network | seed | lapse | input activity (at init) | lapse × activity / ‖W‖ | measured weight motion |")
    print("|---|---|---|---|---|---|")
    for name, c in cfgs.items():
        for s in range(3):
            f = os.path.join(R, "e2", f"{name}_sgd_s{s}.json")
            if not os.path.exists(f): continue
            d = json.load(open(f)); X, y, _, _ = D.digits(s)
            net = MLP(64, 64, 24, 10, seed=s, **c); h, _ = net.forward(X[:256])
            N = np.array(d["clock"]["lapse"]); k = len(N); m = np.array(d["clock"]["motion"])[:k]
            act = np.array([np.sqrt((h[i] ** 2).sum(1).mean()) for i in range(k)])
            Wn = np.array([np.linalg.norm(w) for w in net.W[:k]])
            rg = lambda v: v.max() / v.min()
            print(f"| {name} | {s} | ×{rg(N):.0f} | ×{rg(act):.1f} | ×{rg(N*act/Wn):.1f} | ×{rg(m):.1f} |")


def e2():
    print("\n## Experiment 2: does each layer's weight motion follow its lapse?\n")
    print("Per run: slope and correlation of log(relative weight motion per step) against log(lapse) across layers,"
          " averaged over the first 200 steps. A literal clock predicts slope ≈ 1 under SGD.\n")
    print("| network | optimiser | slope (mean ± sd over seeds) | correlation r | lapse range across layers |")
    print("|---|---|---|---|---|")
    res = {}
    for f in sorted(glob.glob(os.path.join(R, "e2", "*.json"))):
        d = json.load(open(f)); name = os.path.basename(f).rsplit("_", 2)
        if "clock" not in d: continue
        m = np.array(d["clock"]["motion"]); N = np.array(d["clock"]["lapse"])
        # layers 0..L-2 are hidden (lapse_profile excluded the output); motion has one entry per weight matrix
        m = m[:len(N)]
        x, yv = np.log(N), np.log(m)
        b = np.polyfit(x, yv, 1)[0]; r = np.corrcoef(x, yv)[0, 1]
        res.setdefault((name[0], name[1]), []).append((b, r, N.max() / N.min()))
    for (net, opt), v in res.items():
        v = np.array(v)
        print(f"| {net} | {opt} | {v[:,0].mean():.2f} ± {v[:,0].std():.2f} | {v[:,1].mean():.2f} | ×{np.exp(np.mean(np.log(v[:,2]))):.3g} |")
    return res


def e3():
    files = sorted(glob.glob(os.path.join(R, "lm", "*.json")))
    if not files:
        print("\n(no language-model results)"); return
    print("\n## Experiment 3: tiny character-level language model\n")
    print("| model | optimiser | seed | test bits/char start → end | unigram baseline | first layer hears (start → end) | κ end | horizons at end |")
    print("|---|---|---|---|---|---|---|---|")
    fig, ax = plt.subplots(figsize=(6, 4))
    for f in files:
        d = json.load(open(f)); a, z = d["log"][0], d["log"][-1]
        hz = sum(1 for v in z["lapse"] if not v >= 1e-2)
        corr = 0.5 * np.log(24) if d["residual"] else 0.0   # T* = T - ln(alpha), alpha = 1/sqrt(24)
        print(f"| {'residual' if d['residual'] else 'plain'} | {d['opt']} | {d['seed']} | {a['test_loss_bits']:.2f} → {z['test_loss_bits']:.2f} | {d['unigram_bits']:.2f} | "
              f"×{np.exp(a['tilt']):.3g} → ×{np.exp(z['tilt']):.3g} (T* {z['tilt']+corr:+.2f}) | {z['kappa']:+.4f} | {hz}/{len(z['lapse'])} |")
        ax.plot(z["lapse"], label=f"{'res' if d['residual'] else 'plain'} {d['opt']} s{d['seed']}")
    ax.set_yscale("log"); ax.axhline(1, color="0.6", ls="--", lw=0.8); ax.axhline(1e-2, color="0.8", ls=":", lw=0.8)
    ax.set_xlabel("hidden layer (input side → output side)"); ax.set_ylabel("lapse N after training")
    ax.set_title("tiny language model: where the error reaches"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "e3_lm_lapse.png"), dpi=130); plt.close(fig)
    for f in files:
        d = json.load(open(f))
        print(f"\nSample, {'residual' if d['residual'] else 'plain'} {d['opt']} seed {d['seed']}:\n\n> {d['sample']}")


def sounds():
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "audio", "*.wav.json")))
    if not files: return
    from lapse.sound import pitch_of
    print("\n## Sound pieces\n")
    print("| piece | network | audio | first layer lapse start → end | its pitch start → end | test accuracy start → end |")
    print("|---|---|---|---|---|---|")
    for f in files:
        d = json.load(open(f)); H = np.array(d["lapse"]); c = d["cfg"]
        print(f"| {d['piece']} | {c['depth']}-layer {'residual' if c['residual'] else 'plain'} {c['act']}, σw {c['sigma_w']} | {len(H)*0.12:.0f} s | "
              f"{H[0,0]:.2e} → {H[-1,0]:.2e} | {pitch_of(H[0,0]):.1f} → {pitch_of(H[-1,0]):.1f} Hz | {d['test_acc'][0]:.2f} → {d['test_acc'][-1]:.2f} |")
        fig, ax = plt.subplots(figsize=(6, 3.2))
        im = ax.imshow(np.log10(H.T), aspect="auto", origin="lower", cmap="magma", vmin=-6, vmax=1,
                       extent=[0, len(H) * c["every"], 0, H.shape[1]])
        ax.set_xlabel("training step"); ax.set_ylabel("layer"); ax.set_title(f"{d['piece']}: log10 lapse (what you hear)")
        fig.colorbar(im, ax=ax, label="log10 N  (each unit = one octave)")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, f"sound_{d['piece']}.png"), dpi=130); plt.close(fig)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    rows = load_e1()
    print(f"loaded {len(rows)} experiment-1 runs")
    e1(rows); e1_corrected(rows); e2(); e2_ranges(); e3(); sounds()
