"""Recompute the README's headline numbers from the raw result files and check the README states exactly them.
Catches stale or hand-copied numbers (CORRECTIONS 11). Run: python tests/test_readme_numbers.py"""
import sys, os, json, glob, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
R = os.path.join(ROOT, "results")
import numpy as np
README = open(os.environ.get("LAPSE_README", os.path.join(ROOT, "README.md"))).read()  # override to test an older README
RESULTS = []


def claim(name, text):
    ok = text in README
    RESULTS.append(ok); print(("PASS " if ok else "FAIL ") + f"{name}: README should contain '{text}'")


def e1_Tstar(task, arch, depth):
    v = []
    for f in glob.glob(os.path.join(R, "e1", f"{task}_{arch}_d{depth}_s*.json")):
        d = json.load(open(f)); z = d["log"][-1]
        if "diverged_at" in d or z["test_acc"] < 0.8 or z["tilt"] is None: continue
        v.append(z["tilt"] + (0.5 * np.log(depth) if arch.startswith("res") else 0.0))
    return np.mean(v)


# Experiment 1: corrected tilt, residual tanh
for task in ("digits", "circle"):
    vals = " | ".join(f"{e1_Tstar(task, 'res-tanh', d):+.2f}" for d in (12, 24, 48, 96))
    claim(f"E1 {task} residual tanh T* at 12/24/48/96", vals)

# Experiment 2: clock slopes (log motion vs log lapse, SGD)
def e2_slope(name):
    b = []
    for f in glob.glob(os.path.join(R, "e2", f"{name}_sgd_s*.json")):
        d = json.load(open(f)); N = np.array(d["clock"]["lapse"]); m = np.array(d["clock"]["motion"])[:len(N)]
        b.append(np.polyfit(np.log(N), np.log(m), 1)[0])
    return np.mean(b)
claim("E2 residual slope", f"**{e2_slope('res-tanh'):.2f}**")
claim("E2 plain 1.0 slope", f"| {e2_slope('plain-tanh-1.0'):.2f} (r =")
claim("E2 plain 0.8 slope", f"| {e2_slope('plain-tanh-0.8'):.2f} |")

# Experiment 5 part 3: one-time-base spreads for the sigma_w = 0.8 network
p3 = json.load(open(os.path.join(R, "e5_alignment.json")))["part3"]
s08 = [r for r in p3 if r["net"] == "plain-tanh-0.8"]
claim("E5 lapse spread sigma 0.8", f"×{min(r['lapse'] for r in s08):.0f}–{max(r['lapse'] for r in s08):.0f}")
claim("E5 activity spread sigma 0.8", f"×{min(r['act'] for r in s08):.0f}–{max(r['act'] for r in s08):.0f}")

# Experiment 3: language-model losses
for f, label in [("res_adam_s0", "residual adam s0"), ("res_adam_s1", "residual adam s1"), ("res_sgd_s0", "residual sgd")]:
    d = json.load(open(os.path.join(R, "lm", f + ".json")))
    claim(f"E3 {label} final bits/char", f"→ **{d['log'][-1]['test_loss_bits']:.2f}**")
d = json.load(open(os.path.join(R, "lm", "plain_adam_s0.json")))
claim("E3 plain final bits/char", f"6.36 → {d['log'][-1]['test_loss_bits']:.2f}")
claim("E3 unigram baseline", f"{d['unigram_bits']:.2f} bits per character")

# Experiment 4: class-count effect, residual
def e4_T(cond):
    v = [json.load(open(f))["log"][-1] for f in glob.glob(os.path.join(R, "e4", f"{cond}_res24_s*.json"))]
    return np.mean([z["Tstar"] for z in v if z["test_acc"] >= 0.7])
claim("E4 digits 2-class shift", f"**{e4_T('digits-2class') - e4_T('digits'):+.2f}, moves**")

# Experiment 6: within-run count and class ordering at loss 0.01
sys.path.insert(0, os.path.join(ROOT, "experiments"))
from scipy.stats import spearmanr
runs = [json.load(open(f)) for f in glob.glob(os.path.join(R, "e6", "*.json"))]
neg = sum(spearmanr([e["Tstar"] for e in r["log"]], [np.log(e["train_loss"]) for e in r["log"]]).statistic < 0 for r in runs)
claim("E6 within-run count", f"{neg} of {len(runs)}")
def at_loss(log, L):
    for a, b in zip(log, log[1:]):
        if a["train_loss"] >= L > b["train_loss"]:
            w = (np.log(a["train_loss"]) - np.log(L)) / (np.log(a["train_loss"]) - np.log(b["train_loss"]))
            return a["Tstar"] + w * (b["Tstar"] - a["Tstar"])
order = [np.mean([at_loss(r["log"], 0.01) for r in runs if r["condition"] == c])
         for c in ("digits-2class", "digits-3class", "digits-5class", "digits")]
claim("E6 class ordering at loss 0.01", ", ".join(f"{v:+.2f}" for v in order) + " at 0.01")

# Experiment 7: residual tanh tilt at loss 0.01, depths 12-96
r7 = [json.load(open(f)) for f in glob.glob(os.path.join(R, "e7", "*.json"))]
for task, label in (("digits", "digits"), ("circle-clean", "circle (clean)")):
    vals = []
    for dep in (12, 24, 48, 96):
        v = [at_loss(r["log"], 0.01) for r in r7 if r["task"] == task and r["act"] == "tanh" and r["depth"] == dep]
        vals.append(np.mean([x for x in v if x is not None]))
    claim(f"E7 {task} tanh at loss 0.01", f"| {label} | " + " | ".join(f"{x:+.2f}" for x in vals) + " |")
# Experiments 8-12: transport at loss 0.03 (README section 8)
import warnings; warnings.filterwarnings("ignore")
from e9_12_analyze_lib import runs as r812, vals as v812
def tr(exp, pat):
    return "  ".join(f"{v812(r812(exp, f'{t}_{pat}_s*.json'))[0].mean():+.2f}" for t in ("digits", "circle-clean")).split("  ")
for label, exp, pat in (("plain ReLU (reference)", "e8", "relu_d96"), ("tanh (reference)", "e8", "tanh_d96"),
                        ("so outputs don't stack", "e9", "signed_d96"), ("but outputs centred on zero", "e10", "shrink_d96"),
                        ("500-step learning-rate warm-up", "e11", "warmup_d96")):
    d, c = tr(exp, pat)
    claim(f"E9-12 {label}", f"{label} | {d} | {c} |")
from e8_analyze import load as l8, summary as s8
S8 = s8(l8("e8"), 0.03)
for task, act, label in (("digits", "relu", "ReLU, digits"), ("circle-clean", "relu", "ReLU, circle")):
    row = S8[(task, act, 96)]
    claim(f"E8 split {label}", f"| {label} | {row['Tstar'][0]:+.2f} | {row['ln_out'][0]:+.2f} | **{row['ln_transport'][0]:+.2f}** | **{row['ln_gate'][0]:+.2f}** |".replace("-", "−"))
# Experiments 13-16 (README section 9)
for label, exp, pat in (("warm-up over 50 steps", "e13", "warmup50_d96"), ("warm-up over 1,500 steps", "e13", "warmup1500_d96"),
                        ("warm-up of the output layer only", "e14", "warmout_d96"), ("sign odds q = 0.75 (6× pile-up)", "e15", "q0.75_d96"),
                        ("sign odds q = 0.875 (15× pile-up)", "e15", "q0.875_d96")):
    d, c = tr(exp, pat)
    claim(f"E13-16 {label}", f"{label} | {d} | {c} |")
c = f"{v812(r812('e14', 'circle-clean_warmblocks_d96_s*.json'))[0].mean():+.2f}"
claim("E14 blocks-only circle", f"1 of 3 never trained | {c} |")
claim("E16 digits 128", f"(+{v812(r812('e16', 'digits_warmup_d128_s*.json'))[0].mean():.2f} against +{v812(r812('e12', 'digits_relu_d128_s*.json'))[0].mean():.2f})")
# Experiments 17-20 (README section 10)
for label, exp, pat in (("as in ResNets and transformers", "e17", "two_d96"), ("(lr 0.001), plain one-matrix ReLU", "e18", "adam_relu_d96"),
                        ("plain one-matrix ReLU, SGD", "e19", "plain_w128_d96"), ("width 128: signed ReLU", "e19", "signed_w128_d96")):
    d, c = tr(exp, pat)
    claim(f"E17-19 {label}", f"{label} | {d} | {c} |")
pr = r812("e8", "digits_relu_d96_s*.json")
claim("E20 digits plain final loss and accuracy", f"final training loss of {np.mean([r['log'][-1]['train_loss'] for r in pr]):.4f} and {100*np.mean([r['test_acc'] for r in pr]):.1f}% test")
an = open(os.path.join(R, "e17_20_analysis.md")).read()
m = re.search(r"digits: across (\d+) runs, Spearman correlation of transport with log final training loss ([+-]\d\.\d\d), with test accuracy ([+-]\d\.\d\d)", an)
claim("E20 digits correlations", f"Across {m.group(1)} digits runs, transport correlates with\nfinal log training loss at {m.group(2).replace('-', '−')} and with test accuracy at {m.group(3)}")
# Experiment 21 (README section 11)
for label, exp, pat in (("SGD, lr 0.05 (reference)", "e8", "tanh_d24"), ("Adam (normalization + momentum)", "e21", "adam"),
                        ("RMSprop (normalization only)", "e21", "rmsprop"), ("momentum SGD (momentum only)", "e21", "momentum")):
    d, c = tr(exp, pat)
    claim(f"E21 {label}", f"{label} | {d} | {c} |")
# shock pieces: median of the per-log largest jump, in semitones
for name, val in (("shock", "2.75"), ("shock_warmup", "0.31")):
    H = np.log10(np.array(json.load(open(os.path.join(ROOT, "audio", name + ".wav.json")))["lapse"]))
    claim(f"sound {name} median jump", f"{np.median(np.abs(np.diff(H, axis=0)).max(1) * 12):.2f}")
# Experiments 22-23 (README section 12)
from sklearn.metrics import roc_auc_score
P22 = json.load(open(os.path.join(R, "e22_predictors.json")))
for key, label in (("kick", "readout kick (logit change from one SGD step on the readout; μP's argument)"), ("sharp", "preconditioned sharpness (Gilmer 2022; Kalra & Barkeshli 2024)"), ("stream_growth", "pile-up ratio")):
    aucs = []
    for task in ("digits", "circle-clean"):
        rs = [r for r in P22.values() if r["config"]["task"] == task]
        yb = [int(r["transport"] is None or r["failed"] or r["transport"] < 0.3) for r in rs]
        aucs.append(f"{roc_auc_score(yb, [r[key] for r in rs]):.2f}")
    claim(f"E22 AUC {key}", f"| {label} | {aucs[0]} | {aucs[1]} |")
e23 = open(os.path.join(R, "e23_analysis.md")).read()
m = re.search(r"kick (\d+) of (\d+), sharpness (\d+) of \d+, pile-up ratio (\d+) of", e23)
claim("E23 kick score", f"for kick in {m.group(1)} of {m.group(2)} runs, for sharpness in {m.group(3)} of {m.group(2)}, and for the pile-up ratio in\n{m.group(4)} of {m.group(2)}")
ind = open(os.path.join(ROOT, "independent", "results.md")).read()
claim("independent replication 7 of 8", "Of 8 predictions, 7\nheld") if ind.count("**holds**") == 7 and ind.count("**fails**") == 1 else claim("independent replication count", "MISMATCH")
# kick bands over all 198 runs (180 earlier + 18 from experiment 23)
from e8_analyze import at_loss_key as _alk
pts = [(r["kick"], r["transport"] is None or r["failed"] or r["transport"] < 0.3) for r in P22.values()]
for p in json.load(open(os.path.join(ROOT, "experiments", "e23_predictions.json"))):
    rr = json.load(open(os.path.join(ROOT, p["run"]))); K = 10 if p["task"] == "digits" else 2
    lv = next((L for L in (0.03, 0.1, 0.3) if _alk(rr["log"], L, "ln_transport") is not None), None)
    tt = _alk(rr["log"], lv, "ln_transport") if lv else None
    pts.append((p["kick"], rr["log"][-1]["train_loss"] > 0.5 * np.log(K) or tt is None or tt < 0.3))
band = lambda lo, hi: (sum(1 for k, b in pts if lo <= k < hi), sum(1 for k, b in pts if lo <= k < hi and b))
(n1, b1), (n2, b2), (n3, b3) = band(0, 100), band(100, 500), band(500, 1e12)
claim("kick bands", f"Below 100, none of {n1} runs lost transport; between 100 and 500, {b2} of\n  {n2} did; above 500, {b3} of {n3}." if b1 == 0 else "MISMATCH")
# Experiments 24-26 (README section 13), recomputed from the analysis files the pre-registered scripts wrote
e24 = open(os.path.join(R, "e24_analysis.md")).read()
m = re.search(r"Per-run rule right in (\d+) of (\d+) runs", e24); claim("E24 per-run rule", f"right in {m.group(1)} of {m.group(2)} runs")
e26 = open(os.path.join(R, "e26_analysis.md")).read()
m = re.search(r"\| digits \| final \| 0.03 \| ([+-]\d\.\d\d) ± [\d.]+ \(3/3\) \| ([+-]\d\.\d\d)", e26)
claim("E26 final-LN digits ReLU vs twin", f"(digits {m.group(1)} against {m.group(2)})")
e25 = open(os.path.join(R, "e25_analysis.md")).read()
def e25cell(task, cond, col):
    blk = e25.split(f"## {task}")[1]; row = next(l for l in blk.splitlines() if l.startswith(f"| {cond} |"))
    return row.split("|")[col].strip()
sw = lambda task, cond: float(e25cell(task, cond, 5).split("→")[1])
claim("E25 share_W", f"{sw('digits','plain')*100:.0f}% (digits) and {sw('circle-clean','plain')*100:.0f}% (circle) of their\n  energy, against {sw('digits','cap10')*100:.1f}% and {sw('circle-clean','cap10')*100:.0f}% when")
f1 = lambda task, cond: float(e25cell(task, cond, 7).split()[0])
claim("E25 gate flips", f"({f1('circle-clean','plain')*100:.0f}–{f1('digits','plain')*100:.0f}%), against {f1('digits','cap10')*100:.0f}% when capped")
# Experiment 28 (README section 14), from the pre-registered analysis's own table
e28 = open(os.path.join(R, "e28_analysis.md")).read()
def e28row(key):
    row = next(l for l in e28.splitlines() if l.startswith(f"| {key} |")).split("|")
    return row[5].split()[0].strip(), row[6].split()[0].strip(), [float(x) for x in row[9].split("/")]
for key, label in (("P28a", "ReLU, inputs ×1"), ("P28c", "ReLU ×10, kick capped at 10"), ("P28d", "ReLU ×10, final LayerNorm")):
    a, b, (fa, fb) = e28row(key)
    fmt2 = lambda v: f"{v:.3f}" if v < 0.1 else f"{v:.2f}"
    claim(f"E28 {key}", f"| {a} / {b} | {fmt2(fa)} / {fmt2(fb)} |")
print(f"{sum(RESULTS)}/{len(RESULTS)} README numbers match the raw results")
sys.exit(0 if all(RESULTS) else 1)
