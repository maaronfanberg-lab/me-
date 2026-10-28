"""Helpers shared by the experiment 9-12 and 13-16 analyses (copied verbatim from e9_12_analyze.py)."""
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


