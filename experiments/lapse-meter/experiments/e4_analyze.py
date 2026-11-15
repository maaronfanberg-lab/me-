"""Analysis for experiment 4, using exactly the rule fixed in E4_PREREGISTRATION.md:
a condition 'moves' T* if |Δ| from its baseline exceeds 2 × sqrt(sd_condition² + sd_baseline²),
where sd is the standard deviation of T* over seeds; T* averaged over runs with test accuracy ≥ 0.70."""
import json, glob, os
import numpy as np

R = os.path.join(os.path.dirname(__file__), "..", "results", "e4")
CIRCLE = ["circle", "circle-clean", "circle-noisier", "circle-embed64", "circle-pad62noise", "circle-std1"]
DIGITS = ["digits", "digits-2class", "digits-pca2", "digits-noisy"]
runs = [json.load(open(f)) for f in glob.glob(os.path.join(R, "*.json"))]


def cell(cond, arch):
    rs = [r for r in runs if r["condition"] == cond and r["arch"] == arch]
    ok = [r for r in rs if r["log"][-1]["test_acc"] >= 0.70 and r["log"][-1]["Tstar"] is not None]
    T = np.array([r["log"][-1]["Tstar"] for r in ok])
    return dict(n=len(rs), ok=len(ok), T=T, mean=T.mean() if len(T) else np.nan, sd=T.std(ddof=1) if len(T) > 1 else np.nan,
                acc=np.mean([r["log"][-1]["test_acc"] for r in rs]) if rs else np.nan,
                loss=np.mean([r["log"][-1]["train_loss"] for r in ok]) if ok else np.nan,
                nin=rs[0]["n_inputs"] if rs else None, ncls=rs[0]["n_classes"] if rs else None)


out = []
for arch, label in [("res24", "residual tanh, 24 layers (α removed)"), ("plain12", "plain tanh, 12 layers")]:
    out.append(f"\n### {label}\n")
    out.append("| condition | inputs | classes | runs counted | test acc | final train loss | T* (mean ± sd) | Δ from baseline | moves? |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for group in (CIRCLE, DIGITS):
        base = cell(group[0], arch)
        for cond in group:
            c = cell(cond, arch)
            if cond == group[0]:
                d, mv = "baseline", ""
            elif c["ok"] < 2 or base["ok"] < 2:
                d, mv = "–", "too few runs"
            else:
                delta = c["mean"] - base["mean"]; thr = 2 * np.sqrt(c["sd"] ** 2 + base["sd"] ** 2)
                d, mv = f"{delta:+.2f} (threshold {thr:.2f})", "**yes**" if abs(delta) > thr else "no"
            out.append(f"| {cond} | {c['nin']} | {c['ncls']} | {c['ok']}/{c['n']} | {c['acc']:.3f} | {c['loss']:.3f} | "
                       f"{c['mean']:+.2f} ± {c['sd']:.2f} | {d} | {mv} |")
# does final training loss track T* across all counted runs?
pts = [(r["log"][-1]["train_loss"], r["log"][-1]["Tstar"], r["arch"]) for r in runs
       if r["log"][-1]["test_acc"] >= 0.70 and r["log"][-1]["Tstar"] is not None]
for arch in ("res24", "plain12"):
    p = np.array([(a, b) for a, b, c in pts if c == arch])
    if len(p) > 2:
        out.append(f"\nAcross all counted {arch} runs: correlation of T* with log(final train loss) r = "
                   f"{np.corrcoef(np.log(p[:, 0]), p[:, 1])[0, 1]:+.2f} (n = {len(p)})")
text = "\n".join(out)
print(text)
open(os.path.join(R, "..", "e4_analysis.md"), "w").write("# Experiment 4 results\n" + text + "\n")
