"""Index the VSCO-2-CE samples used by the piece and measure each one's true pitch.
Writes samples_index.json: per instrument, a list of {file, midi_name, vel, f0_measured, cents_off}."""
import os, re, json, sys, numpy as np
from scipy.io import wavfile
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/sgossner/vsco-2-ce"
INST = {  # name: (folder, kind)   kind 'note' = pitched sustain/short
 "vln_sus": "Strings/Violin Section/susVib", "vln_spic": "Strings/Violin Section/Spic", "vln_pizz": "Strings/Violin Section/Pizz", "vln_trem": "Strings/Violin Section/Trem",
 "vla_sus": "Strings/Viola Section/susvib", "vla_spic": "Strings/Viola Section/spic", "vla_pizz": "Strings/Viola Section/pizz", "vla_trem": "Strings/Viola Section/trem",
 "vc_sus": "Strings/Cello Section/susvib", "vc_spic": "Strings/Cello Section/spic", "vc_pizz": "Strings/Cello Section/pizzT", "vc_trem": "Strings/Cello Section/trem",
 "cb_sus": "Strings/Solo Contrabass/SusNV", "cb_pizz": "Strings/Solo Contrabass/Pizz", "cb_trem": "Strings/Solo Contrabass/Trem",
 "solo_vln": "Strings/Solo Violin/Arco Vib", "harp": "Strings/Harp",
 "hn_sus": "Brass/F Horn/sus", "hn_stac": "Brass/F Horn/stac", "tpt_sus": "Brass/Trumpet/sus", "tpt_stac": "Brass/Trumpet/stac",
 "tbn_sus": "Brass/Tenor Trombone/sus", "tbn_stac": "Brass/Tenor Trombone/stac", "tuba_sus": "Brass/Tuba/sus", "tuba_stac": "Brass/Tuba/stac",
 "fl_sus": "Woodwinds/Flute/susvib", "ob_sus": "Woodwinds/Oboe/Vib", "cl_sus": "Woodwinds/Clarinet/susLong", "bn_sus": "Woodwinds/Bassoon/sus",
 "fl_stac": "Woodwinds/Flute/stac", "cl_stac": "Woodwinds/Clarinet/stac", "picc_sus": "Woodwinds/Piccolo/Sus",
 "glock": "Percussion/Glock",
}
NAMES = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}
pat = re.compile(r"_([A-G]#?)(-?\d)(?=[_.])", re.I)
vpat = re.compile(r"_v(\d+)|_(pp|p|mp|mf|f|ff)(?=[_.])")
VEL = {"pp":1,"p":1,"mp":2,"mf":2,"f":3,"ff":3}
def f0_of(x, sr, nominal):
    m = x.mean(1) if x.ndim > 1 else x
    m = m.astype(float); a = int(0.25*sr); seg = m[a:a+int(1.5*sr)]
    if len(seg) < sr//4: seg = m[:int(1.0*sr)]
    seg = seg*np.hanning(len(seg)); N = 1 << 19; S = np.abs(np.fft.rfft(seg, N)); fr = np.fft.rfftfreq(N, 1/sr)
    cands = nominal * 2**(np.arange(-1300, 1301, 2)/1200)  # +-13 semitones, 2-cent steps
    best, bf = -1, None
    for f in cands:
        hs = [S[int(round(k*f*N/sr))] for k in range(1, 7) if k*f < sr/2]
        sc = sum(h/(k) for k, h in enumerate(hs, 1))  # weighted harmonic sum
        if sc > best: best, bf = sc, f
    # refine: parabolic on fundamental bin's harmonic 1..3 average
    return bf
out = {}
for name, folder in INST.items():
    d = os.path.join(ROOT, folder); rows = []
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".wav"): continue
        mm = pat.search(f)
        if not mm: continue
        midi = 12*(int(mm.group(2))+1) + NAMES[mm.group(1).upper()]
        sr, x = wavfile.read(os.path.join(d, f))
        nominal = 440*2**((midi-69)/12)
        f0 = f0_of(x, sr, nominal) if name not in ("timp",) else None
        vm = vpat.search(f); vel = (int(vm.group(1)) if vm.group(1) else VEL[vm.group(2)]) if vm else 1
        rows.append(dict(file=os.path.join(folder, f), midi=midi, vel=vel, sr=sr, dur=round(len(x)/sr, 2),
                         f0=f0, cents=None if f0 is None else round(1200*np.log2(f0/nominal), 1)))
    out[name] = rows
    c = [r["cents"] for r in rows if r["cents"] is not None]
    print(f"{name:10s} n={len(rows):3d} midi {min(r['midi'] for r in rows) if rows else '-'}-{max(r['midi'] for r in rows) if rows else '-'}  cents median {np.median(c) if c else 'n/a'}  |off|>50: {sum(abs(v)>50 for v in c)}", flush=True)
json.dump(out, open("samples_index.json", "w"), indent=0)
