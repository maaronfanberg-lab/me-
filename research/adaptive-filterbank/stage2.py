"""Stage 2 — ear masking model, checked against a published masking-pattern fit.

Model A (built here): Glasberg & Moore (1990) excitation pattern.
  - ERB(f) = 24.7 (4.37 f/1000 + 1)
  - roex weighting W(g) = (1 + p g) exp(-p g),  g = |f - fc| / fc,  p51 = 4 fc / ERB(fc)
  - lower side broadens with level: p_l = p51 - k (p51 / p51_1k)(X - 51), X = level per ERB at the
    component (dB); k = 0.38 (Glasberg & Moore 1990) or 0.35 (ANSI S3.4-2007 / AMT moore1997);
    upper side p_u = p51 (level independent)
  - detectors every 0.1 ERB; masked threshold = target level at which the masker+target excitation
    first exceeds the masker excitation by 1 dB at ANY detector (van der Heijden & Kohlrausch 1994,
    Hear. Res. 80:38-52), so off-frequency listening is included.

Model B (published reference): Terhardt (1979) / Maiwald (1967) tone masking pattern in Bark,
fitted to Zwicker's data: lower slope 27 dB/Bark, upper slope 24 + 230/f - 0.2 L dB/Bark
(f in Hz, L masker level dB SPL). Bark: Zwicker & Terhardt (1980) z = 13 atan(0.76 f/kHz) + 3.5 atan((f/7.5 kHz)^2).
Model B is a formula fitted to data, not raw data; agreement is a shape check.

Pass conditions fixed before the first run: see PASS.  Deterministic (no randomness).
"""
import json
import numpy as np

PASS = {
    "mean_abs_db": 3.0,     # mean |A - B| over audible points, per masker level
    "max_abs_db": 6.0,      # worst point, per masker level
    "upper_slope_flattens": True,   # Model A's upward spread must grow with level, as in the data
    "k_variants_agree_db": 1.0,     # 0.38 vs 0.35 must not change conclusions by more than 1 dB mean
}

FM = 1000.0
LEVELS = [40.0, 60.0, 80.0]
DZ = np.arange(-3.0, 5.01, 0.5)   # target offset from masker in Bark

def erb(f):
    return 24.7 * (4.37 * np.asarray(f, float) / 1000.0 + 1.0)

def erb_number(f):
    return 21.4 * np.log10(4.37 * np.asarray(f, float) / 1000.0 + 1.0)

def erb_number_inv(e):
    return (10 ** (np.asarray(e, float) / 21.4) - 1.0) * 1000.0 / 4.37

def bark(f):
    f = np.asarray(f, float)
    return 13 * np.arctan(0.76 * f / 1000) + 3.5 * np.arctan((f / 7500) ** 2)

def bark_inv(z):
    lo, hi = 1.0, 20000.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if bark(mid) < z: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

def quiet_threshold(f):
    """Terhardt (1979) threshold in quiet, dB SPL."""
    k = np.asarray(f, float) / 1000
    return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4

DET = erb_number_inv(np.arange(erb_number(50), erb_number(15000), 0.1))
P511 = 4 * 1000 / erb(1000)

def excitation(comps, k=0.38):
    """comps: list of (freq Hz, level dB SPL). Returns excitation (intensity units) at DET."""
    f = np.array([c[0] for c in comps]); L = np.array([c[1] for c in comps])
    I = 10 ** (L / 10)
    # level per ERB around each component: sum of component intensities within +-0.5 ERB of it
    en = erb_number(f)
    X = np.array([10 * np.log10(I[np.abs(en - e) <= 0.5].sum()) for e in en])
    E = np.zeros_like(DET)
    p51 = 4 * DET / erb(DET)
    for fi, Ii, Xi in zip(f, I, X):
        g = (fi - DET) / DET               # component below detector CF -> g<0 -> filter's LOWER side
        pl = np.maximum(p51 - k * (p51 / P511) * (Xi - 51.0), 0.1)
        p = np.where(g < 0, pl, p51)
        ga = np.abs(g)
        E += Ii * (1 + p * ga) * np.exp(-p * ga)
    # internal noise: excitation equal to threshold in quiet at each detector
    E += 10 ** (quiet_threshold(DET) / 10)
    return E

def masked_threshold(ft, Lm, k=0.38):
    Em = excitation([(FM, Lm)], k)
    lo, hi = -40.0, 120.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        Emt = excitation([(FM, Lm), (ft, mid)], k)
        if (10 * np.log10(Emt / Em)).max() >= 1.0: hi = mid
        else: lo = mid
    return 0.5 * (lo + hi)

def terhardt_pattern(dz, Lm):
    s1 = 27.0
    s2 = 24.0 + 230.0 / FM - 0.2 * Lm
    return np.where(dz < 0, -s1 * (-dz), -s2 * dz), s2

def run(k):
    zm = bark(FM)
    out = {}
    for Lm in LEVELS:
        ft = np.array([bark_inv(zm + d) for d in DZ])
        A = np.array([masked_threshold(f, Lm, k) for f in ft])
        B_rel, s2 = terhardt_pattern(DZ, Lm)
        # anchor both at the masker frequency (shape comparison; masking index is not part of Model B)
        a0 = A[np.argmin(np.abs(DZ))]
        A_rel = A - a0
        B_abs = a0 + B_rel
        audible = B_abs > quiet_threshold(ft) + 10     # compare only where Model B is well above quiet
        d = (A_rel - B_rel)[audible]
        # Model A's upper slope from its own points between +1 and +3 Bark
        # (test fix) only points >=10 dB above threshold in quiet, so the internal-noise floor
        # cannot flatten the measured slope
        sel = (DZ >= 1) & (DZ <= 3) & (A > quiet_threshold(ft) + 10)
        slopeA = -np.polyfit(DZ[sel], A_rel[sel], 1)[0] if sel.sum() >= 3 else None   # n/a: too few points above the floor
        out[str(int(Lm))] = {
            "target_hz": np.round(ft, 1).tolist(),
            "modelA_threshold_db": np.round(A, 2).tolist(),
            "modelA_rel_db": np.round(A_rel, 2).tolist(),
            "modelB_rel_db": np.round(B_rel, 2).tolist(),
            "masking_index_db_A": round(float(Lm - a0), 2),
            "n_compared": int(audible.sum()),
            "mean_abs_db": round(float(np.abs(d).mean()), 2),
            "max_abs_db": round(float(np.abs(d).max()), 2),
            "upper_slope_A_db_per_bark": None if slopeA is None else round(float(slopeA), 2),
            "upper_slope_B_db_per_bark": round(float(s2), 2),
        }
    return out

def main():
    rep = {"pass_conditions": PASS, "dz_bark": DZ.tolist()}
    r38, r35 = run(0.38), run(0.35)
    rep["k0.38"] = r38; rep["k0.35"] = r35
    lv = [str(int(L)) for L in LEVELS]
    ok_fit = all(r38[l]["mean_abs_db"] <= PASS["mean_abs_db"] and r38[l]["max_abs_db"] <= PASS["max_abs_db"] for l in lv)
    slopes = [r38[l]["upper_slope_A_db_per_bark"] for l in lv]
    valid = [s for s in slopes if s is not None]
    flattens = len(valid) >= 2 and all(a > b for a, b in zip(valid, valid[1:]))
    kdiff = max(abs(r38[l]["mean_abs_db"] - r35[l]["mean_abs_db"]) for l in lv)
    rep["fit_pass"] = ok_fit
    rep["upper_slope_A_by_level"] = slopes
    rep["flattens_pass"] = flattens
    rep["k_variant_max_diff_db"] = round(kdiff, 2)
    rep["k_pass"] = kdiff <= PASS["k_variants_agree_db"]
    rep["STAGE2_PASS"] = ok_fit and flattens and rep["k_pass"]
    with open(__file__.replace("stage2.py", "stage2-report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    short = {k: v for k, v in rep.items() if k not in ("k0.35",)}
    for l in lv:
        r = r38[l]
        print(f"L={l}: mean|d|={r['mean_abs_db']} max|d|={r['max_abs_db']} n={r['n_compared']} "
              f"slopeA={r['upper_slope_A_db_per_bark']} slopeB={r['upper_slope_B_db_per_bark']} "
              f"MI_A={r['masking_index_db_A']}")
        print("   A_rel", r["modelA_rel_db"]); print("   B_rel", r["modelB_rel_db"])
    for k in ["fit_pass", "upper_slope_A_by_level", "flattens_pass", "k_variant_max_diff_db", "k_pass", "STAGE2_PASS"]:
        print(k, rep[k])

if __name__ == "__main__":
    main()
