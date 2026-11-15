"""Can a listener follow individual layers in the shock pieces? Measured, not assumed.
For each log, counts the voices whose nearest other voice is more than one ERB away (the auditory filter width,
Glasberg & Moore 1990: ERB(f) = 24.7 (4.37 f/1000 + 1) Hz). Tones closer than about one ERB fall in the same
auditory filter and fuse into beating rather than being heard as separate notes. Tried: all 95 voices, every 8th
layer (12 voices), and steeper pitch mappings (k octaves per decade of lapse).
Usage: python experiments/sound_separability.py"""
import json, os
import numpy as np
A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio")
erb = lambda f: 24.7 * (4.37 * f / 1000 + 1)


def resolvable(F):
    out = []
    for row in F:
        s = np.sort(row); g = np.diff(s); near = np.full(len(s), np.inf); near[:-1] = g; near[1:] = np.minimum(near[1:], g)
        out.append(np.mean(near > erb(s)))
    return np.array(out)


if __name__ == "__main__":
    for name in ("shock", "shock_warmup"):
        H = np.array(json.load(open(os.path.join(A, name + ".wav.json")))["lapse"])
        for label, cols in (("95 voices", list(range(H.shape[1]))), ("12 voices", list(range(0, H.shape[1], 8)))):
            for k in (1, 3, 7):
                F = 330 * 2 ** (k * np.log10(H[:, cols])); r = resolvable(F)
                print(f"{name}, {label}, {k} octave(s) per decade: {F.min():.0f}-{F.max():.0f} Hz, "
                      f"voices clear of every neighbour by > 1 ERB: mean {r.mean():.0%}")
