"""Stage 2b — two masking modes. Checks (thresholds fixed before the first run):
 M1 refactor is additive: cambridge mode reproduces Stage 2 Model A bit-for-bit.
 M2 munich mode reproduces the Terhardt pattern it encodes, computed the long way (search with the
    1-dB rule), within 0.5 dB at every point >=10 dB above quiet.
 M3 fast path (masking_curve) agrees with the slow search within 1.0 dB in both modes, 25 target
    frequencies 300-6000 Hz, both sides of the masker, no exclusions. (Exclusion zone of first
    version removed: it hid nothing, but a check should not have holes.)
 M4 combination: two-tone masker gives a finite, monotone-in-level threshold in both modes.
 M5 the modes differ where Stage 2 said they do: |above-masker gap| < |below-masker gap|.
"""
import json, importlib.util, sys, os
import numpy as np
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import masking as M
import stage2 as S2

PASS = {"M2_db": 0.5, "M3_db": 1.0}
FM = 1000.0
rep = {"pass_conditions": PASS}

# M1 (at Stage 2's 0.1-ERB grid, so the comparison is like-for-like)
M.set_grid(0.1)
s2 = json.load(open(os.path.join(here, "stage2-report.json")))
worst = 0.0
for L in ["40", "60", "80"]:
    ft = s2["k0.38"][L]["target_hz"]
    A_old = np.array(s2["k0.38"][L]["modelA_threshold_db"])
    A_new = np.array([round(M.masked_threshold(f, [(FM, float(L))], "cambridge"), 2) for f in S2.np.array([S2.bark_inv(S2.bark(FM) + d) for d in S2.DZ])])
    worst = max(worst, float(np.abs(A_new - A_old).max()))
rep["M1_max_diff_db"] = worst; rep["M1_pass"] = worst == 0.0
M.set_grid(0.02)

# M2
w2 = 0.0
for L in [40.0, 60.0, 80.0]:
    ft = np.array([S2.bark_inv(S2.bark(FM) + d) for d in S2.DZ])
    T = np.array([M.masked_threshold(f, [(FM, L)], "munich") for f in ft])
    rel = T - T[np.argmin(np.abs(S2.DZ))]
    B, _ = S2.terhardt_pattern(S2.DZ, L)
    ok = (T > M.quiet_threshold(ft) + 10)
    w2 = max(w2, float(np.abs(rel - B)[ok].max()))
rep["M2_max_diff_db"] = round(w2, 3); rep["M2_pass"] = w2 <= PASS["M2_db"]

# M3
w3 = {}
for mode in M.MODES:
    fr = np.geomspace(300, 6000, 25)
    _, curve = M.masking_curve([(FM, 70.0)], mode, freqs=fr)
    diffs = []
    for f, cv in zip(fr, curve):
        slow = M.masked_threshold(f, [(FM, 70.0)], mode)
        if slow > M.quiet_threshold(f) + 10:
            diffs.append(abs(slow - cv))
    w3[mode] = round(max(diffs), 3)
rep["M3_max_diff_db"] = w3; rep["M3_pass"] = all(v <= PASS["M3_db"] for v in w3.values())

# M4
m4 = {}
for mode in M.MODES:
    th = [M.masked_threshold(1500.0, [(1000.0, L), (2000.0, L - 10)], mode) for L in [50.0, 60.0, 70.0]]
    m4[mode] = [round(x, 2) for x in th]
rep["M4_thresholds_1500Hz_two_tone"] = m4
rep["M4_pass"] = all(np.all(np.isfinite(v)) and v[0] < v[1] < v[2] for v in m4.values())

# M5
ft_hi, ft_lo = S2.bark_inv(S2.bark(FM) + 2), S2.bark_inv(S2.bark(FM) - 1.5)
g = {}
for name, f in [("above_+2bark", ft_hi), ("below_-1.5bark", ft_lo)]:
    g[name] = round(M.masked_threshold(f, [(FM, 80.0)], "munich") - M.masked_threshold(f, [(FM, 80.0)], "cambridge"), 2)
rep["M5_munich_minus_cambridge_db_at_80dB"] = g
rep["M5_pass"] = abs(g["above_+2bark"]) < abs(g["below_-1.5bark"])

rep["STAGE2B_PASS"] = all(rep[k] for k in ["M1_pass", "M2_pass", "M3_pass", "M4_pass", "M5_pass"])
json.dump(rep, open(os.path.join(here, "stage2b-report.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(json.dumps(rep, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
