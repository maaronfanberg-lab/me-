"""Analysis for experiments 9-12, applying the rules fixed in E9_12_PREREGISTRATION.md."""
import os, sys, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from e8_analyze import at_loss_key, R
L = 0.03; TASKS = ["digits", "circle-clean"]


def runs(exp, pat):
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(R, exp, pat)))]


def vals(rs):
    v = [at_loss_key(r["log"], L, "ln_transport") for r in rs]
    v = np.array([x for x in v if x is not None and np.isfinite(x)])
    return v, len(rs)


def fmt(v, n):
    return f"{v.mean():+.2f} ± {v.std(ddof=1):.2f} ({len(v)}/{n})" if len(v) >= 2 else f"{len(v)}/{n} reached"


def above(a, b):
    """Is mean(a) above mean(b) by more than 2*sqrt(sd_a^2+sd_b^2)? None if untestable."""
    if len(a) < 2 or len(b) < 2: return None, None, None
    gap = a.mean() - b.mean(); thr = 2 * np.sqrt(a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2)
    return bool(gap > thr), gap, thr


def word(x): return {True: "yes", False: "no", None: "untestable"}[x]


out = ["# Experiments 9–12 results\n", f"Primary measure: ln_transport at training loss {L}. Reference groups from experiment 8.\n"]
res = {}
for task in TASKS:
    Rv, Rn = vals(runs("e8", f"{task}_relu_d96_s*.json")); Tv, Tn = vals(runs("e8", f"{task}_tanh_d96_s*.json"))
    C = {"signed ReLU, 96": vals(runs("e9", f"{task}_signed_d96_s*.json")), "signed ReLU, 24": vals(runs("e9", f"{task}_signed_d24_s*.json")),
         "shrink, 96": vals(runs("e10", f"{task}_shrink_d96_s*.json")), "tanh+1, 96": vals(runs("e10", f"{task}_tanhp1_d96_s*.json")),
         "warm-up, 96": vals(runs("e11", f"{task}_warmup_d96_s*.json")), "zero-out, 96": vals(runs("e11", f"{task}_zeroout_d96_s*.json"))}
    out.append(f"\n## {task}\n\nReference: plain ReLU 96 = {fmt(Rv, Rn)}; tanh 96 = {fmt(Tv, Tn)}\n")
    out.append("| condition | transport at loss 0.03 | rescued? (gap / threshold vs plain ReLU 96) |")
    out.append("|---|---|---|")
    for name, (v, n) in C.items():
        ok, gap, thr = above(v, Rv); res[(task, name)] = ok
        out.append(f"| {name} | {fmt(v, n)} | {word(ok)}" + (f" ({gap:+.2f} / {thr:.2f})" if gap is not None else "") + " |")
    s96, s24 = C["signed ReLU, 96"][0], C["signed ReLU, 24"][0]
    drop, gap, thr = above(s24, s96); res[(task, "P9b")] = (None if drop is None else not drop)
    out.append(f"\nP9b (signed ReLU, 96 not below 24 by more than threshold): {word(res[(task, 'P9b')])}"
               + (f" (24 minus 96 = {gap:+.2f}, threshold {thr:.2f})" if gap is not None else ""))
    # experiment 12: depth scan of plain ReLU
    out.append("\n| plain ReLU depth | transport at loss 0.03 | stream growth at init (last/first block) |")
    out.append("|---|---|---|")
    D = {}
    for d in (12, 24, 48, 64, 80, 96, 128):
        rs = runs("e8" if d in (12, 24, 48, 96) else "e12", f"{task}_relu_d{d}_s*.json")
        v, n = vals(rs); D[d] = v
        g = [r["log"][0]["stream_norm"][-1] / r["log"][0]["stream_norm"][0] for r in rs] if rs else []
        out.append(f"| {d} | {fmt(v, n) if n else 'not run'} | {np.mean(g):.0f}× |" if g else f"| {d} | not run | – |")
    ok, gap, thr = above(D[48], D[128]) if len(D[128]) else (None, None, None); res[(task, "P12")] = ok
    out.append(f"\nP12 (128 below 48 by more than threshold): {word(ok)}" + (f" (48 minus 128 = {gap:+.2f}, threshold {thr:.2f})" if gap is not None else ""))


def both(key, want=True):
    v = [res[(t, key)] for t in TASKS]
    return "untestable" if None in v else ("holds" if all(x == want for x in v) else "fails")


verdict = {"P9": both("signed ReLU, 96"), "P9b": both("P9b"), "P10": both("shrink, 96"),
           "P11a": both("warm-up, 96", False), "P11b": both("zero-out, 96", False), "P12": both("P12")}
p9_any = [res[(t, "signed ReLU, 96")] for t in TASKS]
hyp = "supported" if verdict["P9"] == "holds" and verdict["P10"] == "holds" else ("refuted" if all(x is False for x in p9_any) else "mixed")
out.insert(2, "**Verdicts:** " + ", ".join(f"{k} {v}" for k, v in verdict.items()) + f". Pile-up hypothesis: **{hyp}**.\n")
text = "\n".join(out); print(text); open(os.path.join(R, "e9_12_analysis.md"), "w").write(text + "\n")
