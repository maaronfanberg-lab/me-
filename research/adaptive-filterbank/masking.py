"""Ear masking model with two selectable modes.

  mode="cambridge" : Glasberg & Moore (1990) roex excitation, lower side broadens with level (k=0.38).
                     Built on notched-noise data. Gentler slope below a loud sound (~21-25 dB/Bark).
  mode="munich"    : Terhardt (1979) / Maiwald (1967) spreading in Bark, fitted to Zwicker's tone
                     masking patterns. Lower slope 27 dB/Bark, upper slope 24 + 230/f - 0.2 L dB/Bark.

Both modes share the same threshold rule: a target is masked until masker+target excitation exceeds
masker excitation by 1 dB at any place (van der Heijden & Kohlrausch 1994), with internal noise at the
threshold in quiet (Terhardt 1979). The two modes agree above a masker and differ below it; that
difference is the open scientific question from Stage 2, kept as a choice instead of settled by fiat.
"""
import numpy as np

MODES = ("cambridge", "munich")

def erb(f):
    return 24.7 * (4.37 * np.asarray(f, float) / 1000.0 + 1.0)

def erb_number(f):
    return 21.4 * np.log10(4.37 * np.asarray(f, float) / 1000.0 + 1.0)

def erb_number_inv(e):
    return (10 ** (np.asarray(e, float) / 21.4) - 1.0) * 1000.0 / 4.37

def bark(f):
    f = np.asarray(f, float)
    return 13 * np.arctan(0.76 * f / 1000) + 3.5 * np.arctan((f / 7500) ** 2)

def quiet_threshold(f):
    k = np.asarray(f, float) / 1000
    return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4

P511 = 4 * 1000 / erb(1000)

def set_grid(step_erb):
    """Detector spacing. 0.1 ERB (Stage 2) quantises off-frequency peaks by up to ~0.6 dB on steep
    slopes; 0.02 ERB brings that under 0.2 dB."""
    global DET, DET_Z, NOISE
    DET = erb_number_inv(np.arange(erb_number(50), erb_number(15000), step_erb))
    DET_Z = bark(DET)
    NOISE = 10 ** (quiet_threshold(DET) / 10)

set_grid(0.02)

def excitation(comps, mode="cambridge", k=0.38):
    """comps: list of (freq Hz, level dB SPL). Returns excitation (intensity) at DET."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    f = np.array([c[0] for c in comps], float); L = np.array([c[1] for c in comps], float)
    I = 10 ** (L / 10)
    E = np.zeros_like(DET)
    if mode == "cambridge":
        en = erb_number(f)
        X = np.array([10 * np.log10(I[np.abs(en - e) <= 0.5].sum()) for e in en])
        p51 = 4 * DET / erb(DET)
        for fi, Ii, Xi in zip(f, I, X):
            g = (fi - DET) / DET
            pl = np.maximum(p51 - k * (p51 / P511) * (Xi - 51.0), 0.1)
            p = np.where(g < 0, pl, p51)
            ga = np.abs(g)
            E += Ii * (1 + p * ga) * np.exp(-p * ga)
    else:  # munich
        zc = bark(f)
        for fi, Li, zi in zip(f, L, zc):
            dz = DET_Z - zi
            s2 = 24.0 + 230.0 / fi - 0.2 * Li
            att = np.where(dz < 0, 27.0 * (-dz), s2 * dz)
            E += 10 ** ((Li - att) / 10)
    return E + NOISE

def masked_threshold(target_hz, maskers, mode="cambridge", k=0.38):
    """Level (dB SPL) at which a tone at target_hz is just detectable in the given maskers."""
    Em = excitation(maskers, mode, k)
    lo, hi = -40.0, 130.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        Emt = excitation(list(maskers) + [(target_hz, mid)], mode, k)
        if (10 * np.log10(Emt / Em)).max() >= 1.0: hi = mid
        else: lo = mid
    return 0.5 * (lo + hi)

def _target_weights(ft, Lt, mode, k=0.38, X=None):
    """Linear weight of a target tone (level Lt) at every detector. X = level per ERB around the
    target, which in cambridge mode includes any masker within +-0.5 ERB (as excitation() does)."""
    if mode == "cambridge":
        p51 = 4 * DET / erb(DET)
        g = (ft - DET) / DET
        Xt = Lt if X is None else X
        pl = np.maximum(p51 - k * (p51 / P511) * (Xt - 51.0), 0.1)
        p = np.where(g < 0, pl, p51); ga = np.abs(g)
        return (1 + p * ga) * np.exp(-p * ga)
    dz = DET_Z - bark(ft)
    s2 = 24.0 + 230.0 / ft - 0.2 * Lt
    return 10 ** (-np.where(dz < 0, 27.0 * (-dz), s2 * dz) / 10)

def masking_curve(maskers, mode="cambridge", k=0.38, freqs=None):
    """Masked threshold for tones at `freqs` (default: every detector), using the same 1-dB rule as
    masked_threshold() but solved directly: the target is heard as soon as, at ANY place d,
    Lt + 10log10 W_t(d) >= E_m(d) + 10log10(10^0.1 - 1). So
        Lt = min_d [ E_m(d) - 5.87 dB - 10log10 W_t(d) ]
    (first version used only d = target place; that ignored off-frequency listening and was 11 dB
    too high below a loud masker in cambridge mode). Two passes settle the target's own level effect."""
    Em = 10 * np.log10(excitation(maskers, mode, k))
    off = 10 * np.log10(10 ** 0.1 - 1)
    freqs = DET.copy() if freqs is None else np.asarray(freqs, float)
    mf = np.array([m[0] for m in maskers], float); mI = 10 ** (np.array([m[1] for m in maskers], float) / 10)
    out = np.empty(len(freqs))
    for i, ft in enumerate(freqs):
        Lt = 51.0
        near = mI[np.abs(erb_number(mf) - erb_number(ft)) <= 0.5].sum()
        if mode == "cambridge" and near > 0:
            # target shares an ERB with a masker: each changes the other's filter shape, which the
            # direct solution cannot express -> use the exact search for these few points
            out[i] = masked_threshold(ft, maskers, mode, k)
            continue
        for _ in range(3):
            X = 10 * np.log10(10 ** (Lt / 10) + near)
            W = _target_weights(ft, Lt, mode, k, X)
            ok = W > 1e-12
            Lt = float(np.min(Em[ok] + off - 10 * np.log10(W[ok])))
        out[i] = Lt
    return freqs, out
