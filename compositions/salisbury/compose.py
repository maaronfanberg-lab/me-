"""The score of LAPSE (20 minutes), generated from data. Every event is a pure function of the data and fixed seeds.

Pitch: the 13 sections are the 13 circles of Metatron's Cube. Each owns one partial of the overtone series of the
Tank's lowest mode, D1 = 36.708 Hz (partials 1-13, so the true, untempered 7th, 11th and 13th partials sound).
The Tank's own inharmonic modes (computed from its physics) are the other pitch world.

  I    Fully connected   0-195 s    the 78 edges of K13, 2.5 s each, in Metatron order
  II   Flow regimes      195-395    experiment 53's 72 runs: kick, product rule, outcome
  III  Anchors           395-595    the Tank with 12 pins, removed one at a time; its true modes, called across the nave
  IV   Teardown          595-795    lapse-meter trace digits_plain_s0: 94 blocks as 94 players; stream and gates
  V    Envelopment       795-995    solo violin; rings of players from the Cass4 figure; melody from the EEG paper's table 3
  VI   Detection         995-1200   78 edges thinned to 28 (weakest first, never disconnecting); noise becomes signal
"""
import os, json, re, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LM = os.path.join(HERE, "..", "..", "experiments", "lapse-meter")
F0 = 36.708                    # D1: the Tank's lowest mode
TOTAL = 1200.0

# 13 Metatron nodes: (name, sustained inst, short inst, partial, distance m, pan, copies)
NODES = [
    ("tank",     None,       None,        1, 15.0,  0.00, 1),
    ("cellos",   "vc_sus",   "vc_spic",   6, 14.0, -0.35, 2),
    ("violas",   "vla_sus",  "vla_spic",  8, 15.0,  0.35, 2),
    ("violins",  "vln_sus",  "vln_spic", 12, 16.0, -0.70, 3),
    ("horns",    "hn_sus",   "hn_stac",   7, 18.0,  0.60, 3),
    ("clarinets","cl_sus",   "cl_stac",   9, 17.0, -0.15, 2),
    ("bassoons", "bn_sus",   "bn_sus",    4, 17.0,  0.15, 2),
    ("basses",   "cb_sus",   "cb_pizz",   2, 30.0, -0.20, 3),
    ("tubas",    "tuba_sus", "tuba_stac", 3, 28.0,  0.85, 2),
    ("trombones","tbn_sus",  "tbn_stac",  5, 28.0, -0.85, 3),
    ("trumpets", "tpt_sus",  "tpt_stac", 10, 40.0,  0.10, 3),
    ("oboes",    "ob_sus",   "ob_sus",   11, 32.0,  0.30, 2),
    ("flutes",   "fl_sus",   "fl_stac",  13, 35.0, -0.40, 2),
]
EXTRA = {"organ": (24.0, 0.0), "solo": (12.0, 0.0), "perc": (22.0, 0.05), "harp": (16.0, 0.55),
         "ring": (15.0, 0.0), "west": (40.0, 0.15), "east": (34.0, -0.1)}
RANGE = {"vc_sus": (65, 660), "vc_spic": (65, 660), "vc_pizz": (65, 660), "vla_sus": (131, 1100), "vla_spic": (131, 1100),
         "vla_pizz": (131, 1100), "vln_sus": (196, 1400), "vln_spic": (196, 1400), "vln_pizz": (196, 1400), "vln_trem": (196, 1400),
         "vla_trem": (131, 1100), "vc_trem": (65, 660),
         "hn_sus": (60, 700), "hn_stac": (60, 700), "cl_sus": (147, 1400), "cl_stac": (147, 1400), "bn_sus": (58, 600),
         "cb_sus": (41, 330), "cb_pizz": (41, 330), "tuba_sus": (44, 350), "tuba_stac": (44, 350), "tbn_sus": (58, 500),
         "tbn_stac": (58, 500), "tpt_sus": (175, 1050), "tpt_stac": (175, 1050), "ob_sus": (233, 1400), "fl_sus": (262, 2000),
         "fl_stac": (262, 2000), "solo_vln": (196, 2400), "harp": (40, 3000), "organ_man": (65, 2000), "organ_ped": (32, 200),
         "glock": (392, 4000)}


def fit(inst, f, pref=None):
    """Move f by whole octaves into the instrument's range (pitch class kept exactly), nearest to pref if given."""
    lo, hi = RANGE[inst]; c = [f * 2 ** k for k in range(-6, 7) if lo <= f * 2 ** k <= hi]
    if not c: return min(max(f, lo), hi)
    return min(c, key=lambda x: abs(np.log2(x / (pref or np.sqrt(lo * hi)))))


EV = []  # the score


def note(t, group, inst, freq, dur, dyn, att=0.0, rel=1.2, copies=1, gain=1.0, rr=0):
    EV.append(dict(k="note", t=float(t), g=group, inst=inst, f=float(freq), dur=float(dur), dyn=float(np.clip(dyn, 0, 1)),
                   att=att, rel=rel, copies=copies, gain=gain, rr=rr))


def tank(t, amp, pins=(), kT=None, dur=16.0, pulse=0.004):
    EV.append(dict(k="tank", t=float(t), g="tank", amp=float(amp), pins=list(pins), kT=kT, dur=dur, pulse=pulse))


def perc(t, group, kind, dyn, rr=0, gain=1.0):
    EV.append(dict(k="perc", t=float(t), g=group, kind=kind, dyn=float(np.clip(dyn, 0, 1)), rr=rr, gain=gain))


def node_note(t, n, dur, dyn, freq=None, short=False, att=0.6, rel=1.5, gain=1.0, rr=0, octave_pref=None):
    name, sus, sh, p, d, pan, cp = NODES[n]
    if n == 0:
        tank(t, 0.3 + 0.7 * dyn); return
    inst = sh if short else sus
    f = freq if freq is not None else F0 * p
    note(t, name, inst, fit(inst, f, octave_pref or F0 * p), dur, dyn, att=0.02 if short else att, rel=0.4 if short else rel,
         copies=cp, gain=gain, rr=rr)


def metatron_edges():
    """K13 in Metatron order: centre-inner, inner ring, inner-outer, outer ring, centre-outer (6+15+36+15+6 = 78)."""
    inner, outer = list(range(1, 7)), list(range(7, 13))
    E = [(0, i) for i in inner]
    E += [(a, b) for i, a in enumerate(inner) for b in inner[i + 1:]]
    E += [(a, b) for a in inner for b in outer]
    E += [(a, b) for i, a in enumerate(outer) for b in outer[i + 1:]]
    E += [(0, o) for o in outer]
    assert len(E) == 78 and len(set(E)) == 78
    return E


def metatron_xy():
    """Circle centres of Metatron's Cube: centre, inner hexagon (radius 1), outer hexagon (radius 2), same angles."""
    xy = [(0.0, 0.0)]
    for r in (1, 2):
        for k in range(6): a = np.pi / 2 + k * np.pi / 3; xy.append((r * np.cos(a), r * np.sin(a)))
    return np.array(xy)


# ---------------------------------------------------------------- I. Fully connected (0-195 s)
def mov1():
    E = metatron_edges(); rng = np.random.default_rng(1)
    note(0.0, "organ", "organ_ped", fit("organ_ped", F0, 37), 34.0, 0.25, att=6.0, rel=6.0)       # pedal D1 from silence
    tank(4.0, 0.35)
    entered = set()
    for e, (a, b) in enumerate(E):
        t = 6.0 + e * 2.5; prog = e / 77
        dyn = 0.18 + 0.62 * prog ** 1.3
        for k, n in enumerate((a, b)):
            entered.add(n)
            node_note(t + 1.25 * k, n, 4.5 + 3 * prog, dyn, att=0.8 + 0.6 * (1 - prog), rel=2.0, rr=e)
        if e % 13 == 12: note(t, "organ", "organ_ped", fit("organ_ped", F0, 37), 30.0, 0.25 + 0.5 * prog, att=3.0, rel=5.0)
    # the full overtone chord: all 13 partials, crescendo to fortissimo
    t0 = 6.0 + 78 * 2.5 - 12.0
    for n in range(1, 13): node_note(t0 + 0.3 * n, n, 14.0, 0.95, att=6.0, rel=4.0, rr=n)
    note(t0, "organ", "organ_ped", fit("organ_ped", F0, 37), 16.0, 0.9, att=4.0, rel=5.0)
    for p in (2, 3, 4, 6, 8): note(t0 + 1.0, "organ", "organ_man", fit("organ_man", F0 * p, F0 * p), 15.0, 0.85, att=5.0, rel=5.0)
    perc(t0 + 8.0, "perc", "timp_roll", 0.9)
    tank(t0 + 12.0, 1.0)


# ---------------------------------------------------------------- II. Flow regimes (195-395 s)
def mov2():
    P = json.load(open(os.path.join(LM, "experiments", "e53_predictions.json")))
    T0, dt = 195.0, 200.0 / len(P); rng = np.random.default_rng(2)
    kicks = np.log10([max(p["kick"], 1) for p in P]); kl, kh = kicks.min(), kicks.max()
    div_so_far = 0
    for i, p in enumerate(P):
        r = json.load(open(os.path.join(LM, p["run"])))
        diverged = r["log"][-1]["step"] < r["config"]["steps"]
        t = T0 + i * dt; x = (np.log10(max(p["kick"], 1)) - kl) / (kh - kl + 1e-9)      # 0..1 position of this kick
        partial = int(4 + round(x * 12))                                                   # louder kick, higher partial
        if diverged:
            div_so_far += 1
            # slug: a brass plug on the run's partial, timpani, and the Tank
            for n in (9, 4, 10):
                node_note(t, n, 0.6, 0.55 + 0.4 * x, freq=F0 * partial, short=True, rr=i)
            perc(t, "perc", "timp", 0.5 + 0.5 * x, rr=i)
            if p["prod"] > 735 * 4: tank(t + 0.05, 0.25 + 0.5 * x)
        else:
            # bubbly: a scatter of short string notes around the run's partial; more of them for a bigger kick
            m = 3 + int(round(x * 7))
            for j in range(m):
                q = partial + int(rng.integers(-2, 3)); q = max(2, q)
                inst = ["vln_pizz", "vla_pizz", "vc_pizz", "harp"][j % 4]
                grp = {"vln_pizz": "violins", "vla_pizz": "violas", "vc_pizz": "cellos", "harp": "harp"}[inst]
                note(t + rng.uniform(0, dt * 0.9), grp, inst, fit(inst, F0 * q, 330), 0.5, 0.35 + 0.35 * x, rel=0.6, copies=1, rr=i + j)
        if p["product_says"] and not diverged:
            # a false alarm: the rule said "diverges" and it did not. An unresolved 11th-partial question in the winds.
            note(t, "clarinets", "cl_sus", fit("cl_sus", F0 * 11, 400), dt * 2.5, 0.3, att=0.8, rel=2.0, copies=1)
            note(t + 0.4, "flutes", "fl_sus", fit("fl_sus", F0 * 13, 950), dt * 2.2, 0.25, att=0.8, rel=2.0, copies=1)
        if i % 6 == 0:  # the drone underneath grows with the number of divergences so far
            note(t, "basses", "cb_sus", fit("cb_sus", F0 * 2, 73), dt * 6.5, 0.2 + 0.6 * div_so_far / 36, att=2.0, rel=3.0, copies=3)
            note(t, "cellos", "vc_sus", fit("vc_sus", F0 * 3, 110), dt * 6.5, 0.15 + 0.5 * div_so_far / 36, att=2.0, rel=3.0, copies=2)


# ---------------------------------------------------------------- III. Anchors (395-595 s)
def mov3():
    from tank import Tank
    tk = Tank(); kT = tk.tuned_kT(F0); m = tk.m
    pins = []
    for r in (1, 2, 3, 4, 5, 6): pins += [m["rings"][r][1], m["rings"][r][5]]
    T0, stage = 395.0, 200.0 / 13
    west = [10, 9, 8]; east = [11, 12, 7]; inner = [1, 2, 3, 4, 5, 6]
    for s in range(13):
        k = 12 - s; tk.pins = set(pins[:k]); M = tk.modes(F0, kT)
        fr = np.sort(M["s"].imag / (2 * np.pi)); fr = fr[fr > 5][:6]
        t = T0 + s * stage
        tank(t, 0.55, pins=pins[:k], kT=kT, dur=18.0)
        # the loop: a call from the west answered from the east; the answer's distance and delay shrink as anchors go
        delay = 6.0 * (k / 12) + 0.8
        for j, f in enumerate(fr[:4]):
            call = west[j % 3]; answer = east[j % 3] if k > 4 else inner[j % 6]
            g_call = "west" if call == 10 else NODES[call][0]
            node_note(t + 1.0 + 1.7 * j, call, 5.0, 0.5 + 0.03 * j, freq=f, att=0.8, rel=2.5, rr=s * 7 + j)
            node_note(t + 1.0 + 1.7 * j + delay, answer, 5.0, 0.45, freq=f, att=0.8, rel=2.5, rr=s * 7 + j + 3)
        # the strings hold the current lowest mode in octaves: the body's own pitch, sinking as it comes loose
        note(t, "cellos", "vc_sus", fit("vc_sus", fr[0], 110), stage + 2, 0.35, att=3.0, rel=3.0, copies=2)
        note(t, "basses", "cb_sus", fit("cb_sus", fr[0], 55), stage + 2, 0.35, att=3.0, rel=3.0, copies=3)
        note(t + 2, "violas", "vla_trem", fit("vla_trem", fr[1], 250), stage, 0.22, att=3.0, rel=3.0, copies=2)


# ---------------------------------------------------------------- IV. Pile-up and teardown (595-795 s)
def mov4():
    d = json.load(open(os.path.join(LM, "results", "e34", "digits_plain_s0.json")))
    fine = {e["step"]: e for e in d["fine"]}
    ob0 = np.array(fine[0]["open_by_block"]); nb = len(ob0)        # 94 blocks: 94 players
    order = [n for n in range(1, 13)]
    T0, Tk = 595.0, 685.0
    players = []
    for b in range(nb):
        n = order[b % 12]; t = T0 + b * (Tk - T0 - 4) / nb
        # the pile-up: everyone converges on the shared direction, D, in their own octave
        name, sus, sh, p, dd, pan, cp = NODES[n]
        f = fit(sus, F0 * 2, F0 * p)
        lvl = 0.25 + 0.7 * (b / nb) * float(ob0[b]) / max(ob0.max(), 1e-9)
        players.append((b, n, f, t, lvl))
    stream = {s: fine[s]["stream"] for s in (0, 1, 2, 3)}
    for b, n, f, t, lvl in players:
        # each player holds until its block's gates close (step 1 or 2), at the level the stream allows
        o1, o2 = fine[1]["open_by_block"][b], fine[2]["open_by_block"][b]
        stop = Tk + (3.0 if o1 < 0.5 * ob0[b] else 6.0 if o2 < 0.5 * ob0[b] else 9.0)
        name, sus = NODES[n][0], NODES[n][1]
        note(t, name, sus, f, stop - t, lvl, att=2.5, rel=0.25, copies=1, rr=b)
    note(T0, "organ", "organ_ped", fit("organ_ped", F0, 37), Tk - T0 + 9, 0.7, att=20.0, rel=0.4)
    for p in (2, 4, 8): note(T0 + 30, "organ", "organ_man", fit("organ_man", F0 * p, F0 * p), Tk - T0 - 21, 0.8, att=25.0, rel=0.3)
    # the kick: one tutti strike, the Tank at full force
    for n in range(1, 13): node_note(Tk, n, 0.5, 1.0, freq=F0 * 2, short=True, rr=n)
    perc(Tk, "perc", "bdrum", 1.0); perc(Tk, "perc", "timp", 1.0); tank(Tk, 1.0, dur=22.0, pulse=0.002)
    # steps 1 and 2: the stream falls 234 -> 105 -> 20 (data); the survivors play at that level
    for s, tt in ((1, Tk + 3.0), (2, Tk + 6.0)):
        g = stream[s] / stream[0]
        for n in range(1, 13): node_note(tt, n, 0.4, 0.95 * g ** 0.5, freq=F0 * 2, short=True, gain=g, rr=n + 13 * s)
    # aftermath: steps 3..300 over the remaining time. Batch centring removes the shared D, and each surviving
    # player returns to its own partial; the texture grows back as the training loss falls (data).
    ta, tb = Tk + 10.0, 793.0
    steps = sorted(k for k in fine if k >= 3)
    losses = np.array([fine[k]["train_loss"] for k in steps]); L0 = np.log(losses.max()); L1 = np.log(losses.min())
    keyed = [k for k in steps if "open_by_block" in fine[k] and k >= 10]
    for i, k in enumerate(keyed):
        t = ta + (tb - ta - 8) * (k - 10) / (keyed[-1] - 10 + 1e-9)
        learned = (L0 - np.log(fine[k]["train_loss"])) / (L0 - L1 + 1e-9)
        ob = np.array(fine[k]["open_by_block"])
        live = [b for b in range(nb) if ob[b] > 0.35][:: max(1, int(len(ob) / 10))]
        for j, b in enumerate(live[:8]):
            n = order[b % 12]; p = NODES[n][3]
            node_note(t + 0.6 * j, n, 6.0, 0.18 + 0.55 * learned, freq=F0 * p, att=1.2, rel=2.5, rr=k + j)
    tank(tb - 9, 0.3)


# ---------------------------------------------------------------- V. Envelopment (795-995 s)
TABLE3 = [  # EEG paper (Liang et al. 2022) Table 3: medians, controls (PC) and epilepsy (PE), PLI, full band
    (1.13, 1.16), (0.18, 0.18), (1.12, 1.14), (0.24, 0.25), (2.60, 2.91), (0.38, 0.49), (2.59, 2.82), (0.51, 0.66),
    (1.64, 1.64), (0.03, 0.04), (1.63, 1.64), (0.04, 0.05), (0.44, 0.45), (0.04, 0.05), (0.44, 0.45), (0.06, 0.07),
    (0.96, 1.09), (0.19, 0.26), (0.94, 1.04), (0.23, 0.32)]
IBA1 = {"5xFAD": [2.3, 3.0, 3.6, 4.3], "Cass4": [1.5, 1.9, 2.1, 2.4]}    # read off the figure (approximate)
RINGS_UM = [1, 10, 15, 20]


def mov5():
    vals = np.log([v for pair in TABLE3 for v in pair]); lo, hi = vals.min(), vals.max()
    to_partial = lambda v: int(8 + round((np.log(v) - lo) / (hi - lo) * 8))       # partials 8..16: D4..D5
    T0 = 795.0
    for half, (key, col, spread, push, solo_gain, halo) in enumerate(
            [("5xFAD", 0, 1, 1.0, 1.0, 0.5), ("Cass4", 1, 3, 1.6, 10 ** (-2.4 / 20), 1.4)]):
        t = T0 + half * 100.0
        ring_players = [int(round(3 * r)) for r in IBA1[key]]
        for i, row in enumerate(TABLE3):
            q = to_partial(row[col]); f = F0 * q; tt = t + i * 5.0
            note(tt, "solo", "solo_vln", fit("solo_vln", f, 600), 5.6, 0.62, att=0.35, rel=1.6, gain=1.5 * solo_gain, copies=1, rr=i)
            # the rings: close rings tight around her pitch, outer rings wider; in the second half they move away
            for r, (um, cnt) in enumerate(zip(RINGS_UM, ring_players)):
                for c in range(cnt // 3 + 1):
                    off = (r * spread) * (1 if c % 2 == 0 else -1)
                    qq = max(2, q + off)
                    inst = ["vln_sus", "vla_sus", "vc_sus", "vln_sus"][r]
                    EV.append(dict(k="note", t=tt + 0.15 * r, g=f"ring{r}_{half}", inst=inst, f=fit(inst, F0 * qq, 300 if r == 2 else 500),
                                   dur=5.4, dyn=0.30 + 0.08 * (3 - r), att=1.0, rel=2.0, copies=1, gain=0.8, rr=i + r + c,
                                   pos=(12.0 + um * 0.3 * push, (-0.6 + 0.4 * r) * (1 if c % 2 == 0 else -1))))
        # the halo: diffuse amyloid around the core (6E10/ThioS ratio 0.5 -> 1.4): tremolo strings far away
        for i in range(0, 20, 4):
            note(t + i * 5.0, "east", "vln_trem", fit("vln_trem", F0 * 16, 600), 20.0, 0.12 + 0.12 * halo, att=4.0, rel=4.0, copies=2,
                 gain=halo)
    tank(T0 + 99.0, 0.4); tank(T0 + 198.0, 0.3)


# ---------------------------------------------------------------- VI. Detection (995-1200 s)
def mov6():
    from tank import Tank
    E = metatron_edges(); xy = metatron_xy()
    w = {e: 1.0 / np.linalg.norm(xy[e[0]] - xy[e[1]]) for e in E}
    live = set(E); removed = []

    def lam2(edges):
        Lp = np.zeros((13, 13))
        for a, b in edges: Lp[a, a] += 1; Lp[b, b] += 1; Lp[a, b] -= 1; Lp[b, a] -= 1
        return np.sort(np.linalg.eigvalsh(Lp))[1]
    for e in sorted(E, key=lambda e: (w[e], e)):          # weakest (longest) first
        if len(removed) == 50: break
        trial = live - {e}
        if lam2(trial) > 1e-9: live = trial; removed.append(e)
    assert len(live) == 28, len(live)
    tk = Tank(); M = tk.modes(F0); modes = np.sort(M["s"].imag / (2 * np.pi)); modes = modes[modes > 30]
    T0, T1 = 995.0, 1170.0; step = (T1 - T0) / 50
    for i in range(51):
        t = T0 + i * step; frac = i / 50
        edges = sorted(live | set(removed[i:]))                # edges still sounding at this point
        # the pairs currently sounding: a rotating subset of the live edges
        for j, (a, b) in enumerate(edges[i % 3::6][:7]):
            for k, n in enumerate((a, b)):
                if n == 0: continue
                signal = (n / 13) < frac + 0.08                 # node n has found its partial
                f = F0 * NODES[n][3] if signal else modes[(n * 3 + i) % len(modes)]
                node_note(t + 0.4 * j + 0.9 * k, n, 4.0, 0.3 + 0.45 * frac, freq=f, att=0.9, rel=2.2, rr=i * 7 + j + k)
        if i % 10 == 0: tank(t, 0.3 + 0.4 * frac)
    # signal: the whole overtone series, from the 28 edges that remain, fortissimo; then the stone
    t0 = T1
    for n in range(1, 13): node_note(t0 + 0.25 * n, n, 13.0, 1.0, att=5.0, rel=0.8, rr=n + 100)
    note(t0, "organ", "organ_ped", fit("organ_ped", F0, 37), 16.0, 1.0, att=4.0, rel=0.8)
    for p in (2, 3, 4, 6, 8, 12): note(t0, "organ", "organ_man", fit("organ_man", F0 * p, F0 * p), 16.0, 0.95, att=4.0, rel=0.8)
    perc(t0 + 6.0, "perc", "timp_roll", 1.0); perc(t0 + 16.0, "perc", "bdrum", 1.0)
    tank(t0 + 16.0, 1.0, dur=20.0)
    tank(1192.0, 0.12, dur=8.0)                               # felt more than heard, under the last of the reverb
    return dict(removed=removed, kept=sorted(live))


def build():
    EV.clear(); mov1(); mov2(); mov3(); mov4(); mov5(); info = mov6()
    EV.sort(key=lambda e: e["t"])
    return EV, info


if __name__ == "__main__":
    ev, info = build()
    kinds = {}
    for e in ev: kinds[e["k"]] = kinds.get(e["k"], 0) + 1
    print(len(ev), "events", kinds, "last at", max(e["t"] for e in ev))
    for name, (a, b) in [("I", (0, 195)), ("II", (195, 395)), ("III", (395, 595)), ("IV", (595, 795)), ("V", (795, 995)), ("VI", (995, 1200))]:
        print(name, sum(1 for e in ev if a <= e["t"] < b), "events")
    print("thinning kept", len(info["kept"]), "edges")
    json.dump(ev, open(os.path.join(HERE, "score.json"), "w"))
