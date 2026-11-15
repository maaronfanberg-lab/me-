"""Sample playback for the Salisbury piece. VSCO-2-CE (CC0) recordings, tuned from each sample's MEASURED pitch.

render(inst, freq, dur, dyn) returns a stereo float32 note: the nearest-pitched recording at the dynamic layer
nearest `dyn` (0..1), shifted to `freq` by resampling, extended past the recording's end by equal-power
crossfades between takes if the note is longer than the recording, and released with a raised-cosine fade.
"""
import os, json, numpy as np
from functools import lru_cache
from scipy.io import wavfile

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("VSCO", "/home/claude/sgossner/vsco-2-ce")
IDX = json.load(open(os.path.join(HERE, "samples_index.json")))
SUSTAINED = {k for k in IDX if k.endswith("_sus") or k in ("solo_vln", "organ_man", "organ_ped") or k.endswith("_trem")}


def _valid(rows):
    out = []
    for r in rows:
        if r["f0"] is None: continue
        res = r["cents"] - 1200 * round(r["cents"] / 1200)
        if abs(res) < 40: out.append(r)
    return out


LIB = {k: _valid(v) for k, v in IDX.items()}


@lru_cache(maxsize=600)
def load(path):
    sr, x = wavfile.read(os.path.join(ROOT, path))
    assert sr == SR, (path, sr)
    x = x.astype(np.float32) / (32768.0 if x.dtype == np.int16 else (2 ** 31 if x.dtype == np.int32 else 1.0))
    if x.ndim == 1: x = np.stack([x, x], 1)
    x = x[:, :2]
    env = np.abs(x).max(1); pk = env.max() or 1
    on = int(np.argmax(env > pk * 0.01)); on = max(0, on - int(0.004 * SR))   # trim leading silence (-40 dB)
    x = x[on:]
    # usable end: where the level falls 50 dB below peak for good
    above = np.nonzero(env[on:] > pk * 10 ** (-50 / 20))[0]
    end = int(above[-1]) if len(above) else len(x)
    return np.ascontiguousarray(x[:end]), float(pk)


def pick(inst, freq, dyn):
    rows = LIB[inst]
    assert rows, inst
    vels = sorted({r["vel"] for r in rows})
    want = vels[int(round(dyn * (len(vels) - 1)))]
    # nearest pitch first; among those within a semitone, prefer the wanted layer
    best = min(rows, key=lambda r: (abs(np.log2(freq / r["f0"])) * 12 + (0 if r["vel"] == want else 0.6)))
    near = [r for r in rows if abs(np.log2(best["f0"] / r["f0"])) * 12 < 0.5]
    return best, near


def _extend(x, need):
    """Lengthen a sustained recording to `need` samples: repeat its steady middle with 0.6 s equal-power crossfades."""
    if len(x) >= need: return x
    b = int(0.05 * SR); nb = len(x) // b
    e = 20 * np.log10(np.sqrt(np.mean(x[:nb * b, 0].reshape(nb, b) ** 2, 1)) + 1e-9)
    med = np.median(e[int(0.5 * SR) // b:])
    steady = np.nonzero(e > med - 9)[0]                       # last block still within 9 dB of the steady level
    z1 = int(steady[-1] * b) - int(0.2 * SR) if len(steady) else int(0.8 * len(x))
    z0 = int(0.9 * SR)
    if z1 - z0 < int(1.6 * SR): z0, z1 = int(0.3 * len(x)), max(int(0.3 * len(x)) + int(0.5 * SR), z1)
    seg = x[z0:z1]; F = min(int(1.2 * SR), len(seg) // 3)
    fi = np.sin(np.linspace(0, np.pi / 2, F))[:, None].astype(np.float32); fo = np.cos(np.linspace(0, np.pi / 2, F))[:, None].astype(np.float32)
    out = [x[:z1]]; cur = out[0]; total = len(cur); k = 0
    while total < need:
        # alternate forward and a shifted start so repeats do not line up
        s = seg if k % 2 == 0 else np.concatenate([seg[len(seg) // 3:], seg[:len(seg) // 3]])
        tail = out[-1][-F:] * fo + s[:F] * fi
        out[-1] = out[-1][:-F]; out.append(tail); out.append(s[F:]); total += len(s) - F; k += 1
    return np.concatenate(out)[:need]


def render(inst, freq, dur, dyn=0.6, rel=0.6, att=0.0, gain=1.0, detune_cents=0.0, rr=0):
    r, near = pick(inst, freq * 2 ** (detune_cents / 1200), dyn)
    if rr and len(near) > 1: r = near[rr % len(near)]
    x, pk = load(r["file"])
    ratio = freq * 2 ** (detune_cents / 1200) / r["f0"]
    n_out = int((dur + rel) * SR)
    need_src = int(n_out * ratio) + 2
    if inst in SUSTAINED: x = _extend(x, need_src)
    t = np.arange(n_out) * ratio
    t = t[t < len(x) - 1]
    i0 = t.astype(np.int64); fr = (t - i0).astype(np.float32)[:, None]
    y = x[i0] * (1 - fr) + x[i0 + 1] * fr                       # linear interpolation (shifts stay within a semitone)
    env = np.ones(len(y), np.float32)
    a = int(att * SR)
    if a > 1: env[:min(a, len(y))] = np.sin(np.linspace(0, np.pi / 2, a))[:len(y)] ** 2
    if len(y) < n_out and len(y) > 0:                         # the recording ran out: never stop dead
        L = min(len(y), int(0.25 * SR)); env[-L:] *= np.cos(np.linspace(0, np.pi / 2, L)) ** 2
    d = int(dur * SR)
    if d < len(y):
        L = len(y) - d
        env[d:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, L))).astype(np.float32)
    lvl = 10 ** ((dyn - 1.0) * 14 / 20)                         # within-layer level: 14 dB from pp to ff
    return (y * env[:, None] * (gain * lvl)).astype(np.float32)


if __name__ == "__main__":
    import time
    for inst, f in [("vc_sus", 65.4), ("hn_sus", 174.6), ("vln_sus", 440.0), ("tuba_sus", 43.65)]:
        t0 = time.time(); y = render(inst, f, 20.0, 0.7)
        # measure the rendered pitch two ways: requested vs measured from the output
        seg = y[int(2 * SR):int(4 * SR), 0] * np.hanning(int(2 * SR)); N = 1 << 20
        S = np.abs(np.fft.rfft(seg, N)); fr = np.fft.rfftfreq(N, 1 / SR)
        c = f * 2 ** (np.arange(-100, 101) / 1200); sc = [sum(S[int(round(k * q * N / SR))] / k for k in range(1, 6)) for q in c]
        fm = c[int(np.argmax(sc))]
        print(f"{inst:9s} want {f:7.2f} Hz  got {fm:7.2f} Hz ({1200*np.log2(fm/f):+.1f} c)  len {len(y)/SR:.1f}s  {time.time()-t0:.2f}s")
