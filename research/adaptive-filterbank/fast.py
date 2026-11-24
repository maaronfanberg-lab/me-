"""Stage 5 — fast engine (real-time design), same model as Stages 1-4.

Replaces the per-sample gammatone banks (638 bands x 2, ~9x slower than real time in Python) with two
short-time spectra per 10 ms hop, weighted by the gammatone power responses (Parseval: the power of a
filter's output over a window = sum over bins |X(f)|^2 |G(f)|^2):
  narrow : 4096-point Hann (85 ms)  x  |G_25Hz(f)|^2
  wide   : 1024-point Hann (21 ms)  x  |G_max(ERB,f/4)(f)|^2
Onset weight, hold/release and the Glasberg & Moore (2002) short-term smoothing run at the 10 ms frame
rate with time constants converted, not re-chosen. Masking per frame is Stage 3's frame_margins.
Everything is causal: each frame uses only samples up to its own time.

Pass conditions (fixed before the first run): PASS.
"""
import json, os, sys, time
import numpy as np
from scipy.stats import gamma
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import masking as M
import stage3 as S3

PASS = {
    "F1_steady_level_median_db": 1.0,   # fast vs reference band levels, steady tones + noise, bands >= quiet+10
    "F2_hidden_melody": True,           # H1-H3 and pipeline-vs-exact (3 dB) pass with the fast engine
    "F3_stage3_checks": True,           # flicker <= 2/s median, steady jitter p95 <= 3 dB, deterministic
    "F4_realtime_factor_dev": 1.0,      # info: seconds of audio per second of compute on this machine
}

FS, HOP = S3.FS, 480
NN, NW = 4096, 1024
FC = S3.FC

def _weights(n, bws):
    f = np.fft.rfftfreq(n, 1 / FS)
    b = 1.019 * bws
    return (1.0 + ((f[None, :] - FC[:, None]) / b[:, None]) ** 2) ** -4      # [band, bin]

WN = _weights(NN, S3.BW_N); WN[WN < 1e-9] = 0
WW = _weights(NW, S3.BW_W); WW[WW < 1e-9] = 0
HN = np.hanning(NN); HW = np.hanning(NW)
CN = NN * np.sum(HN ** 2); CW = NW * np.sum(HW ** 2)
from scipy.sparse import csr_matrix
WNs, WWs = csr_matrix(WN), csr_matrix(WW)

HOLD_FR = np.ceil(gamma.ppf(1 - 1e-6, 7) / (4 * np.pi * 1.019 * S3.BW_N) * 100).astype(int)   # 10 ms frames
REL = np.exp(-10.0 / 20.0)
AA, AR = 1 - (1 - 0.045) ** 10, 1 - (1 - 0.02) ** 10
OCTW = np.log2((FC + 12.5) / np.maximum(FC - 12.5, 1.0))

class Engine:
    """Streaming analysis: feed 480-sample hops, get (level, threshold, margin, w) per hop."""
    def __init__(self, mode="cambridge", grid=0.1):
        self.mode = mode; M.set_grid(grid)
        self.buf = np.zeros(NN)
        self.Lhist = np.full((len(FC), 7), -1e9)     # wide-band dB history for peak-relative rise
        self.w = np.zeros(len(FC)); self.cnt = np.zeros(len(FC), int)
        self.s = None

    def step(self, hop):
        self.buf = np.concatenate([self.buf[len(hop):], hop])
        Xn = np.abs(np.fft.rfft(self.buf * HN)) ** 2
        Xw = np.abs(np.fft.rfft(self.buf[-NW:] * HW)) ** 2
        Pn = WNs.dot(Xn) / CN; Pw = WWs.dot(Xw) / CW
        # onset weight (Stage 1 rules at 10 ms resolution)
        L = 10 * np.log10(Pw + 1e-7)
        rise = L - self.Lhist[:, 1:].max(1)          # vs max over the previous 10-60 ms
        self.Lhist = np.roll(self.Lhist, 1, axis=1); self.Lhist[:, 0] = L
        local = np.clip((rise - 6.0) / 6.0, 0, 1)
        gate = np.clip(((rise > 6.0) * OCTW).sum() - 1.0, 0, 1)
        target = np.maximum(local, gate)
        trig = (target >= self.w) & (target > 0)
        self.w = np.where(trig, target, np.where(self.cnt > 0, self.w, self.w * REL))
        self.cnt = np.where(trig, HOLD_FR, np.maximum(self.cnt - 1, 0))
        P = ((1 - self.w) * np.sqrt(Pn) + self.w * np.sqrt(Pw)) ** 2
        if self.s is None: self.s = P.copy()
        self.s = np.where(P > self.s, self.s + AA * (P - self.s), self.s + AR * (P - self.s))
        lev = 10 * np.log10(2 * self.s / 0.5 + 1e-20) + 100.0
        bw = (1 - self.w) * S3.BW_N + self.w * S3.BW_W
        mg, th = S3.frame_margins(lev, bw, self.mode)
        return lev, th, mg, self.w.copy()

def analyse_fast(x, mode="cambridge"):
    e = Engine(mode)
    n = len(x) // HOP
    out = [e.step(x[i * HOP:(i + 1) * HOP]) for i in range(n)]
    lev, th, mg, w = (np.stack([o[k] for o in out], 1) for k in range(4))
    return lev, th, mg, w

def main():
    rep = {"pass_conditions": PASS}
    t = np.arange(3 * FS) / FS
    rng = np.random.default_rng(5)
    steady = (10 ** ((70 - 100) / 20)) * np.sin(2 * np.pi * 1000 * t) + (10 ** ((50 - 100) / 20)) * np.sin(2 * np.pi * 3150 * t) \
        + 0.003 * rng.standard_normal(len(t))
    lr, _, _, _ = S3.analyse(steady, "cambridge")
    lf, _, _, _ = analyse_fast(steady, "cambridge")
    nf = min(lr.shape[1], lf.shape[1]); sl = slice(nf // 2, nf)
    ok = lr[:, sl].mean(1) > M.quiet_threshold(FC) + 10
    d = np.abs(lf[:, sl].mean(1) - lr[:, sl].mean(1))[ok]
    rep["F1_median_db"] = round(float(np.median(d)), 3); rep["F1_p95_db"] = round(float(np.percentile(d, 95)), 3)
    rep["F1_pass"] = rep["F1_median_db"] <= PASS["F1_steady_level_median_db"]

    import hidden_melody as H, stage4 as S4
    x, notes = H.make(3.0)
    def mel(lev, mg):
        out = []
        for t0, f, Ln, thr in notes:
            b = int(np.argmin(np.abs(FC - f))); j0, j1 = int((t0 + 0.12) * 100), int((t0 + H.NOTE_S - 0.03) * 100)
            out.append(mg[b, j0:j1])
        return np.concatenate(out)
    t0c = time.time()
    lev, th, mg, w = analyse_fast(x, "cambridge")
    el = time.time() - t0c
    m_in = mel(lev, mg)
    G = S4.gains2(lev, w, "cambridge", 1, 1); y = S4.process(x, G)
    lev2, _, mg2, _ = analyse_fast(y, "cambridge"); m_out = mel(lev2, mg2)
    hm = {"pipeline_median": round(float(np.median(m_in)), 2), "out_median": round(float(np.median(m_out)), 2),
          "gain": round(float(np.median(m_out - m_in)), 2), "audible_out_pct": round(float((m_out > 0).mean() * 100), 1),
          "lufs_delta": round(float(S4.lufs(y) - S4.lufs(x)), 2)}
    hm["pass"] = bool(abs(hm["pipeline_median"] + 5) <= 3 and hm["gain"] >= 3 and hm["audible_out_pct"] >= 50 and abs(hm["lufs_delta"]) <= 1)
    rep["F2"] = hm; rep["F2_pass"] = hm["pass"]
    rep["F4_realtime_factor_dev"] = round(3.0 / el, 2)

    rng = np.random.default_rng(1234); t = np.arange(8 * FS) / FS
    xs = sum(0.08 / h * np.sin(2 * np.pi * f0 * h * t) for f0 in (110, 138.59, 164.81) for h in range(1, 10))
    for hit in np.arange(0.5, 8, 0.5):
        n0 = int(hit * FS); tt = t[:len(t) - n0]; xs[n0:] += 0.3 * rng.standard_normal(len(tt)) * np.exp(-tt / 0.05)
    f3 = {}
    for mode in M.MODES:
        lev, th, mg, w = analyse_fast(xs, mode)
        m = S3.metrics(lev, th, mg, w)
        _, _, mgb, _ = analyse_fast(xs, mode)
        m["deterministic"] = bool(np.array_equal(mg, mgb))
        m["pass"] = bool(m["median_toggles_per_s_contested"] <= 2 and m["p95_margin_step_db"] is not None
                         and m["n_steady_steps"] >= 1000 and m["p95_margin_step_db"] <= 3 and m["deterministic"])
        f3[mode] = m
    rep["F3"] = f3; rep["F3_pass"] = all(v["pass"] for v in f3.values())
    rep["STAGE5_PASS"] = bool(rep["F1_pass"] and rep["F2_pass"] and rep["F3_pass"])
    conv = lambda o: o.item() if hasattr(o, "item") else str(o)
    json.dump(rep, open(os.path.join(here, "stage5-report.json"), "w"), indent=1, default=conv)
    print(json.dumps(rep, indent=1, default=conv))

if __name__ == "__main__":
    main()
