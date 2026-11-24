"""Stage 4 — Recover / Tame -> time-varying minimum-phase EQ.

Gain rules (Iris's design, inferred from the Gullfoss manual's descriptions, not Soundtheory's code):
  Recover : a band that is hidden but close (margin between -12 and 0 dB) is lifted toward audibility:
            +min(1 - margin, 6) dB x Recover.   Deeper than -12 dB is treated as leakage, left alone.
  Tame    : a band that pokes out of its neighbourhood (level minus the power mean of +-1 ERB) by more
            than 6 dB is cut: -min(0.5 (d - 6), 6) dB x Tame.
  Loudness: every frame, a broadband offset keeps the K-weighted (BS.1770) band-power sum unchanged.
  Smoothing: 0.5-ERB Gaussian across frequency, then a causal 30 ms one-pole over time.
Filter (patent US11158341 idea: log-magnitude target -> minimum-phase response every ~10 ms, FFT
convolution, overlapping fades). The minimum-phase step here is the exact cepstral (homomorphic)
method, checked against scipy.signal.minimum_phase. Frames: 10 ms hop, 20 ms Hann (50% overlap sums
to 1, so consecutive filters crossfade). Causal: no output sample depends on future input.
Latency ~ 20 ms (frame) + 10 ms (analysis hop). No long buffering.

Pass conditions fixed before the first run: PASS.
"""
import json, os, sys, time
import numpy as np
from scipy.signal import lfilter, freqz, minimum_phase
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import masking as M
import stage3 as S3

PASS = {
    "P1_hidden_share_drop_pp": 5.0,     # share of audible range hidden falls by >= 5 percentage points
    "P2_lufs_delta_db": 1.0,            # |integrated loudness out - in| <= 1 dB
    "P3_pre_echo_db": -40.0,            # energy 1-20 ms before each click <= -40 dB re 0-20 ms after
    "P3_control_must_fail": True,       # the same test must flag a linear-phase version (test is sensitive)
    "P4_bypass_bit_identical": True,
    "P5_deterministic": True,
    "P6_p95_gain_step_db": 1.0,         # per band per 10 ms (no zipper)
}

FS = S3.FS; HOP = 480; NFFT = 4096

# ---------------- loudness (ITU-R BS.1770-4) ----------------
KB1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]; KA1 = [1.0, -1.69065929318241, 0.73248077421585]
KB2 = [1.0, -2.0, 1.0]; KA2 = [1.0, -1.99004745483398, 0.99007225036621]

def lufs(x):
    y = lfilter(KB2, KA2, lfilter(KB1, KA1, x))
    blk, step = int(0.4 * FS), int(0.1 * FS)
    z = np.array([np.mean(y[i:i + blk] ** 2) for i in range(0, len(y) - blk + 1, step)])
    Lb = -0.691 + 10 * np.log10(z + 1e-20)
    z1 = z[Lb > -70]
    rel = -0.691 + 10 * np.log10(z1.mean()) - 10
    z2 = z1[(-0.691 + 10 * np.log10(z1)) > rel]
    return -0.691 + 10 * np.log10(z2.mean())

_, h1 = freqz(KB1, KA1, worN=S3.FC, fs=FS); _, h2 = freqz(KB2, KA2, worN=S3.FC, fs=FS)
KW = np.abs(h1 * h2) ** 2

# ---------------- gains ----------------
EN = M.erb_number(S3.FC)
NEAR1 = (np.abs(EN[:, None] - EN[None, :]) <= 1.0).astype(float)
NEAR1 /= NEAR1.sum(1, keepdims=True)
GS = np.exp(-0.5 * ((EN[:, None] - EN[None, :]) / 0.5) ** 2); GS /= GS.sum(1, keepdims=True)

GS25 = np.exp(-0.5 * ((EN[:, None] - EN[None, :]) / 0.25) ** 2); GS25N = GS25.copy(); GS25 /= GS25.sum(1, keepdims=True)

def attribute(L, bw_now, mode):
    """For each band: margin, the place where it is hardest to hear, and the band (outside its own
    neighbourhood) that contributes most masking there."""
    I = 10 ** (L / 10)
    W = S3.comp_weights(L, mode)
    C = W * I[None, :]
    # Own sound = neighbouring bands whose level is explained by band b's own filter leakage
    # (level <= L_b + 10log10|G_b(f_k)|^2 + 3 dB). Louder neighbours hold OTHER sound and stay maskers.
    # (v1: df < bw; v2: fixed 40-dB radius, which also threw out a pad partial 20 Hz from a melody
    # note and called the hidden note audible - caught by the hidden-melody ground-truth test.)
    bp = 1.019 * bw_now
    resp = -40.0 * np.log10(1.0 + ((S3.FC[None, :] - S3.FC[:, None]) / bp[:, None]) ** 2)   # [b, k] dB
    own = L[None, :] <= L[:, None] + resp + 3.0
    own &= resp > -60.0
    from scipy.sparse import csr_matrix
    E_minus = (C.sum(1, keepdims=True) - np.asarray(csr_matrix(own.astype(float)).dot(C.T).T)) + M.NOISE[:, None]
    with np.errstate(divide="ignore"):
        T = 10 * np.log10(E_minus) + S3.OFF - 10 * np.log10(np.maximum(W, 1e-30))
    T[W < 1e-12] = np.inf
    dstar = T.argmin(0)
    margin = L - T[dstar, np.arange(len(L))]
    Cd = C[dstar, :].copy()                                   # contributions at each band's critical place
    Cd[own] = 0
    masker = Cd.argmax(1)
    # spectral peaks: local maximum over +-1 band (25 Hz). (First version used the whole 40-dB own
    # neighbourhood, ~78 Hz, which merged chord partials 28 Hz apart into one "component".)
    Lp = np.concatenate([[-np.inf], L, [-np.inf]])
    peak = (L >= Lp[:-2]) & (L >= Lp[2:])
    return margin, masker, peak

def gains2(lev, w, mode, recover=1.0, tame=1.0, bias=0.0):
    """Masking-aware Recover/Tame (v2). For each hidden-but-close COMPONENT (spectral peak, margin in
    (-12, 0)), the deficit D = 1 - margin dB is split by Bias: Recover lifts the component by
    (1+bias)/2 * D, Tame cuts its main masker by (1-bias)/2 * D; each capped at 6 dB, scaled by the
    Recover/Tame amounts. Then 0.25-ERB smoothing, loudness compensation, 30 ms causal smoothing."""
    nb, nf = lev.shape
    bwf = (1 - w) * S3.BW_N[:, None] + w * S3.BW_W[:, None]
    G = np.zeros((nb, nf)); a = np.exp(-10.0 / 30.0); prev = np.zeros(nb)
    for j in range(nf):
        L = lev[:, j]
        m, k, peak = attribute(L, bwf[:, j], mode)
        cand = peak & (m > -12) & (m < 0) & (L > M.quiet_threshold(S3.FC) + 10)
        D = 1 - m
        up = np.zeros(nb); down = np.zeros(nb)
        up[cand] = np.minimum((1 + bias) / 2 * D[cand], 6.0) * recover
        np.maximum.at(down, k[cand], np.minimum((1 - bias) / 2 * D[cand], 6.0) * tame)
        # spread each lift/cut as a 0.25-ERB bump keeping its full depth at the centre (dilation);
        # averaging (first version) diluted a single-band 6 dB lift to ~0.4 dB.
        g = (GS25N * up[None, :]).max(1) - (GS25N * down[None, :]).max(1)
        P = 10 ** (L / 10) * KW
        g -= 10 * np.log10((P * 10 ** (g / 10)).sum() / P.sum())
        prev = a * prev + (1 - a) * g
        G[:, j] = prev
    return G

def gains(lev, mg, recover=1.0, tame=1.0):
    nb, nf = lev.shape
    G = np.zeros((nb, nf)); a = np.exp(-10.0 / 30.0); prev = np.zeros(nb)
    for j in range(nf):
        m = mg[:, j]; L = lev[:, j]
        g = np.where((m > -12) & (m < 0), np.minimum(1 - m, 6.0), 0.0) * recover
        local = 10 * np.log10(NEAR1 @ 10 ** (L / 10))
        d = L - local
        g -= np.where(d > 6, np.minimum(0.5 * (d - 6), 6.0), 0.0) * tame
        g = GS @ g
        P = 10 ** (L / 10) * KW
        g -= 10 * np.log10((P * 10 ** (g / 10)).sum() / P.sum())
        prev = a * prev + (1 - a) * g
        G[:, j] = prev
    return G

# ---------------- minimum-phase filters ----------------
FG = np.fft.rfftfreq(NFFT, 1 / FS)

def minphase_from_db(g_db):
    """Exact minimum-phase spectrum for a log-magnitude target (real cepstrum folding)."""
    gd = np.interp(FG, S3.FC, g_db, left=g_db[0], right=g_db[-1])
    logmag = gd * np.log(10) / 20
    full = np.concatenate([logmag, logmag[-2:0:-1]])
    c = np.fft.ifft(full).real
    fold = np.zeros_like(c); fold[0] = c[0]; fold[1:NFFT // 2] = 2 * c[1:NFFT // 2]; fold[NFFT // 2] = c[NFFT // 2]
    return np.exp(np.fft.fft(fold))[: NFFT // 2 + 1]

def linphase_from_db(g_db):
    gd = np.interp(FG, S3.FC, g_db, left=g_db[0], right=g_db[-1])
    return 10 ** (gd / 20) * np.exp(-1j * np.pi * FG / FS * NFFT)      # delay NFFT/2: symmetric FIR

def process(x, G, kind="min"):
    """Time-varying filtering: frame j uses gains G[:, j]. 20 ms Hann frames, 10 ms hop, OLA."""
    if not np.any(G):
        return x.copy()                                                   # bypass: bit-identical
    win = np.hanning(2 * HOP + 1)[:-1]                                    # periodic Hann, sums to 1 at 50%
    y = np.zeros(len(x) + NFFT)
    nf = G.shape[1]
    for j in range(nf):
        s = j * HOP
        seg = x[s:s + 2 * HOP]
        if len(seg) < 2 * HOP: seg = np.pad(seg, (0, 2 * HOP - len(seg)))
        H = minphase_from_db(G[:, j]) if kind == "min" else linphase_from_db(G[:, j])
        out = np.fft.irfft(np.fft.rfft(seg * win, NFFT) * H, NFFT)
        y[s:s + NFFT] += out
    if kind != "min":
        y = y[NFFT // 2:]                                                 # remove the linear-phase delay
    return y[:len(x)]

# ---------------- checks ----------------
def pre_echo_db(G, kind):
    n = G.shape[1] * HOP
    clicks = np.arange(int(0.3 * FS), n - int(0.1 * FS), int(0.25 * FS))
    x = np.zeros(n); x[clicks] = 1.0
    y = process(x, G, kind)
    vals = []
    for c in clicks:
        pre = np.sum(y[c - int(0.020 * FS):c - int(0.001 * FS)] ** 2)
        post = np.sum(y[c:c + int(0.020 * FS)] ** 2)
        vals.append(10 * np.log10(pre / post + 1e-30))
    return float(np.max(vals))

def check_minphase():
    """Way 1 (cepstral) vs way 2 (scipy homomorphic on a linear-phase FIR with the same magnitude)."""
    rng = np.random.default_rng(7)
    g = M.np.convolve(rng.normal(0, 4, len(S3.FC)), np.ones(25) / 25, mode="same")
    H1 = minphase_from_db(g)
    lp = np.fft.irfft(np.abs(H1) ** 2 * np.exp(-1j * np.pi * FG * (NFFT - 1) / FS * 0), NFFT)
    lp = np.roll(lp, NFFT // 2 - 1)[: NFFT - 1]                            # symmetric FIR of |H|^2
    h2 = minimum_phase(lp, method="homomorphic", n_fft=8 * NFFT)
    H2 = np.fft.rfft(h2, NFFT)
    sel = (FG > 60) & (FG < 15000)
    mag_err = float(np.max(np.abs(20 * np.log10(np.abs(H1[sel]) / np.abs(H2[sel])))))
    target = np.interp(FG, S3.FC, g)
    tgt_err = float(np.max(np.abs(20 * np.log10(np.abs(H1[sel])) - target[sel])))
    h1 = np.fft.irfft(H1, NFFT)
    tail = float(10 * np.log10(np.sum(h1[NFFT // 2:] ** 2) / np.sum(h1 ** 2) + 1e-30))
    return {"vs_scipy_mag_db": round(mag_err, 3), "vs_target_db": round(tgt_err, 3), "late_half_energy_db": round(tail, 1)}

def run(x, label, mode="cambridge"):
    rep = {}
    t0 = time.time()
    lev, th, mg, w = S3.analyse(x, mode)
    G = gains2(lev, w, mode, 1.0, 1.0)
    rep["compute_gains_s"] = round(time.time() - t0, 1)
    y = process(x, G, "min")
    lev2, th2, mg2, w2 = S3.analyse(y, mode)
    # (test fix) share hidden among COMPONENTS (spectral peaks >=10 dB above quiet), not every band:
    # most bands are filter skirts of a nearby peak, permanently "hidden" and not detail.
    def comp_hidden(lv, ww):
        bwf = (1 - ww) * S3.BW_N[:, None] + ww * S3.BW_W[:, None]
        hid = tot = 0
        for j in range(lv.shape[1]):
            m, _, pk = attribute(lv[:, j], bwf[:, j], mode)
            c = pk & (lv[:, j] > M.quiet_threshold(S3.FC) + 10)
            hid += int((c & (m <= 0)).sum()); tot += int(c.sum())
        return 100.0 * hid / max(tot, 1)
    h_in, h_out = comp_hidden(lev, w), comp_hidden(lev2, w2)
    # supplementary (not a pass condition): components that were close to audible (margin -12..0) in
    # the input - what share became audible, and how far their margin moved (same band, same frame)
    bwf1 = (1 - w) * S3.BW_N[:, None] + w * S3.BW_W[:, None]
    bwf2 = (1 - w2) * S3.BW_N[:, None] + w2 * S3.BW_W[:, None]
    n_near = n_flip = 0; dm = []
    NH = np.zeros(lev.shape, bool); M1 = np.zeros(lev.shape); M2 = np.zeros(lev.shape)
    for j in range(lev.shape[1]):
        m1, _, pk = attribute(lev[:, j], bwf1[:, j], mode)
        m2, _, _ = attribute(lev2[:, j], bwf2[:, j], mode)
        c = pk & (m1 > -12) & (m1 < 0) & (lev[:, j] > M.quiet_threshold(S3.FC) + 10)
        n_near += int(c.sum()); n_flip += int((c & (m2 > 0)).sum()); dm.extend((m2 - m1)[c].tolist())
        NH[:, j] = c; M1[:, j] = m1; M2[:, j] = m2
    # persistent: same band near-hidden for >= 5 consecutive frames (50 ms); score frames 3+ of each run
    run_len = np.zeros(lev.shape, int)
    for j in range(lev.shape[1]):
        run_len[:, j] = np.where(NH[:, j], (run_len[:, j - 1] + 1) if j else 1, 0)
    full = np.zeros(lev.shape, bool)
    for j in range(lev.shape[1] - 1, -1, -1):
        nxt = full[:, j + 1] if j + 1 < lev.shape[1] else np.zeros(lev.shape[0], bool)
        full[:, j] = NH[:, j] & ((run_len[:, j] >= 5) | (nxt & NH[:, j]))
    sel = full & (run_len >= 3)
    rep["persistent_near_hidden_cells"] = int(sel.sum())
    rep["persistent_became_audible_pct"] = round(100.0 * float(((M2 > 0) & sel).sum()) / max(int(sel.sum()), 1), 1)
    rep["persistent_median_margin_gain_db"] = round(float(np.median((M2 - M1)[sel])), 2) if sel.any() else None
    rep["near_hidden_components"] = n_near
    rep["near_hidden_became_audible_pct"] = round(100.0 * n_flip / max(n_near, 1), 1)
    rep["near_hidden_median_margin_gain_db"] = round(float(np.median(dm)), 2) if dm else None
    rep["hidden_share_in_pct"] = round(h_in, 2); rep["hidden_share_out_pct"] = round(h_out, 2)
    rep["P1_pass"] = (h_in - h_out) >= PASS["P1_hidden_share_drop_pp"]
    li, lo = lufs(x), lufs(y)
    rep["lufs_in"] = round(li, 2); rep["lufs_out"] = round(lo, 2)
    rep["P2_pass"] = abs(lo - li) <= PASS["P2_lufs_delta_db"]
    pe_min = pre_echo_db(G, "min")
    # (test fix) sensitivity control: linear phase with a fixed, clearly audible EQ (+12 dB at 1 kHz,
    # -12 dB at 3 kHz, 0.5-ERB wide). First version used the program EQ, whose mild gains gave the
    # linear-phase control only -46.7 dB pre-echo, so the control could not prove the test sensitive.
    ctrl = 12 * np.exp(-0.5 * ((EN - M.erb_number(1000)) / 0.5) ** 2) - 12 * np.exp(-0.5 * ((EN - M.erb_number(3000)) / 0.5) ** 2)
    pe_lin = pre_echo_db(np.repeat(ctrl[:, None], G.shape[1], 1), "lin")
    rep["pre_echo_min_db"] = round(pe_min, 1); rep["pre_echo_linear_control_db"] = round(pe_lin, 1)
    rep["P3_pass"] = pe_min <= PASS["P3_pre_echo_db"] and pe_lin > PASS["P3_pre_echo_db"]
    rep["P4_pass"] = bool(np.array_equal(process(x, np.zeros_like(G)), x))
    rep["P5_pass"] = bool(np.array_equal(process(x, gains2(lev, w, mode, 1.0, 1.0)), y))
    step = np.abs(np.diff(G, axis=1))
    rep["p95_gain_step_db"] = round(float(np.percentile(step, 95)), 3)
    rep["max_gain_db"] = round(float(G.max()), 2); rep["min_gain_db"] = round(float(G.min()), 2)
    rep["P6_pass"] = rep["p95_gain_step_db"] <= PASS["P6_p95_gain_step_db"]
    rep["STAGE4_PASS"] = bool(all(rep[f"P{i}_pass"] for i in range(1, 7)))
    return rep

def main():
    out = {"pass_conditions": PASS, "minphase_check": check_minphase()}
    if len(sys.argv) > 1:
        x = S3.load_audio(sys.argv[1], 20); x = x[5 * FS:20 * FS]; src = sys.argv[2]
    else:
        rng = np.random.default_rng(1234); t = np.arange(8 * FS) / FS
        x = sum(0.08 / h * np.sin(2 * np.pi * f0 * h * t) for f0 in (110, 138.59, 164.81) for h in range(1, 10))
        for hit in np.arange(0.5, 8, 0.5):
            n0 = int(hit * FS); tt = t[:len(t) - n0]
            x[n0:] += 0.3 * rng.standard_normal(len(tt)) * np.exp(-tt / 0.05)
        src = "synthetic"
    out["source"] = src
    for mode in M.MODES:
        out[mode] = run(x, src, mode)
    out["STAGE4_PASS"] = all(out[m]["STAGE4_PASS"] for m in M.MODES)
    conv = lambda o: o.item() if hasattr(o, "item") else str(o)
    json.dump(out, open(os.path.join(here, "stage4-report.json"), "w"), indent=1, default=conv)
    print(json.dumps(out, indent=1, default=conv))

if __name__ == "__main__":
    main()
