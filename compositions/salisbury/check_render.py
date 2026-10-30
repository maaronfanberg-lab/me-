"""Checks on a rendered LAPSE: what a listener would notice.
Usage: python check_render.py lapse.wav t0 outdir
  length; clipping; hard edges (largest 50-ms drops, full band and bass, with their times); silent gaps
  (>2 s below -60 dBFS before the final second); level per minute; L/R correlation per movement;
  and a spectrogram of each movement (spectrograms.png)."""
import sys, os, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, spectrogram

path, t0, outd = sys.argv[1], float(sys.argv[2]), sys.argv[3]
sr, x = wavfile.read(path); x = x.astype(np.float32) / 32768; m = x.mean(1); n = len(m)
R = ["# LAPSE render check", "", f"- length: {n / sr:.1f} s"]
clip = int(np.sum(np.abs(x) >= 0.9999)); R.append(f"- samples at full scale: {clip} ({'pass' if clip == 0 else 'FAIL'})")
b = int(0.05 * sr); nb = n // b
def frames(sig): return 10 * np.log10(np.mean(sig[:nb * b].reshape(nb, b) ** 2, 1) + 1e-14)
full = frames(m); bass = frames(sosfilt(butter(4, [20, 300], btype="band", fs=sr, output="sos"), m))
for name, e in (("full band", full), ("bass 20-300 Hz", bass)):
    d = np.diff(e); live = e[:-1] > -70                            # ignore drops from near-silence
    idx = np.argsort(np.where(live, d, 0))[:5]
    R.append(f"- largest 50-ms drops, {name}: " + ", ".join(f"{d[i]:.1f} dB at {t0 + (i + 1) * 0.05:.2f} s" for i in idx))
    # a seam is a drop that does NOT recover within 150 ms; a notch recovers
    seams = [i for i in idx if d[i] < -12 and np.max(e[i + 1:i + 4]) < e[i] - 9]
    R.append(f"  - drops over 12 dB that stay down (hard cut-offs): {len(seams)} ({'pass' if not seams else 'CHECK: ' + ', '.join(f'{t0 + (i + 1) * 0.05:.2f} s' for i in seams)})")
sil = full < -60; gaps = []; run = 0
for i, s in enumerate(sil[: nb - int(1 / 0.05)]):
    run = run + 1 if s else 0
    if run == int(2 / 0.05): gaps.append(t0 + (i - run + 1) * 0.05)
R.append(f"- silent gaps over 2 s before the end: {len(gaps)} ({'pass' if not gaps else 'CHECK: ' + ', '.join(f'{g:.1f} s' for g in gaps)})")
sec = int(60 * sr); lv = [20 * np.log10(np.sqrt(np.mean(m[i:i + sec] ** 2)) + 1e-9) for i in range(0, n - sec // 2, sec)]
R.append("- level per minute (dBFS RMS): " + ", ".join(f"{v:.0f}" for v in lv))
MOV = [("I", 0, 195), ("II", 195, 395), ("III", 395, 595), ("IV", 595, 795), ("V", 795, 995), ("VI", 995, 1200)]
fig, axs = plt.subplots(6, 1, figsize=(14, 18))
for ax, (nm, a, bb) in zip(axs, MOV):
    i0, i1 = int(max(0, a - t0) * sr), int(min(n / sr, bb - t0 + 8) * sr)
    if i1 - i0 < sr: ax.set_visible(False); continue
    seg = x[i0:i1]; c = float(np.corrcoef(seg[:, 0], seg[:, 1])[0, 1])
    rms = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
    R.append(f"- Movement {nm}: RMS {rms:.1f} dBFS, L/R correlation {c:.2f}")
    f, t, S = spectrogram(seg.mean(1), sr, nperseg=8192, noverlap=4096)
    ax.pcolormesh(t + a, f, 10 * np.log10(S + 1e-14), vmin=-125, vmax=-40, shading="auto", cmap="magma")
    ax.set_yscale("log"); ax.set_ylim(25, 12000); ax.set_title(f"Movement {nm}", loc="left")
fig.tight_layout(); fig.savefig(os.path.join(outd, "spectrograms.png"), dpi=60)
open(os.path.join(outd, "report.md"), "w").write("\n".join(R) + "\n")
print("\n".join(R))
