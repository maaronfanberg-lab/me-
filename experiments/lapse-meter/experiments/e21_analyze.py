"""Analysis for experiment 21, applying the rules fixed in E21_PREREGISTRATION.md."""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import R
from e9_12_analyze_lib import runs, vals, fmt, above, word, TASKS

out = ["# Experiment 21 results\n", "Residual tanh, 24 layers. Transport at training loss 0.03.\n"]
res = {}
for task in TASKS:
    ref = vals(runs("e8", f"{task}_tanh_d24_s*.json"))
    out.append(f"\n## {task}\n\nSGD, lr 0.05 (experiment 8): {fmt(*ref)}\n")
    out.append("| optimizer | transport at loss 0.03 | above SGD? (gap / threshold) | failed to train |\n|---|---|---|---|")
    for name, pat in (("Adam, lr 0.001", "adam"), ("RMSprop, lr 0.001", "rmsprop"), ("momentum SGD, lr 0.005", "momentum"),
                      ("SGD, lr 0.02", "sgd0.02"), ("SGD, lr 0.1", "sgd0.1")):
        rs = runs("e21", f"{task}_{pat}_s*.json"); v, n = vals(rs)
        ok, gap, thr = above(v, ref[0]); res[(task, pat)] = ok
        fail = sum(r["log"][-1]["train_loss"] > 0.5 * np.log(10 if task == "digits" else 2) for r in rs)
        out.append(f"| {name} | {fmt(v, n)} | {word(ok)}" + (f" ({gap:+.2f} / {thr:.2f})" if gap is not None else "") + f" | {fail} of {n} |")


def both(key, want=True):
    v = [res[(t, key)] for t in TASKS]
    return "untestable" if None in v else ("holds" if all(x == want for x in v) else "fails")


V = {"P21a": both("adam"), "P21b": both("rmsprop"), "P21c": both("momentum", False)}
p21b = [res[(t, "rmsprop")] for t in TASKS]
hyp = "supported" if V["P21b"] == "holds" and V["P21c"] == "holds" else ("refuted" if all(x is False for x in p21b) else "mixed")
out.insert(2, "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in V.items()) + f". H21 (normalization, not momentum): **{hyp}**.\n")
text = "\n".join(out); print(text); open(os.path.join(R, "e21_analysis.md"), "w").write(text + "\n")
