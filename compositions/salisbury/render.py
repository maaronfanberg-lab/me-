"""Render LAPSE from score.json: every note from a real recording, the Tank from its physics, all in the modelled cathedral.

Usage: python render.py [t0 t1] [out.wav]      (default: the whole piece, 0-1200 s, to lapse.wav)
"""
import os, sys, json, time, hashlib, numpy as np
from scipy.io import wavfile
import sampler, room
from sampler import SR
from tank import Tank
from compose import NODES, EXTRA, F0

HERE = os.path.dirname(os.path.abspath(__file__))
POS = {n[0]: (n[4], n[5]) for n in NODES}; POS.update(EXTRA)
FAMILY = {"vln": 1.0, "vla": 1.0, "vc": 1.05, "cb": 1.1, "solo": 1.0, "harp": 0.9, "hn": 0.9, "tpt": 0.8, "tbn": 0.85,
          "tuba": 0.95, "fl": 0.8, "ob": 0.75, "cl": 0.8, "bn": 0.8, "organ": 0.85, "glock": 0.6}


def ref_levels():
    """Each instrument's RMS for a mid note at dyn 0.6, so sections can be balanced from measured levels."""
    path = os.path.join(HERE, "levels.json")
    if os.path.exists(path): return json.load(open(path))
    out = {}
    for inst, rows in sampler.LIB.items():
        if not rows: continue
        fs = sorted(r["f0"] for r in rows); f = fs[len(fs) // 2]
        y = sampler.render(inst, f, 3.0, 0.6); seg = y[int(0.3 * SR):int(2.5 * SR)]
        out[inst] = float(np.sqrt(np.mean(seg ** 2)) + 1e-9)
    json.dump(out, open(path, "w"), indent=1); return out


LEV = None
PERC = {"timp": "Percussion/Timpani", "timp_roll": "Percussion/Timpani/Rolls", "bdrum": "Percussion"}
# cymbals and gong: (file prefix, dynamic layers soft to loud)
PERC2 = {"crash": ("cymbal-crash1_", ["pp", "mp", "mf", "ff"]), "gong": ("gongHit_", ["p", "mf", "f", "fff"]),
         "gongscrape": ("gongscrape_", ["pp", "mf"]), "scresc_long": ("susCymb1-cresc-Long", [""]),
         "scresc_short": ("susCymb1-cresc-Short", [""])}


def perc_sample(kind, dyn, rr):
    if kind in PERC2:
        pre, layers = PERC2[kind]; d = os.path.join(sampler.ROOT, "Percussion")
        lay = layers[int(round(dyn * (len(layers) - 1)))]
        files = sorted(f for f in os.listdir(d) if f.startswith(pre + lay) and f.endswith(".wav"))
        x, _ = sampler.load(os.path.relpath(os.path.join(d, files[rr % len(files)]), sampler.ROOT)); return x
    d = os.path.join(sampler.ROOT, PERC[kind])
    pref = {"timp": "Timpani", "timp_roll": "Timpani", "bdrum": "BDrumNewhit"}[kind]
    files = sorted(f for f in os.listdir(d) if f.startswith(pref) and f.endswith(".wav"))
    vs = sorted({int(f.split("_v")[1].split("_")[0]) for f in files})
    v = vs[int(round(dyn * (len(vs) - 1)))]
    pick = [f for f in files if f"_v{v}_" in f]
    x, _ = sampler.load(os.path.relpath(os.path.join(d, pick[rr % len(pick)]), sampler.ROOT))
    return x


_tank_cache = {}


def tank_sound(ev):
    f0 = ev.get("f0", F0)
    key = (round(f0, 3), tuple(ev["pins"]), ev["kT"], ev["dur"], ev["pulse"])
    if key not in _tank_cache:
        tk = Tank(decay=14.0, loss=0.12); tk.pins = set(ev["pins"])
        y, _ = tk.strike(f0, ev["dur"], SR, pulse=ev["pulse"], kT=ev["kT"])
        fade = np.ones(len(y)); L = int(1.5 * SR); fade[-L:] = np.cos(np.linspace(0, np.pi / 2, L)) ** 2
        y = y * fade[:, None]; y /= np.max(np.abs(y)) + 1e-12
        _tank_cache[key] = y.astype(np.float32)
    return _tank_cache[key] * (0.55 * ev["amp"])


def render_event(ev):
    if ev["k"] == "tank": return tank_sound(ev)
    if ev["k"] == "perc":
        x = perc_sample(ev["kind"], ev["dyn"], ev["rr"]); return x * (0.5 * ev["gain"] * (0.4 + 0.6 * ev["dyn"]))
    inst = ev["inst"]; fam = inst.split("_")[0]
    norm = 0.06 / LEV.get(inst, 0.06) * FAMILY.get(fam, 1.0)
    parts = []
    for c in range(ev["copies"]):
        det = [0.0, 4.0, -4.0, 7.0, -7.0][c % 5]
        y = sampler.render(inst, ev["f"], ev["dur"], ev["dyn"], rel=ev["rel"], att=ev["att"], gain=ev["gain"] * norm,
                           detune_cents=det, rr=ev["rr"] + c)
        parts.append((int((0.0 if c == 0 else 0.008 + 0.011 * c) * SR), y))
    out = np.zeros((max(lag + len(y) for lag, y in parts), 2), np.float32)   # sized for the longest copy
    for lag, y in parts: out[lag:lag + len(y)] += y
    return out / np.sqrt(ev["copies"]) * (1 + 0.35 * np.log2(ev["copies"]))   # bigger section, a little louder


def group_pos(ev):
    if "pos" in ev: return ev["pos"]
    return POS[ev["g"]] if ev["g"] in POS else POS["perc"]


def render(t0=0.0, t1=1200.0, out="lapse.wav", tail=14.0):
    global LEV; LEV = ref_levels()
    ev = json.load(open(os.path.join(HERE, "score.json")))
    ev = [e for e in ev if t0 - 30.0 <= e["t"] < t1]
    n = int((t1 - t0 + tail) * SR)
    groups = {}
    for e in ev: groups.setdefault((e["g"], tuple(group_pos(e))), []).append(e)
    mix = np.zeros((n, 2), np.float32); t_start = time.time()
    for gi, ((g, pos), es) in enumerate(sorted(groups.items())):
        stem = np.zeros((n + int(40 * SR), 2), np.float32); off = int(30 * SR)
        for e in es:
            y = render_event(e); i = off + int(round((e["t"] - t0) * SR))
            if i + len(y) <= 0 or i >= len(stem): continue
            a = max(0, i); b = min(len(stem), i + len(y)); stem[a:b] += y[a - i:b - i]
        d, pan = pos
        seed = int(hashlib.md5(g.encode()).hexdigest()[:6], 16)
        placed = room.place(stem, d, pan, seed)
        mix += placed[off:off + n]
        print(f"  group {gi + 1}/{len(groups)} {g:12s} d={d:5.1f} m  {len(es):4d} events  {time.time() - t_start:6.1f}s", flush=True)
    peak = float(np.max(np.abs(mix)))
    mix *= 10 ** (-1.0 / 20) / peak                                  # peak at -1 dBFS
    wavfile.write(out, SR, np.clip(mix, -1, 1).astype(np.float32))           # 32-bit float master; no 16-bit rounding
    return dict(peak_before=peak, seconds=n / SR)


if __name__ == "__main__":
    a = sys.argv[1:]
    t0, t1 = (float(a[0]), float(a[1])) if len(a) >= 2 else (0.0, 1200.0)
    out = a[2] if len(a) >= 3 else "lapse.wav"
    print(render(t0, t1, out))
