"""Ground-truth test for the main goal: a quiet melody partly hidden by a loud pad.

Pad: 4 harmonic tones (A3 C#4 E4 A4, 8 harmonics, 1/h) at ~72 dB SPL. Melody: sine notes 900-1300 Hz,
each set so its exact Stage-2 masked threshold is 5 dB above it (margin -5 dB, hidden but close).
Score = the melody band's margin in the processed signal vs. the input (known notes, known times).
Pass conditions (fixed before running any processor on it):
  H1 median melody margin gain >= 3 dB
  H2 >= 50% of melody frames audible after processing (0% before, by construction)
  H3 integrated loudness within 1 dB
"""
import numpy as np, masking as M, stage3 as S3

FS = S3.FS
PASS = {"H1_median_margin_gain_db": 3.0, "H2_audible_pct": 50.0, "H3_lufs_db": 1.0}
def _notes():
    """Melody notes >= 1 ERB from every pad partial (v1 put notes ~20 Hz from pad partials, below the
    analysis and the ear's resolution, so 'hidden note' had no clean meaning)."""
    pf = np.array([f for f, _ in pad_partials()])
    cand = np.arange(1500.0, 3200.0, 5.0)
    d = np.min(np.abs(M.erb_number(cand)[:, None] - M.erb_number(pf)[None, :]), 1)
    ok = cand[d >= 1.0]
    picks = [ok[int(i)] for i in np.linspace(0, len(ok) - 1, 4)]
    return picks + picks[-2:0:-1]
NOTE_S = 0.5

def db2amp(db):
    return 10 ** ((db - 100) / 20)        # full-scale sine = 100 dB SPL

def pad_partials():
    roots = [220.0, 277.18, 329.63, 440.0]
    return [(r * h, 72.0 - 20 * np.log10(h) - 6) for r in roots for h in range(1, 6)]

def make(seconds=3.0):
    t = np.arange(int(seconds * FS)) / FS
    pp = pad_partials()
    x = sum(db2amp(L) * np.sin(2 * np.pi * f * t + 0.37 * i) for i, (f, L) in enumerate(pp))
    mel = np.zeros_like(t); notes = []
    for i, f in enumerate(_notes()):
        t0 = 0.25 + i * NOTE_S
        if t0 + NOTE_S > seconds: break
        thr = M.masked_threshold(f, pp, "cambridge")
        L = thr - 5.0
        seg = (t >= t0) & (t < t0 + NOTE_S)
        env = np.minimum(1, np.minimum((t[seg] - t0) / 0.01, (t0 + NOTE_S - t[seg]) / 0.01))
        mel[seg] += db2amp(L) * env * np.sin(2 * np.pi * f * t[seg])
        notes.append((t0, f, L, thr))
    return x + mel, notes

def melody_margins(x, notes, mode="cambridge"):
    lev, th, mg, w = S3.analyse(x, mode)
    out = []
    for t0, f, L, thr in notes:
        b = int(np.argmin(np.abs(S3.FC - f)))
        j0, j1 = int((t0 + 0.08) * 100), int((t0 + NOTE_S - 0.03) * 100)
        out.append(mg[b, j0:j1])
    return np.concatenate(out), (lev, th, mg, w)
