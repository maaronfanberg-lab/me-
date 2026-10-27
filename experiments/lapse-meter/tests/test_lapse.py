"""Run with:  python tests/test_lapse.py   (or pytest). Every check prints a number and PASS/FAIL."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse import lapse_profile, geometry, slope
from lapse.nets import MLP

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else ""))
    assert ok, name


def test_gradcheck():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((5, 4)); y = rng.integers(0, 3, 5)
    for residual in (False, True):
        for act in ("tanh", "relu", "sigmoid", "linear"):
            net = MLP(4, 6, 4, 3, act=act, sigma_w=1.3, residual=residual, seed=2)
            _, gW, gb, _ = net.backward(X, y)
            worst = 0.0
            for li in range(len(net.W)):
                for (r, c) in [(0, 0), (1, 2), (2, 3)]:
                    if r >= net.W[li].shape[0] or c >= net.W[li].shape[1]:
                        continue
                    h = 1e-6
                    net.W[li][r, c] += h; lp = net.loss(X, y)
                    net.W[li][r, c] -= 2 * h; lm = net.loss(X, y)
                    net.W[li][r, c] += h
                    num = (lp - lm) / (2 * h)
                    if act == "relu" and abs(num) < 1e-12 and abs(gW[li][r, c]) < 1e-12:
                        continue
                    worst = max(worst, abs(num - gW[li][r, c]) / (abs(num) + 1e-8))
            check(f"gradcheck {'residual' if residual else 'plain'} {act}", worst < 1e-5, f"worst rel err {worst:.1e}")


def test_exact_orthogonal_linear():
    # Linear net with every hidden-to-hidden matrix = s * orthogonal: each step back multiplies ||delta|| by exactly s.
    for s in (0.8, 1.0, 1.3):
        net = MLP(32, 32, 10, 5, act="linear", sigma_w=s, orthogonal=True, seed=4)
        rng = np.random.default_rng(1)
        X = rng.standard_normal((64, 32)); y = rng.integers(0, 5, 64)
        _, _, _, d = net.backward(X, y)
        N = lapse_profile(net.geometry_deltas(d))
        ratios = N[:-1] / N[1:]
        k = slope(N)
        check(f"orthogonal linear s={s}: N_l/N_l+1 = s", np.max(np.abs(ratios - s)) < 1e-12, f"max err {np.max(np.abs(ratios - s)):.1e}")
        check(f"orthogonal linear s={s}: kappa = -ln s", abs(k + np.log(s)) < 1e-12, f"kappa {k:+.6f} vs {-np.log(s):+.6f}")


def test_profile_on_constructed_deltas():
    base = np.random.default_rng(3).standard_normal((20, 7))
    deltas = [base * (0.5 ** (4 - i)) for i in range(5)]  # last is output
    N = lapse_profile(deltas)
    check("constructed profile exact", np.allclose(N, [0.5 ** 4, 0.5 ** 3, 0.5 ** 2, 0.5]), str(np.round(N, 6)))
    g = geometry(deltas, horizon=0.1)
    check("tilt = ln N_first", abs(g.tilt - np.log(0.5 ** 4)) < 1e-12, f"{g.tilt:.6f}")
    check("horizon flags layer 0 only", g.horizons == [0], str(g.horizons))
    check("slope None under 3 layers", slope([1.0, 2.0]) is None)


def test_independent_reimplementation():
    # Compare deltas with a separately written plain tanh MLP (the curvature-experiment code), same weights.
    sys.path.insert(0, "/home/claude/curvature")
    try:
        import net as ref
    except Exception as e:
        print("n/a  independent reimplementation unavailable:", e); return
    X, y, _, _ = ref.data(0)
    r = ref.MLP(6, 16, 1.0, 5)
    mine = MLP(64, 16, 6, 10, act="tanh", seed=0)
    mine.W = [w.copy() for w in r.W]; mine.b = [b.copy() for b in r.b]
    _, _, _, dm = mine.backward(X[:100], y[:100])
    _, _, _, dr, _ = r.backward(X[:100], y[:100])
    err = max(float(np.max(np.abs(a - b))) for a, b in zip(dm, dr))
    check("matches independent implementation", err < 1e-12, f"max abs diff {err:.1e}")


def test_remove_alpha():
    # Removing alpha must shift the tilt by exactly -ln(alpha) and leave the slope unchanged.
    rng = np.random.default_rng(5); X = rng.standard_normal((40, 8)); y = rng.integers(0, 3, 40)
    for depth in (4, 16, 64):
        net = MLP(8, 16, depth, 3, act="tanh", residual=True, seed=1)
        d = net.backward(X, y)[3]
        g0 = geometry(net.geometry_deltas(d)); g1 = geometry(net.geometry_deltas(d, remove_alpha=True))
        ok = abs((g1.tilt - g0.tilt) + np.log(net.alpha)) < 1e-12 and abs(g1.kappa - g0.kappa) < 1e-12
        check(f"remove_alpha depth {depth}: tilt shifts by -ln(alpha), slope unchanged", ok,
              f"shift {g1.tilt - g0.tilt:+.6f} vs {-np.log(net.alpha):+.6f}")
    # and it is a no-op for plain nets
    p = MLP(8, 16, 6, 3, seed=1); dp = p.backward(X, y)[3]
    check("remove_alpha is a no-op for plain nets",
          all(np.array_equal(a, b) for a, b in zip(p.geometry_deltas(dp), p.geometry_deltas(dp, remove_alpha=True))))


def test_determinism():
    a = MLP(8, 8, 5, 3, seed=7); b = MLP(8, 8, 5, 3, seed=7)
    check("seeded init bit-identical", all(np.array_equal(x, z) for x, z in zip(a.W, b.W)))


if __name__ == "__main__":
    for f in [test_gradcheck, test_exact_orthogonal_linear, test_profile_on_constructed_deltas, test_independent_reimplementation, test_remove_alpha, test_determinism]:
        f()
    print(f"{sum(RESULTS)}/{len(RESULTS)} checks passed")
