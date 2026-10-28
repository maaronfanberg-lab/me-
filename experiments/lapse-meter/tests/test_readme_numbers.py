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
print(f"{sum(RESULTS)}/{len(RESULTS)} README numbers match the raw results")
sys.exit(0 if all(RESULTS) else 1)
