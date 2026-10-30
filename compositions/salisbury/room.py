"""Salisbury Cathedral, modelled. Not a measured impulse response.

Sourced: reverberation "in excess of 6 seconds" (Soundtech case study); total length 135 m (Wikipedia).
Assumed (stated, not measured): volume ~80,000 m^3; decay by octave band typical of a large stone church,
longest in the bass and shortest in the treble; vault ~25 m.

Physics used:
  critical distance r_c = 0.057 * sqrt(V / T60): the distance where direct sound equals the reverberant field.
  direct sound: delay d / 343 s, level 1/d, gentle air absorption in the treble (about 0.1 dB/m at 8 kHz).
  late field: decorrelated noise per octave band decaying at 60 dB per T60(band); its energy is normalised so
  that it equals the direct energy of a source at r_c. Early reflections: seeded image-like taps 10-160 ms.
Everything is seeded, so the same score gives the same recording.
"""
import numpy as np
from scipy.signal import butter, sosfilt, oaconvolve

SR = 44100
V = 80000.0
BANDS = [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
T60 = [7.6, 7.4, 7.0, 6.6, 6.2, 5.2, 3.8, 2.3, 1.2]     # seconds; mid-band (500-1k) 6.2-6.6 s, consistent with "> 6 s"
T_MID = 6.4
R_C = 0.057 * np.sqrt(V / T_MID)                    # ~6.4 m


def late_ir(seed, length=11.0):
    rng = np.random.default_rng(seed); n = int(length * SR); t = np.arange(n) / SR
    out = np.zeros((2, n))
    for fc, T in zip(BANDS, T60):
        lo, hi = fc / np.sqrt(2), min(fc * np.sqrt(2), 0.45 * SR)
        sos = butter(2, [lo, hi], btype="band", fs=SR, output="sos")
        env = np.exp(-6.91 * t / T)
        for ch in range(2):
            out[ch] += sosfilt(sos, rng.standard_normal(n)) * env
    build = 1 - np.exp(-t / 0.045)                   # diffuse field builds up over the first ~100 ms
    out *= build
    # a real pair of microphones in a stone room is not fully decorrelated: mix a little of each side into the other
    mixc = 0.22
    out = np.stack([out[0] + mixc * out[1], out[1] + mixc * out[0]])
    out /= np.sqrt(np.sum(out ** 2) / 2)             # unit energy per channel
    return out


def early_taps(seed, d, width):
    """Seeded reflections from floor, piers, aisle walls and vault, 10-160 ms after the direct sound."""
    rng = np.random.default_rng(seed + 1000); taps = []
    for k in range(48):
        dt = 0.010 + 0.150 * (k / 48) ** 1.3 + rng.uniform(0, 0.004)
        amp = (d / (d + 343 * dt)) * rng.uniform(0.35, 0.8)  # longer path, weaker; stone reflects most energy
        pan = np.clip(rng.normal(0, width), -1, 1)
        taps.append((dt, amp, pan))
    return taps


def make_ir(seed, d, pan, width=0.6, length=11.0):
    """Stereo IR for a source d metres from the listener at stereo position pan (-1..1), excluding the direct path."""
    late = late_ir(seed, length); n = late.shape[1]; ir = np.zeros((2, n))
    pre = int((d / 343.0 + 0.012) * SR)
    g_late = 1.0 / R_C                               # reverberant field = direct level of a source at r_c
    ir[:, pre:] += g_late * late[:, :n - pre]
    for dt, amp, p in early_taps(seed, d, width):
        i = int((d / 343.0 + dt) * SR)
        if i < n:
            a = amp / max(d, 1.0)
            ir[0, i] += a * np.cos((p + 1) * np.pi / 4); ir[1, i] += a * np.sin((p + 1) * np.pi / 4)
    return ir


def direct(stem, d, pan):
    """Direct path: delay, 1/d level, equal-power pan of the stereo stem's mid, light air absorption."""
    delay = int(d / 343.0 * SR); g = 1.0 / max(d, 1.0)
    fc = min(0.45 * SR, 20000 / (1 + d / 60))      # treble loss grows with distance
    sos = butter(1, fc, fs=SR, output="sos")
    m = sosfilt(sos, stem, axis=0)
    width = 0.35                                     # keep some of the recording's own stereo
    L = g * (np.cos((pan + 1) * np.pi / 4) * m.mean(1) * np.sqrt(2) * (1 - width) + width * m[:, 0])
    R = g * (np.sin((pan + 1) * np.pi / 4) * m.mean(1) * np.sqrt(2) * (1 - width) + width * m[:, 1])
    out = np.zeros((len(stem) + delay, 2), np.float32); out[delay:, 0] = L; out[delay:, 1] = R
    return out


def place(stem, d, pan, seed, width=0.6):
    """A stem as heard from the listener's seat: direct sound plus that position's reverberation."""
    dr = direct(stem, d, pan)
    ir = make_ir(seed, d, pan, width)
    mono = stem.mean(1)
    wet = np.stack([oaconvolve(mono, ir[0]), oaconvolve(mono, ir[1])], 1).astype(np.float32)
    n = max(len(dr), len(wet)); out = np.zeros((n, 2), np.float32)
    out[:len(dr)] += dr; out[:len(wet)] += wet
    return out


if __name__ == "__main__":
    print(f"critical distance r_c = {R_C:.1f} m")
    ir = make_ir(1, 15.0, 0.0)
    # check the decay we built: Schroeder backward integration, T20 extrapolated to 60 dB, in the 500 Hz and 1 kHz bands
    for fc in (125, 500, 1000, 4000):
        sos = butter(2, [fc / np.sqrt(2), fc * np.sqrt(2)], btype="band", fs=SR, output="sos")
        h = sosfilt(sos, ir[0]); e = np.cumsum(h[::-1] ** 2)[::-1]; L = 10 * np.log10(e / e[0] + 1e-30)
        i5, i25 = np.argmax(L < -5), np.argmax(L < -25)
        print(f"  {fc:5d} Hz: measured T60 = {3 * (i25 - i5) / SR:.2f} s (target {T60[BANDS.index(fc)]})")
    for d in (6.4, 15, 45):
        print(f"  direct-to-reverberant at {d} m: {20 * np.log10(R_C / d):+.1f} dB")
