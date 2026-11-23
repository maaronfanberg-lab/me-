"""Stage 1 — adaptive Fourier<->wavelet analysis filterbank (offline test).

Three 4th-order complex gammatone banks at the same centre frequencies:
  narrow : constant bandwidth 25 Hz        (Fourier-like)
  ear    : ERB(f) = 24.7(4.37 f/1000 + 1)  (Glasberg & Moore 1990; the reference "fixed" bank)
  wide   : constant Q, bandwidth f/4       (wavelet-like)
Adaptive = per-band envelope blend  (1-w) |narrow| + w |wide|, where w rises on
onsets detected from the wide bank (instant attack, 80 ms release).

Pass conditions were fixed before the first run (see PASS dict). Deterministic:
all noise from seed 1234. Run:  python3 stage1.py
"""
import json, sys
import numpy as np

FS = 48000
DUR = 2.0
N = int(FS * DUR)
t = np.arange(N) / FS
rng = np.random.default_rng(1234)

PASS = {
    "erb_match_pct": 2.0,          # numeric ERB within 2% of design, every filter
    "smear_reduction_pct": 20.0,   # adaptive drum smear >= 20% below ear bank
    "sep_gain_db": 3.0,            # adaptive chord separation >= 3 dB above ear bank
    "mix_hold": True,              # both gains still hold inside the drum+chord mixture
}

# ---------------- filters ----------------
def erb(f):
    return 24.7 * (4.37 * f / 1000.0 + 1.0)

BANKS = {
    # The ear sits between the two families: narrow never wider than the ear, wide never narrower.
    "narrow": lambda f: np.minimum(erb(np.asarray(f, float)), 25.0),
    "ear": erb,
    "wide": lambda f: np.maximum(erb(np.asarray(f, float)), np.asarray(f, float) / 4.0),
}

IR_LEN = int(0.5 * FS)
NFFT = 1 << int(np.ceil(np.log2(N + IR_LEN)))

def gammatone_ir(fc, bw):
    """4th-order complex gammatone with equivalent rectangular bandwidth bw (Hz).
    For order 4, ERB = b * pi * (2n-2)! 2^-(2n-2) / ((n-1)!)^2 = b * 0.982 ... -> b = 1.019*bw."""
    b = 1.019 * bw
    tt = np.arange(IR_LEN) / FS
    g = tt**3 * np.exp(-2 * np.pi * b * tt) * np.exp(2j * np.pi * fc * tt)
    G = np.fft.fft(g, NFFT)
    return g / np.abs(G).max()          # unit peak gain

def measured_erb(g):
    """Way 2: ERB from the filter's own power response: integral |G|^2 df / max |G|^2."""
    G = np.fft.fft(g, NFFT)
    P = np.abs(G) ** 2
    df = FS / NFFT
    return P.sum() * df / P.max()

def analytic_erb_factor(n=4):
    """Way 1: closed form for gammatone ERB/b (Patterson et al. 1987)."""
    from math import factorial, pi
    return pi * factorial(2 * n - 2) * 2.0 ** (-(2 * n - 2)) / factorial(n - 1) ** 2

def filt(x, fc_list, bank):
    X = np.fft.fft(x, NFFT)
    out = np.empty((len(fc_list), N))
    for i, fc in enumerate(fc_list):
        g = gammatone_ir(fc, float(BANKS[bank](fc)))
        y = np.fft.ifft(X * np.fft.fft(g, NFFT))[:N]
        out[i] = np.abs(y)
    return out

# ---------------- adaptive weight ----------------
from scipy.ndimage import maximum_filter1d

def rise_db(L):
    """Onset rise: current level minus the MAX level over the previous 5-60 ms.
    Amplitude beats keep re-reaching their own peak, so this stays near 0 dB for them;
    a transient rises far above everything in the recent past."""
    span = int(0.055 * FS); gap = int(0.005 * FS)
    # trailing max over [n-60ms, n-5ms]
    M = maximum_filter1d(L, size=span, axis=1, origin=(span - 1) // 2, mode="nearest")
    prev = np.full_like(L, -1e9)
    prev[:, gap:] = M[:, :-gap]
    return L - prev

def narrow_hold_samples(fcs):
    """Time for the narrow filter's ringing after a transient to fall 60 dB (RT60-style): the
    energy envelope of a 4th-order gammatone is t^6 e^(-4 pi b t), a gamma(7, 4 pi b) shape, so
    the hold is gamma.ppf(1 - 1e-6, 7) / (4 pi b). (First version used the 99% point, 13.2/(4 pi b);
    its last 1% of ringing still smeared transients that sat under a sustained chord.)"""
    from scipy.stats import gamma
    b = 1.019 * BANKS["narrow"](np.asarray(fcs, float))
    return (gamma.ppf(1 - 1e-6, 7) / (4 * np.pi * b) * FS).astype(int)

def onset_weight(env_wide, gate=None, hold=None):
    """Per-band weight from the wide bank: rise in octave-neighbourhood energy over 10 ms.
    0 dB..6 dB rise -> 0, 12 dB -> 1. Instant attack, 80 ms exponential release."""
    eps = 1e-7   # -70 dB floor: rises in near-silent bands (filter leakage) are not onsets
    E = env_wide ** 2
    # smooth 2 ms
    k = int(0.002 * FS)
    ker = np.ones(k) / k
    E = np.array([np.convolve(e, ker)[:N] for e in E])
    # octave neighbourhood: average with bands within a factor of 2 in fc (set by caller via NB)
    En = NB @ E
    L = 10 * np.log10(En + eps)
    rise = rise_db(L)
    target = np.clip((rise - 6.0) / 6.0, 0.0, 1.0)
    if gate is not None:
        # A broadband onset switches every band (a transient under a sustained chord still smears
        # in the chord's bands); a strong local onset switches its own band without the gate.
        target = np.maximum(target, gate[None, :])
    a = np.exp(-1.0 / (0.020 * FS))          # 20 ms release after the hold
    w = np.zeros_like(target)
    for i in range(target.shape[0]):
        prev = 0.0; cnt = 0
        H = int(hold[i]) if hold is not None else 0
        row = target[i]; wi = w[i]
        for n in range(N):
            if row[n] >= prev and row[n] > 0:
                prev = row[n]; cnt = H
            elif cnt > 0:
                cnt -= 1
            else:
                prev *= a
            wi[n] = prev
    return w

def coherence_gate(x):
    """Onsets are broadband (Bello et al. 2005, spectral-flux onset detection); amplitude beats
    between close partials are local in frequency. Gate = octaves covered by full-range wide bands
    whose energy rose >6 dB above their recent peak."""
    fcs = list(np.geomspace(60, 12000, 40))
    E = filt(x, fcs, "wide") ** 2
    k = int(0.002 * FS); ker = np.ones(k) / k
    E = np.array([np.convolve(e, ker)[:N] for e in E])
    L = 10 * np.log10(E + 1e-7)   # same -70 dB floor
    rise = rise_db(L)
    # Measure breadth in octaves, not as a share of bands: in a dense mix the bands held by
    # sustained sound cannot rise, so a share-of-bands test under-reads a real broadband hit.
    oct_per_band = np.log2(fcs[-1] / fcs[0]) / (len(fcs) - 1)
    octaves = (rise > 6.0).sum(0) * oct_per_band
    return np.clip(octaves - 1.0, 0.0, 1.0)      # <=1 octave -> 0, >=2 octaves -> 1

def neighbourhood(fcs):
    f = np.asarray(fcs)
    M = ((f[None, :] >= f[:, None] / 2) & (f[None, :] <= f[:, None] * 2)).astype(float)
    return M / M.sum(1, keepdims=True)

# ---------------- test signals ----------------
HITS = [0.25, 0.75, 1.25, 1.75]

def clicks():
    """Zero-duration transients: all measured spread is filter smear, none is source decay."""
    x = np.zeros(N)
    for h in HITS:
        x[int(h * FS)] = 4.0
    return x

def drums():
    x = np.zeros(N)
    for h in HITS:
        n0 = int(h * FS)
        tt = t[: N - n0]
        f_sweep = 50 + 70 * np.exp(-tt / 0.03)
        kick = np.sin(2 * np.pi * np.cumsum(f_sweep) / FS) * np.exp(-tt / 0.15)
        snare = rng.standard_normal(len(tt)) * np.exp(-tt / 0.06) * 0.5 \
            + 0.3 * np.sin(2 * np.pi * 200 * tt) * np.exp(-tt / 0.05)
        hat = np.diff(rng.standard_normal(len(tt) + 1)) * np.exp(-tt / 0.03) * 0.3
        x[n0:] += kick + snare + hat
    return x

def chord_partials():
    roots = [110.0, 110 * 2 ** (4 / 12), 110 * 2 ** (7 / 12)]
    return [(r * h, 1.0 / h) for r in roots for h in range(1, 13)]

def chord():
    x = np.zeros(N)
    for f, a in chord_partials():
        x += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi))
    return x / 4

# ---------------- metrics ----------------
def smear_ms_spread(env, weights):
    """Energy-weighted temporal spread (ms) of each band envelope in a 0.24 s window after each hit,
    averaged over hits, then energy-weighted over bands."""
    vals, wts = [], []
    win = int(0.24 * FS)
    tw = np.arange(win) / FS
    for b in range(env.shape[0]):
        for h in HITS:
            n0 = int(h * FS)
            e2 = env[b, n0:n0 + win] ** 2
            s = e2.sum()
            if s <= 0:
                continue
            mu = (tw * e2).sum() / s
            vals.append(np.sqrt(((tw - mu) ** 2 * e2).sum() / s) * 1000)
            wts.append(weights[b])
    return float(np.average(vals, weights=wts))

def blur_ms(env, weights):
    """Attack blur: 10%->90% rise time (ms) of each band envelope to its peak within 60 ms
    after each hit. Band weights are FIXED (ear-bank drum energy), identical for every bank,
    so the score reflects the filters, not a re-weighting of bands."""
    win = int(0.060 * FS)
    vals, wts = [], []
    for b in range(env.shape[0]):
        for h in HITS:
            n0 = int(h * FS)
            e = env[b, n0:n0 + win]
            pk = e.max()
            if pk <= 0:
                continue
            i90 = int(np.argmax(e >= 0.9 * pk)); i10 = int(np.argmax(e >= 0.1 * pk))
            vals.append((i90 - i10) / FS * 1000); wts.append(weights[b])
    return float(np.average(vals, weights=wts))

def steady_mask():
    """Samples at least 150 ms after the start and after any hit, and >=50 ms before the next hit."""
    m = t > 0.15
    for h in HITS:
        m &= ~((t > h - 0.05) & (t < h + 0.15))
    return m

def separation_db(env_peaks, env_mids, mask):
    Ep = (env_peaks[:, mask] ** 2).mean(1)
    Em = (env_mids[:, mask] ** 2).mean(1)
    r = 10 * np.log10(0.5 * (Ep[:-1] + Ep[1:]) / Em)
    return float(r.mean()), r

# ---------------- run ----------------
def main():
    report = {"pass_conditions": PASS}

    # G1: bandwidth two ways
    fac = analytic_erb_factor()
    worst = 0.0
    for bank, fn in BANKS.items():
        for fc in [100, 300, 1000, 3000, 8000]:
            bw = float(fn(fc))
            way1 = 1.019 * bw * fac          # closed form
            way2 = measured_erb(gammatone_ir(fc, bw))
            worst = max(worst, abs(way2 - bw) / bw * 100, abs(way1 - bw) / bw * 100)
    report["G1_erb_worst_err_pct"] = round(worst, 3)
    report["G1_pass"] = worst <= PASS["erb_match_pct"]

    # Partials and valley frequencies (pairs closer than 15 Hz are unresolvable by any bank; excluded)
    P = sorted(set(round(f, 2) for f, _ in chord_partials() if f < 2000))
    pairs = [(a, b) for a, b in zip(P[:-1], P[1:]) if b - a >= 15.0]
    peaks = sorted(set([a for a, _ in pairs] + [b for _, b in pairs]))
    # keep pair structure: evaluate peaks per pair
    pk_lo = [a for a, b in pairs]; pk_hi = [b for a, b in pairs]; mids = [(a + b) / 2 for a, b in pairs]
    report["n_pairs"] = len(pairs)
    report["n_excluded_close_pairs"] = len(P) - 1 - len(pairs)

    smear_fcs = list(np.geomspace(60, 12000, 40))
    global NB

    def run(sig_parts):
        out = {}
        x = sum(sig_parts.values())
        gate = coherence_gate(x)
        # weights from the actual input (mixture or single)
        for name, fcs in [("smear", smear_fcs), ("lo", pk_lo), ("hi", pk_hi), ("mid", mids)]:
            globals()["NB"] = neighbourhood(fcs)
            env_w_mix = filt(x, fcs, "wide")
            w = onset_weight(env_w_mix, gate, narrow_hold_samples(fcs))
            out[name] = {"w": w}
            for part, s in sig_parts.items():
                en, ee, ew = filt(s, fcs, "narrow"), filt(s, fcs, "ear"), filt(s, fcs, "wide")
                out[name][part] = {"narrow": en, "ear": ee, "wide": ew,
                                   "adaptive": (1 - w) * en + w * ew}
        return out

    d, c = clicks(), chord()
    mask = steady_mask()
    res = {}
    for label, parts in [("alone", None), ("mix", {"drum": d, "chord": c})]:
        if label == "alone":
            rd = run({"drum": d}); rc = run({"chord": c})
            get = lambda name, part: (rd if part == "drum" else rc)[name][part]
        else:
            rm = run(parts)
            get = lambda name, part: rm[name][part]
        r = {}
        ew = (get("smear", "drum")["ear"] ** 2).sum(1)
        for bank in ["narrow", "ear", "wide", "adaptive"]:
            sm = smear_ms_spread(get("smear", "drum")[bank], ew)
            lo, hi, mid = get("lo", "chord")[bank], get("hi", "chord")[bank], get("mid", "chord")[bank]
            Ep = 0.5 * ((lo[:, mask] ** 2).mean(1) + (hi[:, mask] ** 2).mean(1))
            Em = (mid[:, mask] ** 2).mean(1)
            sep = float(np.mean(10 * np.log10(Ep / Em)))
            r[bank] = {"drum_smear_ms": round(sm, 2), "chord_sep_db": round(sep, 2)}
        res[label] = r
    report["results"] = res

    for label in ["alone", "mix"]:
        r = res[label]
        sred = (r["ear"]["drum_smear_ms"] - r["adaptive"]["drum_smear_ms"]) / r["ear"]["drum_smear_ms"] * 100
        sgain = r["adaptive"]["chord_sep_db"] - r["ear"]["chord_sep_db"]
        report[f"{label}_smear_reduction_pct"] = round(sred, 1)
        report[f"{label}_sep_gain_db"] = round(sgain, 2)
        report[f"{label}_pass"] = sred >= PASS["smear_reduction_pct"] and sgain >= PASS["sep_gain_db"]

    # G4: detector behaviour on realistic drums and on the steady chord
    smear_fcs_ = list(np.geomspace(60, 12000, 40))
    globals()["NB"] = neighbourhood(smear_fcs_)
    dr = drums()
    wd = onset_weight(filt(dr, smear_fcs_, "wide"), coherence_gate(dr), narrow_hold_samples(smear_fcs_))
    hits_found = sum(1 for h in HITS if wd[:, int(h * FS):int((h + 0.02) * FS)].max(1).mean() > 0.5)
    wc = onset_weight(filt(c, smear_fcs_, "wide"), coherence_gate(c), narrow_hold_samples(smear_fcs_))
    w_steady = float(wc[:, mask].mean())
    report["G4_real_drum_hits_detected"] = f"{hits_found}/{len(HITS)}"
    report["G4_chord_steady_mean_w"] = round(w_steady, 4)
    report["G4_pass"] = hits_found == len(HITS) and w_steady < 0.02
    report["STAGE1_PASS"] = report["G1_pass"] and report["alone_pass"] and report["mix_pass"] and report["G4_pass"]
    print(json.dumps(report, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    with open(__file__.replace("stage1.py", "stage1-report.json"), "w") as f:
        json.dump(report, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

if __name__ == "__main__":
    main()
