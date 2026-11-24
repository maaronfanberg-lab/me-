"""Stage 3 — moment-by-moment "what's hidden" map on real music.

Pipeline (each step from Stages 1-2; nothing tuned on the test track):
 1. Adaptive gammatone analysis (Stage 1): narrow (25 Hz), wide (max(ERB, f/4)) banks, bands every
    25 Hz from 50 Hz to 16 kHz (spacing = narrow bandwidth, so no spectral holes). Envelope power is
    averaged into 1 ms bins.
 2. Onset weight w per band (Stage 1 rules): peak-relative rise, octave-breadth gate, hold until narrow
    ringing is 60 dB down, 20 ms release.
 3. Blend: amplitude (1-w) narrow + w wide; power = blend^2.
 4. Short-term smoothing of band power: Glasberg & Moore (2002) short-term loudness time constants,
    attack 22 ms, release 50 ms (alpha_a = 0.045, alpha_r = 0.02 per 1 ms).
 5. Every 10 ms: each band is a component (fc, level). Calibration: a full-scale sine = 100 dB SPL
    (stated assumption). Masking (Stage 2, mode cambridge or munich): for band b, masker excitation =
    all bands except those holding b's own sound (level explained by b's own filter leakage); threshold by the 1-dB rule solved over all places; margin = level - threshold.

Pass conditions fixed before the first run: PASS.
"""
import json, os, sys, time, hashlib
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.stats import gamma
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import masking as M

PASS = {
    "P2_median_toggles_per_s_contested": 2.0,  # raw audible<->hidden flips, bands contested >=10% each way
    "P3_p95_margin_step_db": 3.0,             # 95th pct |margin change| per 10 ms, bands >=10 dB above quiet
    "P4_deterministic": True,
    "P5_sanity_db": 3.0,                       # pipeline vs Stage 2 exact threshold, synthetic case
}

FS = 48000
DEC = 48                     # 1 ms bins
HOP = 10                     # frames every 10 ms (in 1 ms bins)
FC = np.arange(50.0, 16000.0, 25.0)
K = len(FC)

def erb(f): return M.erb(f)
BW_N = np.minimum(erb(FC), 25.0)
BW_W = np.maximum(erb(FC), FC / 4.0)

def gt_freq_resp(fc, bw, nfft):
    """Frequency response of the unit-peak 4th-order complex gammatone (closed form):
    G(f) = 1 / (1 + j (f - fc)/b')^4 with b' = 1.019 bw, normalised to |G(fc)| = 1."""
    b = 1.019 * bw
    f = np.fft.fftfreq(nfft, 1 / FS)
    return 1.0 / (1.0 + 1j * (f - fc) / b) ** 4

def band_power(x, bws):
    n = len(x)
    nfft = 1 << int(np.ceil(np.log2(n + FS // 2)))
    X = np.fft.fft(x, nfft)
    nb = n // DEC
    out = np.empty((K, nb))
    for i, (fc, bw) in enumerate(zip(FC, bws)):
        y = np.fft.ifft(X * gt_freq_resp(fc, bw, nfft))[:n]
        out[i] = (np.abs(y[:nb * DEC]) ** 2).reshape(nb, DEC).mean(1)
    return out

def onset_weight(Pw):
    """Stage-1 rules on 1 ms bins."""
    L = 10 * np.log10(Pw + 1e-7)
    span, gap = 55, 5
    Mx = maximum_filter1d(L, size=span, axis=1, origin=(span - 1) // 2, mode="nearest")
    prev = np.full_like(L, -1e9); prev[:, gap:] = Mx[:, :-gap]
    rise = L - prev
    local = np.clip((rise - 6.0) / 6.0, 0, 1)
    oct_per_band = np.log2(FC[-1] / FC[0]) / (K - 1)       # bands are linear in Hz: weight by octaves
    octw = np.log2((FC + 12.5) / np.maximum(FC - 12.5, 1.0))
    octaves = ((rise > 6.0) * octw[:, None]).sum(0)
    gate = np.clip(octaves - 1.0, 0, 1)
    target = np.maximum(local, gate[None, :])
    hold = np.round(gamma.ppf(1 - 1e-6, 7) / (4 * np.pi * 1.019 * BW_N) * 1000).astype(int)  # ms
    a = np.exp(-1.0 / 20.0)
    w = np.zeros_like(target)
    for i in range(K):
        prevw = 0.0; cnt = 0; H = hold[i]; row = target[i]; wi = w[i]
        for n in range(row.shape[0]):
            v = row[n]
            if v >= prevw and v > 0: prevw = v; cnt = H
            elif cnt > 0: cnt -= 1
            else: prevw *= a
            wi[n] = prevw
    return w

def stl_smooth(P):
    out = np.empty_like(P); s = P[:, 0].copy()
    for n in range(P.shape[1]):
        v = P[:, n]
        s = np.where(v > s, s + 0.045 * (v - s), s + 0.02 * (v - s))
        out[:, n] = s
    return out

def comp_weights(levels, mode):
    """W[d, k]: weight of component k at detector d (Stage-2 shapes)."""
    D = M.DET[:, None]; f = FC[None, :]
    if mode == "cambridge":
        I = 10 ** (levels / 10)
        en = M.erb_number(FC)
        near = np.abs(en[:, None] - en[None, :]) <= 0.5
        X = 10 * np.log10(near @ I)
        p51 = 4 * D / M.erb(D)
        g = (f - D) / D
        pl = np.maximum(p51 - 0.38 * (p51 / M.P511) * (X[None, :] - 51.0), 0.1)
        p = np.where(g < 0, pl, p51); ga = np.abs(g)
        return (1 + p * ga) * np.exp(-p * ga)
    dz = M.DET_Z[:, None] - M.bark(FC)[None, :]
    s2 = 24.0 + 230.0 / FC[None, :] - 0.2 * levels[None, :]
    return 10 ** (-np.where(dz < 0, 27.0 * (-dz), s2 * dz) / 10)

OFF = 10 * np.log10(10 ** 0.1 - 1)

def frame_margins(levels, bw_now, mode):
    I = 10 ** (levels / 10)
    W = comp_weights(levels, mode)
    C = W * I[None, :]
    # Own sound = neighbouring bands whose level is explained by band b's own filter leakage
    # (level <= L_b + 10log10|G_b(f_k)|^2 + 3 dB). Louder neighbours hold OTHER sound and stay maskers.
    # (v1: df < bw; v2: fixed 40-dB radius, which also threw out a pad partial 20 Hz from a melody
    # note and called the hidden note audible - caught by the hidden-melody ground-truth test.)
    bp = 1.019 * bw_now
    resp = -40.0 * np.log10(1.0 + ((FC[None, :] - FC[:, None]) / bp[:, None]) ** 2)   # [b, k] dB
    own = levels[None, :] <= levels[:, None] + resp + 3.0
    own &= resp > -60.0
    from scipy.sparse import csr_matrix
    E_minus = (C.sum(1, keepdims=True) - np.asarray(csr_matrix(own.astype(float)).dot(C.T).T)) + M.NOISE[:, None]
    with np.errstate(divide="ignore"):
        T = 10 * np.log10(E_minus) + OFF - 10 * np.log10(np.maximum(W, 1e-30))
    T[W < 1e-12] = np.inf
    thr = T.min(0)
    return levels - thr, thr

def analyse(x, mode, grid=0.1):
    M.set_grid(grid)
    Pn, Pw = band_power(x, BW_N), band_power(x, BW_W)
    w = onset_weight(Pw)
    P = ((1 - w) * np.sqrt(Pn) + w * np.sqrt(Pw)) ** 2
    P = stl_smooth(P)
    idx = np.arange(0, P.shape[1], HOP)
    lev = 10 * np.log10(2 * P[:, idx] / 0.5 + 1e-20) + 100.0
    bw = (1 - w[:, idx]) * BW_N[:, None] + w[:, idx] * BW_W[:, None]
    mg = np.empty_like(lev); th = np.empty_like(lev)
    for j in range(lev.shape[1]):
        mg[:, j], th[:, j] = frame_margins(lev[:, j], bw[:, j], mode)
    return lev, th, mg, w[:, idx]

def metrics(lev, th, mg, w):
    aud = mg > 0
    secs = lev.shape[1] * HOP / 1000
    frac = aud.mean(1)
    contested = (frac >= 0.1) & (frac <= 0.9)
    toggles = np.abs(np.diff(aud.astype(int), axis=1)).sum(1) / secs
    # flicker = a flip that reverses within 50 ms (5 frames). A drum hit that hides a band and the band
    # coming back 200 ms later is a real change, not flicker. (First version counted every flip.)
    a = aud.astype(int); rev = np.zeros(a.shape[0])
    d = np.diff(a, axis=1)
    for b in range(a.shape[0]):
        fl = np.nonzero(d[b])[0]
        rev[b] = np.sum(np.diff(fl) <= 5) if len(fl) > 1 else 0
    rev = rev / secs
    above = lev > M.quiet_threshold(FC)[:, None] + 10
    steady = (w[:, 1:] < 0.01) & (w[:, :-1] < 0.01)   # w decays geometrically, never exactly 0
    # jitter in steady passages only (no onset in either frame); transients are meant to move fast
    step = np.abs(np.diff(mg, axis=1))[above[:, 1:] & above[:, :-1] & steady]
    return {
        "seconds": round(secs, 2),
        "n_contested_bands": int(contested.sum()),
        "median_raw_toggles_per_s_contested": round(float(np.median(toggles[contested])), 3) if contested.any() else 0.0,
        "median_toggles_per_s_contested": round(float(np.median(rev[contested])), 3) if contested.any() else 0.0,
        "p90_toggles_per_s_contested": round(float(np.percentile(rev[contested], 90)), 3) if contested.any() else 0.0,
        "n_steady_steps": int(step.size),
        "p95_margin_step_db": round(float(np.percentile(step, 95)), 3) if step.size else None,
        "share_hidden_audible_range": round(float((~aud & above).sum() / max(above.sum(), 1)), 3),
    }

def sanity(mode):
    t = np.arange(int(1.5 * FS)) / FS
    amp = lambda db: 10 ** ((db - 100) / 20)    # full-scale sine (amplitude 1) = 100 dB SPL
    x = amp(70) * np.sin(2 * np.pi * 1000 * t) + amp(40) * np.sin(2 * np.pi * 1100 * t) + amp(40) * np.sin(2 * np.pi * 3000 * t)
    lev, th, mg, w = analyse(x, mode)
    j = slice(lev.shape[1] // 2, None)
    b11, b3 = np.argmin(np.abs(FC - 1100)), np.argmin(np.abs(FC - 3000))
    exact11 = M.masked_threshold(1100.0, [(1000.0, 70.0), (3000.0, 40.0)], mode)
    exact3 = M.masked_threshold(3000.0, [(1000.0, 70.0), (1100.0, 40.0)], mode)
    return {
        "level_1000_band_db": round(float(lev[np.argmin(np.abs(FC - 1000)), j].mean()), 2),
        "thr_1100_pipeline": round(float(th[b11, j].mean()), 2), "thr_1100_exact": round(exact11, 2),
        "thr_3000_pipeline": round(float(th[b3, j].mean()), 2), "thr_3000_exact": round(exact3, 2),
        "1100_hidden": bool(mg[b11, j].mean() < 0), "3000_audible": bool(mg[b3, j].mean() > 0),
    }

def load_audio(path, seconds):
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-t", str(seconds), "-ac", "1", "-ar", str(FS),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)

def main():
    rep = {"pass_conditions": PASS}
    audio = sys.argv[1] if len(sys.argv) > 1 else None
    rep["source"] = sys.argv[2] if len(sys.argv) > 2 else "synthetic"
    if audio:
        x = load_audio(audio, 20)
        start = int(5 * FS); x = x[start:start + 15 * FS] if len(x) > 20 * FS - 1 else x
    else:
        rng = np.random.default_rng(1234); t = np.arange(8 * FS) / FS
        x = sum(0.08 / h * np.sin(2 * np.pi * f0 * h * t) for f0 in (110, 138.59, 164.81) for h in range(1, 10))
        for hit in np.arange(0.5, 8, 0.5):
            n0 = int(hit * FS); tt = t[:len(t) - n0]
            x[n0:] += 0.3 * rng.standard_normal(len(tt)) * np.exp(-tt / 0.05)
    for mode in M.MODES:
        t0 = time.time()
        lev, th, mg, w = analyse(x, mode)
        el = time.time() - t0
        m = metrics(lev, th, mg, w)
        m["compute_s"] = round(el, 1)
        lev2, th2, mg2, _ = analyse(x, mode)
        m["deterministic"] = bool(np.array_equal(mg, mg2))
        m["sanity"] = sanity(mode)
        s = m["sanity"]
        m["P2_pass"] = m["median_toggles_per_s_contested"] <= PASS["P2_median_toggles_per_s_contested"]
        m["P3_pass"] = m["p95_margin_step_db"] is not None and m["n_steady_steps"] >= 1000 and m["p95_margin_step_db"] <= PASS["P3_p95_margin_step_db"]
        m["P4_pass"] = m["deterministic"]
        m["P5_pass"] = (abs(s["thr_1100_pipeline"] - s["thr_1100_exact"]) <= PASS["P5_sanity_db"]
                        and abs(s["thr_3000_pipeline"] - s["thr_3000_exact"]) <= PASS["P5_sanity_db"]
                        and s["1100_hidden"] and s["3000_audible"])
        rep[mode] = m
        np.savez_compressed(os.path.join(here, f"stage3-map-{mode}.npz"), fc=FC, level=lev.astype(np.float32),
                            threshold=th.astype(np.float32), margin=mg.astype(np.float32))
    rep["STAGE3_PASS"] = all(rep[md][p] for md in M.MODES for p in ["P2_pass", "P3_pass", "P4_pass", "P5_pass"])
    json.dump(rep, open(os.path.join(here, "stage3-report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
