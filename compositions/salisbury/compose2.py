"""LAPSE: symphonic poem for orchestra, organ and the Tank, for Salisbury Cathedral (20 minutes).

A composed piece: two themes, real chord progressions with voice-leading, D minor to D major.
The research data decides WHERE things happen (the shape), not the notes:
  III scherzo   experiment 53's 24 cells (3 seeds each, the honest unit): a cell that diverged brings brass and timpani
                hits into its five bars; a healthy cell gets pizzicato answers
  IV anchors    the antiphonal call-and-answer gap closes as the Tank's 12 anchors come away, 2 bars -> 0
  V teardown    the lapse-meter trace: the pile-up converges on one note; the collapse follows the stream
                234 -> 105 -> 20 (-7 dB, -21 dB); which players survive follows the gate data
  VI adagio     the Cass4 figure: compact close voicing around the solo violin, then wider, farther, with a halo
  VII finale    the orchestra thins from 13 sections towards the 28 strongest Metatron connections, then returns

Sections (seconds): I 0-150 intro, II 150-333 theme A, III 333-542 scherzo, IV 542-692 chorale,
V 692-812 pile-up/teardown, VI 812-998 adagio, VII 998-1188 finale, then the cathedral's tail to 1200.
"""
import os, json, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LM = os.path.join(HERE, "..", "..", "experiments", "lapse-meter")

# ------------------------------------------------------------------ the orchestra, seated at the crossing
# group: (distance m, pan, copies)    the listener sits in the nave, about 14 m from the front desks
SEAT = {"vln1": (14.0, -0.62, 3), "vln2": (14.5, -0.28, 3), "vla": (14.5, 0.22, 2), "vc": (14.0, 0.52, 2),
        "cb": (16.5, 0.72, 2), "fl": (17.0, -0.15, 2), "ob": (17.0, 0.10, 1), "cl": (18.0, -0.10, 2),
        "bn": (18.0, 0.15, 2), "hn": (19.5, -0.45, 2), "tpt": (20.0, 0.25, 2), "tbn": (20.5, 0.45, 2),
        "tuba": (20.5, 0.62, 1), "harp": (15.0, -0.80, 1), "solo": (12.0, -0.08, 1), "perc": (21.5, 0.0, 1),
        "timp": (21.0, 0.30, 1), "organ": (26.0, 0.0, 1), "tank": (22.0, -0.05, 1),
        "west": (32.0, 0.22, 2), "east": (28.0, -0.25, 2)}
INST = {"vln1": "vln", "vln2": "vln", "vla": "vla", "vc": "vc", "cb": "cb", "fl": "fl", "ob": "ob", "cl": "cl", "bn": "bn",
        "hn": "hn", "tpt": "tpt", "tbn": "tbn", "tuba": "tuba", "solo": "solo", "west": "tpt", "east": "hn"}
ART = {"vln": {"sus": "vln_sus", "short": "vln_spic", "pizz": "vln_pizz", "trem": "vln_trem"},
       "vla": {"sus": "vla_sus", "short": "vla_spic", "pizz": "vla_pizz", "trem": "vla_trem"},
       "vc": {"sus": "vc_sus", "short": "vc_spic", "pizz": "vc_pizz", "trem": "vc_trem"},
       "cb": {"sus": "cb_sus", "short": "cb_pizz", "pizz": "cb_pizz", "trem": "cb_sus"},
       "fl": {"sus": "fl_sus", "short": "fl_stac"}, "ob": {"sus": "ob_sus", "short": "ob_sus"},
       "cl": {"sus": "cl_sus", "short": "cl_stac"}, "bn": {"sus": "bn_sus", "short": "bn_sus"},
       "hn": {"sus": "hn_sus", "short": "hn_stac"}, "tpt": {"sus": "tpt_sus", "short": "tpt_stac"},
       "tbn": {"sus": "tbn_sus", "short": "tbn_stac"}, "tuba": {"sus": "tuba_sus", "short": "tuba_stac"},
       "solo": {"sus": "solo_vln", "short": "solo_vln"}}
RANGE = {"solo": (55, 98), "vln": (55, 93), "vla": (48, 84), "vc": (36, 76), "cb": (28, 55), "fl": (60, 96), "ob": (58, 89), "cl": (50, 89),
         "bn": (34, 72), "hn": (41, 77), "tpt": (54, 82), "tbn": (40, 70), "tuba": (29, 58)}

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
def midi(s):
    """'D4', 'Bb3', 'F#5' -> MIDI number (C4 = 60)."""
    pc = NOTE[s[0]]; i = 1
    while i < len(s) and s[i] in "#b": pc += 1 if s[i] == "#" else -1; i += 1
    return pc + 12 * (int(s[i:]) + 1)
hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)

QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11), "dim": (0, 3, 6),
        "sus4": (0, 5, 7), "add9": (0, 4, 7, 14)}
def chord(sym):
    """'Dm', 'Bb', 'A7', 'D/F#', 'Gm/Bb' -> (pitch classes, bass pc)."""
    main, _, bass = sym.partition("/")
    root = NOTE[main[0]]; i = 1
    while i < len(main) and main[i] in "#b": root += 1 if main[i] == "#" else -1; i += 1
    pcs = [(root + iv) % 12 for iv in QUAL[main[i:]]]
    if bass:
        b = NOTE[bass[0]] + sum(1 if c == "#" else -1 for c in bass[1:]); return pcs, b % 12
    return pcs, root % 12

EV = []
HARM = []   # (t0, t1, pitch classes, symbol) of every chord the pads play: the chord-tone audit checks against it
def ev_note(t, g, inst, m, dur, dyn, att=0.05, rel=0.45, copies=None, gain=1.0, rr=0, pos=None):
    d, pan, cp = SEAT[g]
    EV.append(dict(k="note", t=float(t), g=g, inst=inst, f=hz(m), dur=float(max(0.08, dur)), dyn=float(np.clip(dyn, 0.0, 1.0)),
                   att=float(att), rel=float(rel), copies=int(copies or cp), gain=float(gain), rr=int(rr),
                   pos=list(pos or (d, pan))))
import sampler as _smp
def _gap(inst, m):
    return min(abs(m - (69 + 12 * np.log2(r["f0"] / 440))) for r in _smp.LIB[inst])
def play(t, g, m, dur, dyn, art="sus", **kw):
    fam = INST[g]; lo, hi = RANGE[fam]
    while m < lo: m += 12
    while m > hi: m -= 12
    inst = ART[fam].get(art, ART[fam]["sus"])
    if _gap(inst, m) > 3:                                   # too far from any real recording: try the octave that is closer
        alts = [x for x in (m - 12, m + 12) if lo <= x <= hi and _gap(inst, x) <= 3]
        if alts: m = min(alts, key=lambda x: abs(x - m))
    ev_note(t, g, inst, m, dur, dyn, **kw)
def tank(t, root_midi, amp, pins=(), dur=16.0, pulse=0.004):
    f0 = hz(root_midi)
    while f0 > 60: f0 /= 2
    while f0 < 30: f0 *= 2
    EV.append(dict(k="tank", t=float(t), g="tank", f0=f0, amp=float(amp), pins=list(pins), kT=None, dur=dur, pulse=pulse,
                   pos=list(SEAT["tank"][:2])))
def perc(t, kind, dyn, rr=0, gain=1.0, g="perc"):
    EV.append(dict(k="perc", t=float(t), g=g, kind=kind, dyn=float(np.clip(dyn, 0, 1)), rr=rr, gain=gain, pos=list(SEAT[g][:2])))
def organ(ms, t, dur, dyn, att=1.5, rel=2.5):
    for m in ms:
        inst = "organ_ped" if m < 48 else "organ_man"
        ev_note(t, "organ", inst, m, dur, dyn, att=att, rel=rel, copies=1)


class Seg:
    """A section of the score in 4/4 at a fixed tempo. at(bar, beat): bar from 1, beat from 0."""
    def __init__(self, t0, bpm): self.t0, self.spb = t0, 60.0 / bpm
    def at(self, bar, beat=0.0): return self.t0 + ((bar - 1) * 4 + beat) * self.spb
    def beats(self, b): return b * self.spb


def melody(seg, bar, notes, g, dyn, art="sus", legato=0.18, hairpin=None, rr=0, oct=0, gain=1.0, **kw):
    """notes: list of (name or None for rest, beats). Legato by overlapping each note into the next."""
    beat = 0.0; N = len(notes)
    for i, (nm, b) in enumerate(notes):
        if nm is not None:
            dd = dyn if hairpin is None else dyn + (hairpin - dyn) * (i / max(1, N - 1))
            # shape: a little more on longer notes and on the phrase's high point
            play(seg.at(bar, beat), g, (nm if isinstance(nm, int) else midi(nm)) + 12 * oct, seg.beats(b) + legato, dd, art=art, att=0.08 if art == "sus" else 0.0,
                 rel=0.5 if art == "sus" else 0.3, rr=rr + i, gain=gain, **kw)
        beat += b
    return beat


def voices(pcs, bass_pc, prev, ranges):
    """Voice-leading: each voice takes the chord tone nearest its previous pitch, inside its range; the first voice is the bass."""
    out = []
    for k, (lo, hi) in enumerate(ranges):
        is_bass = k == 0 or hi <= 50                       # low voices (tuba, basses) double the bass note
        cands = [m for m in range(lo, hi + 1) if (m % 12 == bass_pc if is_bass else m % 12 in pcs)]
        p = prev[k] if prev and k < len(prev) and lo - 7 <= prev[k] <= hi + 7 else (lo + hi) // 2
        out.append(min(cands, key=lambda m: (abs(m - p), m)))
    # avoid all upper voices doubling one note: nudge duplicates to the next chord tone
    seen = set()
    for k in range(1, len(out)):
        if out[k] in seen:
            lo, hi = ranges[k]
            alts = [m for m in range(lo, hi + 1) if m % 12 in pcs and m not in seen]
            if alts: out[k] = min(alts, key=lambda m: abs(m - out[k]))
        seen.add(out[k])
    return out


def pad(seg, bar0, prog, parts, dyn, bars_per=1, art="sus", hair=None, prev=None, rr=0, gain=1.0):
    """Sustained chords: prog is a list of chord symbols, one per `bars_per` bars; parts: list of (group, lo, hi), bass first."""
    ranges = [(lo, hi) for _, lo, hi in parts]
    for i, sym in enumerate(prog):
        pcs, bp = chord(sym); prev = voices(pcs, bp, prev, ranges)
        d = dyn if hair is None else dyn + (hair - dyn) * i / max(1, len(prog) - 1)
        t = seg.at(bar0 + i * bars_per); L = seg.beats(4 * bars_per); HARM.append((t, t + L, sorted(set(pcs) | {bp}), sym))
        for (g, _, _), m in zip(parts, prev):
            play(t, g, m, L + 0.25, d, art=art, att=0.35, rel=0.9, rr=rr + i, gain=gain)
    return prev


# ------------------------------------------------------------------ the themes
THEME_A = [("D4", 2), ("A4", 2), ("G4", 1), ("F4", 1), ("E4", 1), ("F4", 1), ("D4", 3), ("C4", 1), ("D4", 2), ("E4", 1), ("F4", 1),
           ("G4", 2), ("A4", 2), ("Bb4", 1.5), ("A4", 0.5), ("G4", 1), ("F4", 1), ("E4", 2), ("A3", 2), ("D4", 4)]
THEME_A2 = [("F4", 2), ("A4", 2), ("D5", 3), ("C5", 1), ("Bb4", 1), ("A4", 1), ("G4", 1), ("A4", 1), ("F4", 4),
            ("G4", 2), ("Bb4", 2), ("A4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("F4", 2), ("E4", 1), ("D4", 1), ("C#4", 2), ("E4", 2)]
PROG_A = ["Dm", "Bb", "Dm/C", "Dm", "Gm", "Bb", "A", "Dm"]
PROG_A2 = ["F", "Bb", "Gm", "Dm/F", "Gm", "C", "Dm", "A7"]
THEME_B = [("A4", 3), ("G4", 1), ("F4", 2), ("C5", 2), ("Bb4", 2), ("A4", 1), ("G4", 1), ("A4", 4),
           ("D5", 3), ("C5", 1), ("Bb4", 2), ("G4", 2), ("A4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("F4", 4)]
PROG_B = ["F", "Dm", "Gm", "F", "Bb", "Gm", "C7", "F"]
def major(theme, shift=0):
    """Theme A in D major: F -> F#, C -> C#, Bb -> B."""
    sw = {"F": "F#", "C": "C#", "Bb": "B"}
    out = []
    for nm, b in theme:
        if nm is None: out.append((nm, b)); continue
        p = nm.rstrip("0123456789"); o = nm[len(p):]
        out.append((sw.get(p, p) + o, b))
    return out
THEME_A_MAJ = major(THEME_A); THEME_A2_MAJ = major(THEME_A2)
PROG_A_MAJ = ["D", "G", "D/C#", "D", "G", "Bm", "A", "D"]
PROG_A2_MAJ = ["D/F#", "G", "Em", "D/F#", "G", "A", "Bm", "A7"]
THEME_B_D = [("F#5", 3), ("E5", 1), ("D5", 2), ("A5", 2), ("G5", 2), ("F#5", 1), ("E5", 1), ("F#5", 4),
             ("B5", 3), ("A5", 1), ("G5", 2), ("E5", 2), ("F#5", 1), ("E5", 1), ("D5", 1), ("C#5", 1), ("D5", 4)]
PROG_B_D = ["D", "Bm", "Em", "D", "G", "Em", "A7", "D"]

STR5 = [("cb", 28, 50), ("vc", 43, 62), ("vla", 53, 69), ("vln2", 60, 76), ("vln1", 64, 81)]       # string choir, bass first
WIND = [("bn", 38, 55), ("cl", 55, 70), ("ob", 62, 77), ("fl", 67, 86)]
BRASS = [("tuba", 30, 46), ("tbn", 45, 60), ("hn", 48, 62), ("tpt", 62, 76)]


# ------------------------------------------------------------------ I. Introduction (0-150 s, Largo)
def intro():
    s = Seg(0.0, 48)                                       # 5 s per bar, 30 bars
    organ([midi("D1"), midi("D2")], s.at(1), s.beats(4 * 6), 0.35, att=8.0, rel=4.0)
    tank(s.at(1, 1), midi("D1"), 0.45)
    play(s.at(1), "cb", midi("D2"), s.beats(16), 0.25, art="trem", att=5.0, rel=2.0)
    play(s.at(2), "vc", midi("D3"), s.beats(12), 0.22, art="trem", att=5.0, rel=2.0)
    perc(s.at(3), "scresc_long", 0.3)
    # the horn call: Theme A's first phrase, alone over the strings
    pv = pad(s, 5, ["Dm", "Dm", "Bb", "Bb", "Gm", "Gm", "A", "A"], STR5[1:], 0.2, hair=0.32)
    melody(s, 5, THEME_A[:8], "hn", 0.5, hairpin=0.55, copies=1, oct=-1)
    melody(s, 9, THEME_A[8:15], "hn", 0.52, copies=1, oct=-1)
    # the answer from far away (west end): the same head, a fifth higher, on trumpets
    melody(s, 13, [("A4", 2), ("E5", 2), ("D5", 1), ("C#5", 1), ("B4", 1), ("C#5", 1), ("A4", 4)], "west", 0.42, copies=2) if False else None
    for i, (nm, b, beat) in enumerate([("G4", 2, 0), ("D5", 2, 2), ("C5", 1, 4), ("Bb4", 1, 5), ("A4", 1, 6), ("Bb4", 1, 7), ("A4", 4, 8)]):
        ev_note(s.at(13, beat), "west", "tpt_sus", midi(nm), s.beats(b) + 0.15, 0.42, att=0.08, rel=0.6, rr=i)
    pv = pad(s, 13, ["Gm", "Gm", "Dm", "Dm"] + PROG_A[:4], STR5, 0.28, hair=0.45, prev=pv)
    melody(s, 17, THEME_A[:8], "vc", 0.5, hairpin=0.58)
    # everyone swells
    pad(s, 21, ["Dm", "F", "Bb", "Gm", "Dm/A", "A", "Dm", "A"], WIND, 0.3, hair=0.6, rr=20)
    pv = pad(s, 21, ["Dm", "F", "Bb", "Gm", "Dm/A", "A", "Dm", "A"], STR5, 0.42, hair=0.75, prev=pv, rr=30)
    pad(s, 25, ["Dm/A", "A", "Dm", "A"], BRASS, 0.35, hair=0.7, rr=40)
    melody(s, 21, THEME_A[:12], "vln1", 0.55, hairpin=0.8, oct=1)
    perc(s.at(25), "timp_roll", 0.6, g="timp"); tank(s.at(21), midi("D1"), 0.6); tank(s.at(27), midi("A1"), 0.8)
    perc(s.at(27), "crash", 0.75)
    # the dominant held, fading into the theme
    pad(s, 29, ["A", "A"], STR5, 0.45, hair=0.2, prev=pv, rr=50)
    organ([midi("A1"), midi("A2"), midi("E3"), midi("C#4")], s.at(29), s.beats(8), 0.4, att=1.0, rel=4.0)


# ------------------------------------------------------------------ II. Theme A (150-333 s, Andante)
def theme_a():
    s = Seg(150.0, 63)                                     # 3.81 s per bar, 48 bars
    # A1: cellos and horns in octaves; violas and second violins hold the harmony; basses pizzicato; harp
    pv = None
    for rep, (th, pr, b0) in enumerate([(THEME_A, PROG_A, 1), (THEME_A2, PROG_A2, 9)]):
        melody(s, b0, th, "vc", 0.55, hairpin=0.6, rr=rep * 40)
        melody(s, b0, th, "hn", 0.42, copies=1, oct=-1, rr=rep * 40 + 7)
        pv = pad(s, b0, pr, [("cb", 28, 45), ("vla", 50, 64), ("vln2", 57, 72)], 0.28, prev=pv, rr=rep * 10)
        for i, sym in enumerate(pr):                       # pizzicato basses on beats 1 and 3
            pcs, bp = chord(sym)
            for beat in (0, 2): play(s.at(b0 + i, beat), "cb", 36 + (bp - 0) % 12, 0.5, 0.45, art="pizz", rr=i + beat)
            for k, beat in enumerate((0, 1, 2, 3)):         # harp: a broken chord through the bar
                m = 60 + sorted(pcs)[k % len(pcs)] + 12 * (k // len(pcs))        # C4-based, so the pitch class is right
                ev_note(s.at(b0 + i, beat), "harp", "harp", m, s.beats(4 - beat), 0.35, rel=0.6, rr=i * 4 + k)
    # A2: the theme an octave up in the first violins and flutes, cellos sing a falling countermelody, horns hold chords
    COUNTER = [("A3", 4), ("G3", 2), ("F3", 2), ("E3", 4), ("F3", 2), ("G3", 2), ("Bb3", 4), ("A3", 2), ("G3", 2), ("E3", 2), ("C#3", 2), ("D3", 4)]
    for rep, (th, pr, b0) in enumerate([(THEME_A, PROG_A, 17), (THEME_A2, PROG_A2, 25)]):
        melody(s, b0, th, "vln1", 0.62, hairpin=0.72, oct=1, rr=rep * 50)
        melody(s, b0, th, "fl", 0.45, oct=1, copies=1, rr=rep * 50 + 3)
        melody(s, b0, COUNTER if rep == 0 else [(n, b) for n, b in COUNTER], "vc", 0.5, rr=rep * 50 + 9)
        pv = pad(s, b0, pr, [("cb", 28, 45), ("vla", 52, 66), ("vln2", 59, 74), ("hn", 48, 62)], 0.4, hair=0.55, prev=pv, rr=rep * 20)
        pad(s, b0, pr, [("tbn", 43, 57)], 0.22, rr=rep * 30)
    tank(s.at(17), midi("D1"), 0.55); perc(s.at(32), "timp_roll", 0.5, g="timp")
    # transition: Theme A's head climbs through a sequence, landing in F major
    seq = [("Bb", "Bb3"), ("Gm", "G3"), ("C", "C4"), ("F", "F3")]
    for i, (sym, start) in enumerate(seq):
        b0 = 33 + 2 * i; root = midi(start)
        third = 3 if sym.endswith("m") else 4
        fig = [(0, 2), (7, 2), (5, 1), (third, 1), (2, 1), (third, 1)]
        for j, (iv, bb) in enumerate(fig):
            play(s.at(b0, sum(x[1] for x in fig[:j])), "vln1", root + 12 + iv, s.beats(bb) + 0.15, 0.55 + 0.05 * i, rr=i * 6 + j)
        pv = pad(s, b0, [sym, sym], STR5[:3] + [("hn", 52, 66)], 0.42 + 0.05 * i, prev=None, rr=60 + i)
    # Theme B: oboe and clarinet, gentle, over hushed strings (F major)
    melody(s, 41, THEME_B, "ob", 0.5, copies=1)
    melody(s, 41, THEME_B, "cl", 0.38, oct=-1, copies=1, rr=5)
    pad(s, 41, PROG_B, [("cb", 29, 45), ("vc", 45, 60), ("vla", 53, 67), ("vln2", 60, 72)], 0.2, rr=70)
    tank(s.at(48, 2), midi("A1"), 0.35)


# ------------------------------------------------------------------ III. Scherzo (333-542 s, Allegro): experiment 53
def scherzo():
    s = Seg(333.0, 138)                                    # 1.74 s per bar, 120 bars
    P = json.load(open(os.path.join(LM, "experiments", "e53_predictions.json")))
    cells = {}
    for p in P:
        r = json.load(open(os.path.join(LM, p["run"]))); div = r["log"][-1]["step"] < r["config"]["steps"]
        c = p["run"].rsplit("_s", 1)[0]; cells.setdefault(c, []).append(div)
    cell_div = [sum(v) >= 2 for v in cells.values()]          # 24 cells, outcome by majority of 3 seeds
    assert len(cell_div) == 24
    BLOCK_D = ["Dm", "Dm", "Bb", "C", "Dm", "Dm", "Gm", "A"]
    BLOCK_F = PROG_B
    BUILD = ["Gm", "Gm", "Gm", "Gm", "A", "A", "A", "A", "Bb", "Bb", "Bb", "Bb", "C", "C", "C", "C", "D", "D", "D", "D", "A", "A", "A", "A"]
    prog = BLOCK_D * 6 + BLOCK_F * 3 + BUILD + PROG_A * 3
    assert len(prog) == 120
    pv = None
    for i, sym in enumerate(prog):
        bar = i + 1; pcs, bp = chord(sym); root = 38 + (bp - 2) % 12           # around D2-C#3
        heat = 0.5 + 0.35 * (bar > 72) + 0.1 * (bar > 96)
        # the engine: violas and cellos in driving eighths
        pat = [0, 0, 7, 0, 12, 0, 7, 0]
        for k, iv in enumerate(pat):
            play(s.at(bar, 0.5 * k), "vc", root + iv, 0.22, heat - 0.05 * (k % 2), art="short", rr=i * 8 + k, copies=2)
            if bar > 8: play(s.at(bar, 0.5 * k), "vla", root + 12 + (iv if iv != 12 else 7), 0.22, heat - 0.1, art="short", rr=i * 8 + k + 3)
        play(s.at(bar), "cb", root - 12 if root - 12 >= 28 else root, s.beats(2), heat, art="short", rr=i)
        # sustained winds and second violins hold the harmony every two bars
        pv = voices(pcs, bp, pv, [(38, 52), (60, 72), (64, 77), (67, 81)])
        for (g, m) in zip(["bn", "cl", "vln2", "fl"], pv): play(s.at(bar), g, m, s.beats(4) + 0.05, 0.32 + 0.2 * (bar > 72), att=0.1, rel=0.3, rr=i)
    # experiment 53: five bars per cell, in the runs' own order
    for c, div in enumerate(cell_div):
        b0 = 1 + 5 * c
        sym = prog[b0 - 1]; pcs, bp = chord(sym)
        if div:   # diverged: brass and timpani hits on 1 and the and-of-2, then a stab two bars later
            for bar, beat in ((b0, 0), (b0, 1.5), (b0 + 2, 0), (b0 + 3, 3)):
                pcs, bp = chord(prog[bar - 1])
                pvb = voices(pcs, bp, None, [(31, 45), (46, 58), (53, 65), (62, 74)])
                for (g, m) in zip(["tuba", "tbn", "hn", "tpt"], pvb): play(s.at(bar, beat), g, m, 0.35, 0.8, art="short", rr=c * 5 + int(beat))
                perc(s.at(bar, beat), "timp", 0.8, rr=c + int(beat), g="timp")
            if c % 3 == 0: perc(s.at(b0), "crash", 0.6, rr=c)
        else:     # healthy: pizzicato violins answer in thirds
            for k in range(6):
                m = 72 + sorted(pcs)[k % len(pcs)] - 12 * (k % 2)
                play(s.at(b0 + 1, 0.5 * k + 1), "vln1", m, 0.3, 0.5, art="pizz", rr=c * 6 + k)
    # Theme B in the trumpets over the F-major blocks (bars 49-72), augmented
    for rep in range(3):
        melody(s, 49 + 8 * rep, [(n, b) for n, b in THEME_B][:8 if rep < 2 else 17], "tpt", 0.55 + 0.08 * rep, copies=2, rr=rep * 20)
    # Theme A's head in trombones and horns over the return (bars 97-120), fortissimo
    for rep in range(3):
        melody(s, 97 + 8 * rep, THEME_A[:8], "tbn", 0.8, oct=-1, rr=rep * 10)
        melody(s, 97 + 8 * rep, THEME_A[:8], "hn", 0.75, oct=-1, rr=rep * 10 + 4)
        melody(s, 97 + 8 * rep, THEME_A[:8], "tpt", 0.7, rr=rep * 10 + 6)
        melody(s, 97 + 8 * rep, THEME_A[:8], "vln1", 0.75, oct=1, art="sus", rr=rep * 10 + 8)
    perc(s.at(73), "scresc_long", 0.5); perc(s.at(97), "crash", 0.9); tank(s.at(97), midi("D1"), 0.85)
    for b in (105, 113): perc(s.at(b), "crash", 0.7, rr=b)
    # the last four bars: tutti hits, D minor
    for bar, beat in ((119, 0), (119, 2), (120, 0)):
        for g, m in zip(["tuba", "tbn", "hn", "tpt", "vc", "vln1"], [38, 50, 57, 69, 50, 74]):
            play(s.at(bar, beat), g, m, 0.5, 0.95, art="short", rr=bar + int(beat))
        perc(s.at(bar, beat), "timp", 1.0, g="timp")
    perc(s.at(120), "crash", 1.0); tank(s.at(120), midi("D1"), 1.0)


# ------------------------------------------------------------------ IV. Chorale: the anchors (542-692 s)
def chorale():
    s = Seg(541.6, 56)                                     # 4.29 s per bar, 35 bars
    up = lambda th: [(midi(n) + 5 if n else None, b) for n, b in th]     # F major -> B-flat major
    TB = up(THEME_B); TB1, TB2 = TB[:8], TB[8:]
    PB = ["Bb", "Gm", "Cm", "Bb", "Eb", "Cm", "F7", "Bb"]
    bar = 1; pv = None
    for k in range(6):
        pins = 12 - 2 * k; gap = 0.5 * pins / 12               # the anchors: the echo comes 2 beats late, closing to together
        phr = PB[:4] if k % 2 == 0 else PB[4:]
        tune = TB1 if k % 2 == 0 else TB2
        lead, lead_g = ("tpt", "west") if k % 2 == 0 else ("hn", "east")
        # the tune: lead trumpet from the west end, or the horns from the east, alternating
        beat = 0.0
        for i, (m, b) in enumerate(tune):
            mm = m if lead == "tpt" else m - 12
            play(s.at(bar, beat), lead_g, mm, s.beats(b) + 0.15, 0.5 + 0.04 * k, att=0.1, rel=0.6, rr=k * 20 + i)
            beat += b
        prev = None
        for i, sym in enumerate(phr):
            pcs, bp = chord(sym); bpc = bp % 12
            prev = voices(pcs, bp, prev, [(34, 46), (46, 58), (53, 62), (58, 67)])
            for j, mm in enumerate(prev):                   # west chord on the beat, east echo `gap` of a bar later
                ev_note(s.at(bar + i), "west", ["tbn_sus", "tbn_sus", "tbn_sus", "tpt_sus"][j], mm + (12 if j == 3 else 0),
                        s.beats(4) + 0.05, 0.32 + 0.04 * k, att=0.25, rel=0.6, rr=k * 4 + i + j)
                ev_note(s.at(bar + i, 4 * gap), "east", ["tuba_sus", "hn_sus", "hn_sus", "hn_sus"][j], mm,
                        s.beats(4 * (1 - gap)) + 0.05, 0.3 + 0.04 * k, att=0.3, rel=0.6, rr=k * 4 + i + j + 2)
            organ([24 + bpc if bpc > 3 else 36 + bpc], s.at(bar + i), s.beats(4) + 0.1, 0.3, att=0.6, rel=0.8)
        pv = pad(s, bar, phr, STR5, 0.18 + 0.03 * k, prev=pv, rr=k * 9)
        tank(s.at(bar), 36 + chord(phr[0])[1], 0.35 + 0.05 * k)
        bar += 5 if k < 5 else 4
    # together at last, on B-flat
    for g, m in zip(["tuba", "tbn", "hn", "tpt"], [34, 50, 58, 70]): play(s.at(30), g, m, s.beats(20), 0.6, att=1.5, rel=3.0)
    pad(s, 30, ["Bb", "Eb/Bb", "Bb", "F/Bb", "Bb"], STR5, 0.4, hair=0.15, prev=pv, rr=99)
    melody(s, 30, [(midi("D5"), 4), (midi("C5"), 2), (midi("Bb4"), 2), (midi("C5"), 4), (midi("Bb4"), 8)], "vln1", 0.5, hairpin=0.25)
    organ([midi("Bb1"), midi("F2"), midi("Bb2"), midi("D3")], s.at(30), s.beats(20), 0.45, att=2.0, rel=4.0)


# ------------------------------------------------------------------ V. Pile-up and teardown (692-812 s): the lapse-meter trace
def teardown():
    s = Seg(691.6, 72)                                     # 3.33 s per bar, 36 bars
    d = json.load(open(os.path.join(LM, "results", "e34", "digits_plain_s0.json")))
    fine = {e["step"]: e for e in d["fine"]}
    ob0 = np.array(fine[0]["open_by_block"]); ob1 = np.array(fine[1]["open_by_block"]); ob2 = np.array(fine[2]["open_by_block"])
    stream = [fine[k]["stream"] for k in (0, 1, 2)]
    organ([midi("A1")], s.at(1), s.beats(4 * 24), 0.5, att=10.0, rel=0.3)
    perc(s.at(9), "timp_roll", 0.5, g="timp"); perc(s.at(17), "scresc_long", 0.8)
    # bars 1-16: harmony over a dominant pedal, gathering
    PROG = ["Bb/A", "A", "Gm/A", "A", "Dm/A", "A", "Bb/A", "A7", "Bb/A", "A", "F/A", "A", "Gm/A", "A7", "Bb/A", "A7"]
    pv = pad(s, 1, PROG, STR5, 0.25, hair=0.75, rr=200)
    pad(s, 5, PROG[4:], WIND, 0.25, hair=0.7, rr=220)
    pad(s, 9, PROG[8:], BRASS, 0.3, hair=0.75, rr=240)
    # bars 17-24: the pile-up. 94 players (one per block) converge onto one A, entering in order.
    groups = ["vln1", "vln2", "vla", "vc", "cb", "fl", "ob", "cl", "bn", "hn", "tpt", "tbn", "tuba"]
    Tk = s.at(25)
    for b in range(len(ob0)):
        g = groups[b % 13]; t = s.at(17) + (Tk - s.at(17)) * b / len(ob0) * 0.85
        stop = Tk + (s.beats(4) if ob1[b] < 0.5 * ob0[b] else s.beats(8) if ob2[b] < 0.5 * ob0[b] else s.beats(12))
        play(t, g, midi("A3"), stop - t, 0.55 + 0.4 * b / len(ob0), att=1.5, rel=0.2, copies=1, rr=b)
    tank(s.at(17), midi("A1"), 0.5)
    # bar 25: the kick
    for g, m in zip(groups, [81, 76, 69, 57, 45, 81, 81, 69, 45, 69, 69, 57, 45]):
        play(Tk, g, m, 0.5, 1.0, art="short", rr=1)
    perc(Tk, "bdrum", 1.0); perc(Tk, "timp", 1.0, g="timp"); perc(Tk, "gong", 1.0); perc(Tk, "crash", 1.0)
    tank(Tk, midi("A1"), 1.0, dur=22.0, pulse=0.002)
    # bars 26, 27: the stream falls 234 -> 105 -> 20 (data): the same chord at -7 and -21 dB, with the survivors
    for k, bar in ((1, 26), (2, 27)):
        gdb = stream[k] / stream[0]; ob = ob1 if k == 1 else ob2
        for b in range(0, len(ob0), 7):
            if ob[b] >= 0.5 * ob0[b]:
                play(s.at(bar), groups[b % 13], midi("A3"), 0.45, 0.9, art="short", gain=gdb, rr=b + k)
        perc(s.at(bar), "timp", 0.9 * gdb ** 0.5, g="timp", gain=gdb)
    # bars 28-36: what is left. Batch centring takes away the shared A; each survivor finds its own line again.
    perc(s.at(28), "gongscrape", 0.2)
    left = [b for b in range(len(ob0)) if ob2[b] >= 0.5 * ob0[b]]
    notes = ["D4", "F4", "A4", "D5", "A3", "F5", "A4", "D4"]
    for i, b in enumerate(left[:16]):
        g = ["vla", "vc", "vln2", "cl", "fl", "vln1", "hn", "ob"][i % 8]
        play(s.at(28 + (i % 4), (i * 1.5) % 4), g, midi(notes[i % 8]), s.beats(6), 0.2 + 0.015 * i, att=1.0, rel=1.5, copies=1, rr=i)
    melody(s, 33, [("A4", 4), ("D5", 4), ("C#5", 2), ("E5", 2), ("D5", 4)], "solo", 0.45, gain=1.4)
    ev_note(s.at(33), "harp", "harp", midi("D4"), 3.0, 0.3, rel=2.0)


# ------------------------------------------------------------------ VI. Adagio: envelopment (812-998 s), D major
IBA1 = {"5xFAD": [2.3, 3.0, 3.6, 4.3], "Cass4": [1.5, 1.9, 2.1, 2.4]}     # read off the figure (approximate)
def adagio():
    s = Seg(811.6, 54)                                     # 4.44 s per bar, 42 bars
    CONT = [("A5", 2), ("B5", 1), ("C#6", 1), ("D6", 3), ("A5", 1), ("B5", 2), ("G5", 2), ("F#5", 2), ("E5", 2), ("D5", 1), ("E5", 1),
            ("F#5", 1), ("G5", 1), ("A5", 4), ("G5", 2), ("F#5", 1), ("E5", 1), ("D5", 2), ("C#5", 2), ("D5", 4)]
    PROG_C = ["D/F#", "G", "Bm", "G", "D/A", "A", "Em", "A7", "D"]
    sections = [(1, THEME_B_D, PROG_B_D), (9, CONT, PROG_C[:8]), (17, THEME_A_MAJ, PROG_A_MAJ), (25, THEME_A2_MAJ, PROG_A2_MAJ),
                (33, THEME_B_D, PROG_B_D)]
    pv = None
    for k, (b0, th, pr) in enumerate(sections):
        half = 0 if b0 < 21 else 1                         # the first half compact, the second diffuse (the Cass4 loss)
        oct = 1 if th in (THEME_A_MAJ, THEME_A2_MAJ) else 0
        melody(s, b0, th, "solo", 0.55 + 0.05 * (k == 3), oct=oct, gain=1.5 * (1.0 if half == 0 else 10 ** (-2.4 / 20)), rr=k * 30)
        rings = IBA1["5xFAD" if half == 0 else "Cass4"]
        push = 1.0 if half == 0 else 1.6
        # close voicing (within an octave) when compact; open voicing (spread over two octaves) when diffuse
        rng = [(38, 50), (55, 64), (59, 67), (62, 71)] if half == 0 else [(31, 45), (45, 57), (57, 69), (69, 81)]
        for i, sym in enumerate(pr):
            pcs, bp = chord(sym); pv = voices(pcs, bp, pv, rng)
            for r, (g, m) in enumerate(zip(["cb", "vc", "vla", "vln2"], pv)):
                cnt = rings[r] / 2.3                       # how many players gather at this ring, from the figure
                dpos = SEAT[g][0] * (1 + 0.05 * r) * push
                ev_note(s.at(b0 + i), g, ART[INST[g]]["sus"], m, s.beats(4) + 0.3, 0.26 + 0.04 * cnt, att=0.5, rel=1.2,
                        copies=max(1, int(round(cnt))), rr=k * 40 + i * 4 + r, pos=(dpos, SEAT[g][1] * push ** 0.5))
            for j in range(4):                              # harp arpeggio, rising
                m = 48 + sorted(pcs)[j % len(pcs)] + 12 * (j // 3)
                ev_note(s.at(b0 + i, j), "harp", "harp", m, s.beats(4 - j), 0.28, rel=0.6, rr=k * 32 + i * 4 + j)
            if half == 1:                                   # the halo: diffuse amyloid (6E10/ThioS 0.5 -> 1.4), chord tones, far away
                for r, near in enumerate((81, 66)):
                    hm = min([x for x in range(near - 6, near + 7) if x % 12 in pcs], key=lambda x: abs(x - near))
                    ev_note(s.at(b0 + i), "east", "vln_trem" if r == 0 else "vla_trem", hm, s.beats(4) + 0.2, 0.2, att=0.8, rel=0.8,
                            copies=2, gain=1.4, rr=k * 9 + i + r)
    pad(s, 17, PROG_A_MAJ + PROG_A2_MAJ, [("hn", 50, 64)], 0.25, rr=300)
    tank(s.at(17), midi("D1"), 0.35); tank(s.at(41), midi("D1"), 0.3)
    organ([midi("D2"), midi("A2"), midi("F#3")], s.at(41), s.beats(8), 0.3, att=3.0, rel=4.0)


# ------------------------------------------------------------------ VII. Finale (998-1188 s), D major
def finale():
    s = Seg(998.3, 66)                                     # 3.64 s per bar, 52 bars
    # bars 1-8: fanfare on Theme A's head, timpani, building
    for rep in range(2):
        melody(s, 1 + 4 * rep, THEME_A_MAJ[:8], "tpt", 0.6 + 0.15 * rep, copies=2, rr=rep * 10)
        melody(s, 1 + 4 * rep, THEME_A_MAJ[:8], "hn", 0.55 + 0.15 * rep, oct=-1, rr=rep * 10 + 5)
    pad(s, 1, ["D", "G", "D", "A", "D", "G", "Bm", "A"], BRASS[:2] + STR5[:3], 0.45, hair=0.8, rr=400)
    perc(s.at(1), "timp_roll", 0.6, g="timp"); perc(s.at(5), "timp_roll", 0.8, g="timp"); perc(s.at(8), "scresc_short", 0.7)
    tank(s.at(1), midi("D1"), 0.6)
    # bars 9-24: Theme A in D major, full orchestra and organ
    pv = None
    for rep, (th, pr, b0) in enumerate([(THEME_A_MAJ, PROG_A_MAJ, 9), (THEME_A2_MAJ, PROG_A2_MAJ, 17)]):
        melody(s, b0, th, "vln1", 0.85, oct=1, rr=rep * 60)
        melody(s, b0, th, "tpt", 0.7, copies=2, rr=rep * 60 + 5)
        melody(s, b0, th, "fl", 0.6, oct=1, copies=2, rr=rep * 60 + 9)
        cm = [("A3", 4), ("B3", 4), ("A3", 2), ("G3", 2), ("F#3", 4), ("G3", 4), ("D4", 4), ("C#4", 4), ("A3", 4)] if rep == 0 else \
             [("A3", 4), ("B3", 4), ("B3", 2), ("G3", 2), ("F#3", 4), ("G3", 4), ("E4", 4), ("D4", 4), ("C#4", 4)]
        melody(s, b0, cm, "hn", 0.7, rr=rep * 60 + 13)
        pv = pad(s, b0, pr, STR5[:4] + [("tbn", 45, 60), ("tuba", 30, 45)], 0.7, hair=0.85, prev=pv, rr=420 + rep * 10)
        for i, sym in enumerate(pr):
            pcs, bp = chord(sym); organ([24 + bp if bp > 3 else 36 + bp, 48 + bp, 60 + sorted(pcs)[1]], s.at(b0 + i), s.beats(4) + 0.3, 0.75, att=0.3, rel=1.0)
        perc(s.at(b0), "crash", 0.9, rr=rep); tank(s.at(b0), midi("D1"), 0.9)
    # bars 25-36: the thinning. Sections fall silent in the order the weakest Metatron connections go (78 -> 28 edges);
    # what remains is quiet: Theme B on one flute, over the strings that are left.
    order = ["tuba", "tbn", "tpt", "hn", "bn", "ob", "cl", "cb", "vla"]
    THIN = ["G", "D/F#", "Em", "A"] + PROG_B_D
    alive = ["cb", "vc", "vla", "vln2", "vln1", "hn", "tbn", "tuba", "tpt", "bn", "cl", "ob"]
    prev = None
    for i, sym in enumerate(THIN):
        if i < len(order) and order[i] in alive: alive.remove(order[i])
        pcs, bp = chord(sym)
        parts = [(g, lo, hi) for g, lo, hi in STR5 + BRASS + WIND if g in alive]
        parts = sorted(parts, key=lambda x: x[1])
        prev = voices(pcs, bp, None, [(lo, hi) for _, lo, hi in parts])
        for (g, _, _), m in zip(parts, prev): play(s.at(25 + i), g, m, s.beats(4) + 0.3, 0.5 - 0.03 * i, att=0.5, rel=1.0, rr=500 + i)
    melody(s, 29, THEME_B_D, "fl", 0.45, oct=-1, copies=1, rr=7)
    # bars 37-48: everyone returns; Theme A's head augmented in the brass; a deceptive turn to B-flat, then home
    FIN = ["D", "G", "Em", "A", "Bb", "A", "A7", "D", "G", "Em", "A", "D"]
    pv = pad(s, 37, FIN, STR5, 0.6, hair=0.95, rr=600)
    pad(s, 37, FIN, WIND, 0.5, hair=0.9, rr=620)
    pad(s, 37, FIN, BRASS, 0.6, hair=1.0, rr=640)
    aug = [(n, 2 * b) for n, b in THEME_A_MAJ[:8]]
    melody(s, 37, aug, "tbn", 0.85, oct=-1, rr=650); melody(s, 37, aug, "hn", 0.8, oct=-1, rr=655)
    melody(s, 37, aug, "tpt", 0.8, rr=658)
    melody(s, 37, [(n, 2 * b) for n, b in THEME_A_MAJ[:8]], "vln1", 0.85, oct=1, rr=660)
    for i, sym in enumerate(FIN):
        pcs, bp = chord(sym); organ([24 + bp if bp > 3 else 36 + bp, 36 + bp, 48 + sorted(pcs)[0], 60 + sorted(pcs)[1], 72 + sorted(pcs)[2]],
                                     s.at(37 + i), s.beats(4) + 0.3, 0.8 + 0.015 * i, att=0.3, rel=1.0)
    perc(s.at(41), "crash", 0.85); perc(s.at(45), "timp_roll", 0.9, g="timp"); perc(s.at(45), "scresc_long", 0.8)
    tank(s.at(41), midi("Bb1"), 0.8); tank(s.at(45), midi("A1"), 0.9)
    # bars 49-52: the final D major chord, everything, the Tank; then the stone
    for g, m in zip(["cb", "vc", "vla", "vln2", "vln1", "bn", "cl", "ob", "fl", "hn", "tbn", "tuba", "tpt"],
                    [38, 50, 62, 66, 74, 50, 69, 78, 86, 62, 54, 38, 74]):
        play(s.at(49), g, m, s.beats(10), 1.0, att=0.15, rel=0.7, rr=700)
    organ([midi("D1"), midi("D2"), midi("A2"), midi("D3"), midi("F#3"), midi("A3"), midi("D4"), midi("F#4"), midi("A4"), midi("D5")],
          s.at(49), s.beats(10), 1.0, att=0.2, rel=0.8)
    perc(s.at(49), "crash", 1.0); perc(s.at(49), "gong", 0.9); perc(s.at(49), "bdrum", 1.0); perc(s.at(49), "timp_roll", 1.0, g="timp")
    tank(s.at(49), midi("D1"), 1.0, dur=22.0)
    tank(s.at(52, 2), midi("D1"), 0.18, dur=12.0)


def build():
    EV.clear(); HARM.clear(); intro(); theme_a(); scherzo(); chorale(); teardown(); adagio(); finale()
    EV.sort(key=lambda e: e["t"]); return EV


if __name__ == "__main__":
    ev = build()
    k = {}
    for e in ev: k[e["k"]] = k.get(e["k"], 0) + 1
    last = max(e["t"] + e.get("dur", 0) for e in ev)
    print(len(ev), "events", k, "last ends at", round(last, 1), "s")
    json.dump(ev, open(os.path.join(HERE, "score.json"), "w"))
    # chord-tone audit: accompaniment built from chords (harp, organ, pizzicato) must use the chord sounding at its start
    acc = [e for e in ev if e["k"] == "note" and (e["inst"] in ("harp", "organ_man", "organ_ped") or e["inst"].endswith("pizz"))]
    bad = []
    for e in acc:
        pc = int(round(69 + 12 * np.log2(e["f"] / 440))) % 12
        cover = [hh for hh in HARM if hh[0] - 0.05 <= e["t"] < hh[1] - 0.05]
        if cover and not any(pc in hh[2] for hh in cover): bad.append((round(e["t"], 2), e["inst"], pc, [hh[3] for hh in cover]))
    print(f"chord-tone audit: {len(acc)} accompaniment notes, {len(bad)} outside the chord", bad[:10])
