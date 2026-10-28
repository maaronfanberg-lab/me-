"""Analysis for experiments 17-20, applying the rules fixed in E17_20_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R, at_loss_key
from e9_12_analyze_lib import runs, fmt, above, word, TASKS


def vals_at(rs, L):
    v = [at_loss_key(r["log"], L, "ln_transport") for r in rs]
    return np.array([x for x in v if x is not None and np.isfinite(x)]), len(rs)


def failed(rs, task):
    return sum(r["log"][-1]["train_loss"] > 0.5 * np.log(10 if task == "digits" else 2) for r in rs)


out = ["# Experiments 17–20 results\n"]
res = {}
for task in TASKS:
    out.append(f"\n## {task}\n")
    # 17: two-matrix blocks
    R96 = vals_at(runs("e8", f"{task}_relu_d96_s*.json"), 0.03)
    t96r, t24r = runs("e17", f"{task}_two_d96_s*.json"), runs("e17", f"{task}_two_d24_s*.json")
    t96, t24 = vals_at(t96r, 0.03), vals_at(t24r, 0.03)
    ok, gap, thr = above(t96[0], R96[0]); res[(task, "P17a")] = ok
    drop, g2, th2 = above(t24[0], t96[0]); res[(task, "P17b")] = None if drop is None else not drop
    out.append("| experiment 17 | transport at loss 0.03 | failed to train |\n|---|---|---|")
    out.append(f"| plain one-matrix ReLU, 96 (exp. 8) | {fmt(*R96)} | – |")
    out.append(f"| two-matrix ReLU, 96 | {fmt(*t96)} | {failed(t96r, task)} of {len(t96r)} |")
    out.append(f"| two-matrix ReLU, 24 | {fmt(*t24)} | {failed(t24r, task)} of {len(t24r)} |")
    out.append(f"\nP17a (two-matrix 96 rescued): {word(ok)}" + (f" ({gap:+.2f} / {thr:.2f})" if gap is not None else "")
               + f". P17b (96 not below 24 by more than threshold): {word(res[(task, 'P17b')])}" + (f" (24 minus 96 = {g2:+.2f}, threshold {th2:.2f})" if g2 is not None else "") + ".")
    # 18: Adam; the lowest of loss 0.03, 0.1, 0.3 that both Adam ReLU groups reach in at least 2 runs (rule fixed in advance)
    a96r, a24r, at96r = runs("e18", f"{task}_adam_relu_d96_s*.json"), runs("e18", f"{task}_adam_relu_d24_s*.json"), runs("e18", f"{task}_adam_tanh_d96_s*.json")
    L18 = next((L for L in (0.03, 0.1, 0.3) if min(len(vals_at(a96r, L)[0]), len(vals_at(a24r, L)[0])) >= 2), 0.3)
    a96, a24, at96 = vals_at(a96r, L18), vals_at(a24r, L18), vals_at(at96r, L18)
    drop, g3, th3 = above(a24[0], a96[0]); res[(task, "P18")] = None if drop is None else not drop
    out.append(f"\n| experiment 18 (Adam, lr 0.001) | transport at loss {L18} | failed to train | starting → final output-layer weight norm |\n|---|---|---|---|")
    for name, rs, v in (("ReLU, 96", a96r, a96), ("ReLU, 24", a24r, a24), ("tanh, 96", at96r, at96)):
        wn = f"{np.mean([r['log'][0]['Wout'] for r in rs]):.1f} → {np.mean([r['log'][-1]['Wout'] for r in rs]):.1f}" if rs else "–"
        out.append(f"| {name} | {fmt(*v)} | {failed(rs, task)} of {len(rs)} | {wn} |")
    out.append(f"\nP18 (Adam ReLU 96 not below Adam ReLU 24 by more than threshold): {word(res[(task, 'P18')])}" + (f" (24 minus 96 = {g3:+.2f}, threshold {th3:.2f})" if g3 is not None else "") + ".")
    # 19: width 128
    p128r, s128r = runs("e19", f"{task}_plain_w128_d96_s*.json"), runs("e19", f"{task}_signed_w128_d96_s*.json")
    p128, s128 = vals_at(p128r, 0.03), vals_at(s128r, 0.03)
    ok, g4, th4 = above(s128[0], p128[0]); res[(task, "P19")] = ok
    out.append("\n| experiment 19 (width 128, 96 layers) | transport at loss 0.03 | failed to train |\n|---|---|---|")
    out.append(f"| plain ReLU | {fmt(*p128)} | {failed(p128r, task)} of {len(p128r)} |")
    out.append(f"| signed ReLU | {fmt(*s128)} | {failed(s128r, task)} of {len(s128r)} |")
    out.append(f"\nP19 (signed rescued against plain at width 128): {word(ok)}" + (f" ({g4:+.2f} / {th4:.2f})" if g4 is not None else "") + ".")


def both(key):
    v = [res[(t, key)] for t in TASKS]
    return "untestable" if None in v else ("holds" if all(v) else "fails")


verdict = {k: both(k) for k in ("P17a", "P17b", "P18", "P19")}
out.insert(1, "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in verdict.items()) + ".\n")

# 20: exploratory synthesis, does the break cost learning? Every 96-layer condition run so far, final state.
groups = [("plain ReLU", "e8", "relu_d96"), ("tanh", "e8", "tanh_d96"), ("signed ReLU", "e9", "signed_d96"),
          ("soft threshold", "e10", "shrink_d96"), ("tanh + 1", "e10", "tanhp1_d96"), ("warm-up 500", "e11", "warmup_d96"),
          ("zero output start", "e11", "zeroout_d96"), ("warm-up 50", "e13", "warmup50_d96"), ("warm-up 150", "e13", "warmup150_d96"),
          ("warm-up 1500", "e13", "warmup1500_d96"), ("warm-up, blocks only", "e14", "warmblocks_d96"), ("warm-up, output only", "e14", "warmout_d96"),
          ("signs q = 0.625", "e15", "q0.625_d96"), ("signs q = 0.75", "e15", "q0.75_d96"), ("signs q = 0.875", "e15", "q0.875_d96"),
          ("two-matrix ReLU", "e17", "two_d96")]
out.append("\n## Experiment 20 (exploratory): does losing transport cost learning?\n")
out.append("Every 96-layer, width-64, SGD condition, at step 6,000. Mean over seeds of both tasks pooled per task.\n")
out.append("| condition | transport at loss 0.03, digits / circle | final training loss, digits / circle | test accuracy, digits / circle |\n|---|---|---|---|")
pts = []
for name, exp, pat in groups:
    cells = [[], [], []]
    for task in TASKS:
        rs = runs(exp, f"{task}_{pat}_s*.json")
        if not rs: cells[0].append("–"); cells[1].append("–"); cells[2].append("–"); continue
        v, n = vals_at(rs, 0.03)
        cells[0].append(f"{v.mean():+.2f}" if len(v) else "–")
        fl = np.mean([r["log"][-1]["train_loss"] for r in rs]); ta = np.mean([r["test_acc"] for r in rs])
        cells[1].append(f"{fl:.4f}"); cells[2].append(f"{ta:.3f}")
        for r in rs:
            t = at_loss_key(r["log"], 0.03, "ln_transport")
            if t is not None and np.isfinite(t): pts.append((task, t, np.log(r["log"][-1]["train_loss"]), r["test_acc"]))
    out.append(f"| {name} | {' / '.join(cells[0])} | {' / '.join(cells[1])} | {' / '.join(cells[2])} |")
from scipy.stats import spearmanr
for task in TASKS:
    P = [p for p in pts if p[0] == task]
    if len(P) > 5:
        rl = spearmanr([p[1] for p in P], [p[2] for p in P]).statistic; ra = spearmanr([p[1] for p in P], [p[3] for p in P]).statistic
        out.append(f"\n{task}: across {len(P)} runs, Spearman correlation of transport with log final training loss {rl:+.2f}, with test accuracy {ra:+.2f}.")
text = "\n".join(out); print(text); open(os.path.join(R, "e17_20_analysis.md"), "w").write(text + "\n")
