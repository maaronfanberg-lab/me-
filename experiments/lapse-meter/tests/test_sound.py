"""Check the sonification does exactly what its docstring says."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse.sound import render, pitch_of

ok_all = []
def check(name, ok, detail=""):
    ok_all.append(ok); print(("PASS " if ok else "FAIL ") + name + "  " + detail); assert ok


def measured_freq(x, fs):
    zc = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    # sub-sample crossing positions
    pos = zc + (-x[zc]) / (x[zc + 1] - x[zc])
    return fs / np.mean(np.diff(pos))


fs = 48000
# 1. one voice, constant lapse values -> pitch equals the mapping
for N in [1.0, 0.1, 3.0, 0.01]:
    a = render(np.full((10, 1), N), seconds_per_log=0.1, fs=fs)
    f = measured_freq(a[:, 0], fs)
    check(f"constant lapse {N}: pitch", abs(f / pitch_of(N) - 1) < 1e-3, f"measured {f:.3f} Hz, mapping {pitch_of(N):.3f} Hz")
# 2. flat network = unison: all voices same pitch -> sum is a single sinusoid at f_ref
a = render(np.ones((10, 5)), seconds_per_log=0.1, fs=fs)
f = measured_freq(a[:, 0] + a[:, 1], fs)
check("flat 5-layer network is a unison at f_ref", abs(f / 330 - 1) < 1e-3, f"{f:.3f} Hz")
# 3. a decade of lapse is exactly one octave
check("one decade = one octave", abs(pitch_of(1.0) / pitch_of(0.1) - 2) < 1e-12)
# 4. deterministic
check("render deterministic", np.array_equal(render(np.random.default_rng(0).random((8, 3)) + 0.01), render(np.random.default_rng(0).random((8, 3)) + 0.01)))
# 5. no clicks: largest sample-to-sample jump stays near the sine's own maximum slope
H = np.vstack([np.ones((5, 1)), np.full((5, 1), 0.01)])
a = render(H, seconds_per_log=0.1, fs=fs)[:, 0]
jump = np.max(np.abs(np.diff(a))); bound = 2 * np.pi * 330 / fs * np.max(np.abs(a)) * 1.01
check("pitch glide has no discontinuity", jump <= bound, f"max step {jump:.5f} <= sine bound {bound:.5f}")
print(f"{sum(ok_all)}/{len(ok_all)} sound checks passed")
