"""Analysis for experiments 13-16, applying the rules fixed in E13_16_PREREGISTRATION.md."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
from e9_12_analyze_lib import runs, vals, fmt, above, word, TASKS

out = ["# Experiments 13–16 results\n", "Primary measure: ln_transport at training loss 0.03.\n"]
res = {}
for task in TASKS:
    R96 = vals(runs("e8", f"{task}_relu_d96_s*.json")); R128 = vals(runs("e12", f"{task}_relu_d128_s*.json"))
    C = [("warm-up 50", "e13", "warmup50_d96", R96), ("warm-up 150", "e13", "warmup150_d96", R96),
         ("warm-up 500 (exp. 11)", "e11", "warmup_d96", R96), ("warm-up 1500", "e13", "warmup1500_d96", R96),
         ("warm-up 500, blocks only", "e14", "warmblocks_d96", R96), ("warm-up 500, output only", "e14", "warmout_d96", R96),
         ("signs q = 0.625", "e15", "q0.625_d96", R96), ("signs q = 0.75", "e15", "q0.75_d96", R96), ("signs q = 0.875", "e15", "q0.875_d96", R96),
         ("128 layers, warm-up 500", "e16", "warmup_d128", R128)]
    out.append(f"\n## {task}\n\nReferences: plain ReLU 96 = {fmt(*R96)}; plain ReLU 128 = {fmt(*R128)}\n")
    out.append("| condition | transport at loss 0.03 | rescued? (gap / threshold vs plain ReLU, same depth) | failed to train |")
    out.append("|---|---|---|---|")
    for name, exp, pat, ref in C:
        rs = runs(exp, f"{task}_{pat}_s*.json"); v, n = vals(rs)
        ok, gap, thr = above(v, ref[0]); res[(task, name)] = ok
        failed = sum(r["log"][-1]["train_loss"] > 0.5 * np.log(10 if task == "digits" else 2) for r in rs)
        out.append(f"| {name} | {fmt(v, n)} | {word(ok)}" + (f" ({gap:+.2f} / {thr:.2f})" if gap is not None else "") + f" | {failed} of {n} |")


def both(key, want=True):
    v = [res[(t, key)] for t in TASKS]
    return "untestable" if None in v else ("holds" if all(x == want for x in v) else "fails")


verdict = {"P13a": both("warm-up 1500"), "P13b": both("warm-up 50", False), "P14a": both("warm-up 500, blocks only"),
           "P14b": both("warm-up 500, output only", False), "P15a": both("signs q = 0.75"), "P15b": both("signs q = 0.625"),
           "P16": both("128 layers, warm-up 500")}
p13 = [res[(t, "warm-up 1500")] for t in TASKS]
hyp = ("supported" if all(verdict[k] == "holds" for k in ("P13a", "P14a", "P16"))
       else ("refuted" if all(x is False for x in p13) else "mixed"))
out.insert(2, "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in verdict.items()) + f". First-step-shock hypothesis: **{hyp}**.\n")
text = "\n".join(out); print(text); open(os.path.join(R, "e13_16_analysis.md"), "w").write(text + "\n")
