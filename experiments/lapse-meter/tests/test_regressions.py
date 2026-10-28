"""One check for each error that earlier checks did not catch (see CORRECTIONS.md). Run: python tests/test_regressions.py"""
import sys, os, re, glob, json, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
import numpy as np
from lapse import geometry
from lapse.nets import MLP, SGD

RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append(ok); print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else "")); assert ok, name


def test_one_time_base():
    """CORRECTIONS 10-11: quantities compared across layers must come from the same steps.
    On a single step, lr*||dL/dW||/||W|| must equal the measured relative weight change exactly; this is the
    identity the clock analysis rests on, and it only holds when both sides use the same step."""
    rng = np.random.default_rng(0); X = rng.standard_normal((64, 16)); y = rng.integers(0, 4, 64)
    net = MLP(16, 16, 8, 4, act="tanh", seed=3); opt = SGD(0.05)
    _, gW, gb, _ = net.backward(X, y)
    before = [w.copy() for w in net.W]; pred = [0.05 * np.linalg.norm(g) / np.linalg.norm(w) for g, w in zip(gW, before)]
    opt.step(net, gW, gb)
    meas = [np.linalg.norm(w - w0) / np.linalg.norm(w0) for w, w0 in zip(net.W, before)]
    err = max(abs(a / b - 1) for a, b in zip(pred, meas))
    check("same-step gradient predicts weight motion exactly", err < 1e-12, f"max rel err {err:.1e}")
    # and a gradient from a *different* step does not: the check can tell the two apart
    _, gW2, _, _ = net.backward(X, y)
    stale = [0.05 * np.linalg.norm(g) / np.linalg.norm(w) for g, w in zip(gW2, before)]
    err2 = max(abs(a / b - 1) for a, b in zip(stale, meas))
    check("a gradient from another step is detectably different", err2 > 1e-6, f"max rel err {err2:.1e}")


def test_alpha_removed_once():
    """CORRECTIONS 13: alpha was removed twice. remove_alpha output must not be rescaled again, and the
    internal-tilt + output-step decomposition must add back to the tilt exactly."""
    rng = np.random.default_rng(1); X = rng.standard_normal((40, 8)); y = rng.integers(0, 3, 40)
    net = MLP(8, 16, 24, 3, act="tanh", residual=True, seed=2)
    d = net.backward(X, y)[3]
    raw = geometry(net.geometry_deltas(d)); cor = geometry(net.geometry_deltas(d, remove_alpha=True))
    check("alpha removed exactly once", abs((cor.tilt - raw.tilt) - (-np.log(net.alpha))) < 1e-12,
          f"shift {cor.tilt - raw.tilt:+.6f}, expected {-np.log(net.alpha):+.6f}")
    L = cor.lapse
    check("internal tilt + output step = tilt", abs(np.log(L[0] / L[-1]) + np.log(L[-1]) - cor.tilt) < 1e-12)


def test_scripts_create_output_folder():
    """CORRECTIONS 16: every experiment script that writes results must create the output folder before training."""
    bad = []
    for f in glob.glob(os.path.join(ROOT, "experiments", "*.py")):
        src = open(f).read()
        writes = re.search(r"json\.dump\(.*open\(", src) or "write_wav(" in src
        if writes and "os.makedirs" not in src and not f.endswith(("analyze.py", "e4_analyze.py", "e6_analyze.py", "e5_alignment.py")):
            bad.append(os.path.basename(f))
    check("every experiment script creates its output folder", not bad, "missing in: " + ", ".join(bad) if bad else "")
    # behavioural check on the fastest script: write into a folder that does not exist yet
    tmp = tempfile.mkdtemp(); target = os.path.join(tmp, "not", "yet", "there.json")
    cfg = '{"task":"circle","depth":3,"act":"tanh","sigma_w":1.0,"residual":false,"lr":0.05,"steps":5,"seed":0,"log_at":[0,5]}'
    r = subprocess.run([sys.executable, os.path.join(ROOT, "experiments", "run.py"), cfg, target], capture_output=True, text=True)
    check("run.py writes into a missing folder", r.returncode == 0 and os.path.exists(target), r.stderr[-200:])


def test_failed_runs_are_counted():
    """CORRECTIONS 23 and 28: comparing at a fixed training loss silently drops runs that never reach it, which twice
    dropped the worst run. Every analysis written after that must report how many runs failed to train, and the
    count must agree with the raw files."""
    sys.path.insert(0, os.path.join(ROOT, "experiments"))
    for name in ("e13_16_analysis.md", "e17_20_analysis.md"):
        txt = open(os.path.join(ROOT, "results", name)).read()
        check(f"{name} reports failed-to-train counts", "failed to train" in txt)
    # the circle 128-layer plain ReLU run that never trained must be visible when counted from the raw files
    rs = [json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "results", "e12", "circle-clean_relu_d128_s*.json"))]
    dead = sum(r["log"][-1]["train_loss"] > 0.5 * np.log(2) for r in rs)
    check("the never-trained 128-layer circle run is counted", dead == 1, f"{dead} of {len(rs)}")


if __name__ == "__main__":
    for f in [test_one_time_base, test_alpha_removed_once, test_scripts_create_output_folder, test_failed_runs_are_counted]:
        f()
    print(f"{sum(RESULTS)}/{len(RESULTS)} regression checks passed")
