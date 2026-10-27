"""Hear a network's depth geometry. One sine voice per layer, driven only by that layer's measured lapse.

Mapping (stated so it can be checked; no scale, no quantisation, no added instruments):
    pitch_l(t)  = f_ref * 2 ** log10(N_l(t))     one octave per decade of lapse; N = 1 sounds at f_ref
    amplitude   = equal for every voice           a layer behind a horizon is not faded by hand: its pitch
                                                   simply falls octaves below hearing
    time        = each logged training step lasts `seconds_per_log` of audio; log N is interpolated
                  linearly between logs, and phase is accumulated so pitch glides without clicks
    stereo      = layer depth sets the pan: first hidden layer hard left, last hard right
So a flat network (every N_l = 1) is a unison at f_ref, and a horizon is a voice sinking out of earshot.
"""
import wave
import numpy as np


def render(lapse_history, seconds_per_log=0.06, fs=48000, f_ref=330.0, gain_db=-1.0):
    H = np.asarray(lapse_history, dtype=np.float64)            # (logs, layers)
    H = np.where(np.isfinite(H) & (H > 0), H, 1e-12)
    T, Lyr = H.shape
    n = int(round(T * seconds_per_log * fs))
    t_log = np.arange(n) / (seconds_per_log * fs)               # position in log units
    t_log = np.clip(t_log, 0, T - 1)                            # clamped interpolation
    out = np.zeros((n, 2))
    for l in range(Lyr):
        lg = np.interp(t_log, np.arange(T), np.log10(H[:, l]))
        f = f_ref * 2.0 ** lg
        phase = 2 * np.pi * np.cumsum(f) / fs
        v = np.sin(phase)
        pan = 0.5 if Lyr == 1 else l / (Lyr - 1)
        out[:, 0] += v * np.cos(pan * np.pi / 2)
        out[:, 1] += v * np.sin(pan * np.pi / 2)
    peak = np.max(np.abs(out))
    if peak > 0:
        out *= 10 ** (gain_db / 20) / peak                     # one global gain, nothing else
    return out


def pitch_of(lapse_value, f_ref=330.0):
    return f_ref * 2.0 ** np.log10(lapse_value)


def write_wav(path, stereo, fs=48000):
    s = np.clip(np.round(stereo * 32767), -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(fs); w.writeframes(s.tobytes())
