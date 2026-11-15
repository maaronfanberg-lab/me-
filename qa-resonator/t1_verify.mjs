// Stage T1 (the water tower) — offline proofs.  node qa-resonator/t1_verify.mjs [old.html] [new.html]
// old.html defaults to the preview just before T1 (git show T1_BASE:apps/resonator-next.html).
// Every number is measured with exactly what the page sends (a body's struct with its probe, the controls in
// SENDS, pad/padRef, lvl), using the page's own SHAPES and defaults.
//  A. Tank: bit-identical to the preview before T1, every Size, chords, moves, Hush, retuning (the tower's
//     additions are switched off for the Tank: no probe, pad 0).
//  B. The tower's modes (engine's own stiffness matrix and eigen-solver), against the research table
//     (sphere estimates) and the finite-element model of the oblate bowl (tower_fe.py): the tuned mode is the
//     bowl's lowest two-lobed mode; breathing and the cluster within 10%.
//  C. The padded mallet: the engine's contact simulation vs tower_acoustics.py (contact time, bandwidth, rebound
//     within 20%), harder swings brighter where the law says so, and the contact scaled with the tower's size.
//  D. Each padding is audibly different from the others; Real size vs Phone size.
//  E. Decay at real size vs the research's 2.9 s for the low bowl modes (within 25%).
//  F. Loudness: the tower at its defaults as loud as the Tank as played (within 1 LU); worst case under the
//     ceiling with no NaN for every padding; deterministic.
//  G. Cost: the tower's springs x oversampling vs the Tank's, and time per second of audio on this machine.
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
const here = path.dirname(new URL(import.meta.url).pathname), root = path.resolve(here, '..');
const T1_BASE = 'f8e9a3de8c443327589e91c11c6eb9bb8d591b28';   // the preview after J1, before T1
let oldSrc = process.argv[2];
if (!oldSrc) { oldSrc = '/tmp/resonator-next-before-t1.html'; fs.writeFileSync(oldSrc, execSync(`git show ${T1_BASE}:apps/resonator-next.html`, { cwd: root, maxBuffer: 1 << 26 })); }
const newSrc = process.argv[3] || path.join(root, 'apps/resonator-next.html');
const A = await import('./harness.mjs?src=' + oldSrc), B = await import('./harness.mjs?src=' + newSrc);
const M = await import('./metrics.mjs');
process.env.NOMAIN = '1';
const TP = await import('./tower_proto.mjs');
const html = fs.readFileSync(newSrc, 'utf8');
const LVL = new Function(html.slice(html.indexOf('const SHAPE_LVL='), html.indexOf('\n', html.indexOf('const SHAPE_LVL='))) + '\nreturn SHAPE_LVL;')();
const TOWER_REF = +html.match(/TOWER_REF=([0-9.]+)/)[1];
const SENDS = ['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices'];
let failed = 0;
const want = k => !process.env.T1_ONLY || process.env.T1_ONLY.includes(k);   // T1_ONLY=BC runs sections B and C (mutation tests)
const check = (name, ok, detail = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };
const RATE = 32000;
const hz = midi => 440 * Math.pow(2, (midi - 69) / 12);

// the page's message burst for a body (what buildShape sends)
function burst(H, shape, n, val, { pad = 2, withPad = true } = {}) {
  const S = H.OWN_SHAPES[shape], g = S.make(n ?? S.def), pos = new Float32Array(g.P.length * 3);
  g.P.forEach((q, i) => pos.set(q, i * 3));
  const st = { t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis };
  if (g.probe) st.probe = Float32Array.from(g.probe);
  const v = {}; for (const k in H.KNOBS) v[k] = H.KNOBS[k].val;
  if (S.ratio != null) v.ratio = S.ratio; if (S.decay != null) v.decay = S.decay;
  Object.assign(v, val || {});
  const m = [st]; for (const k of SENDS) m.push({ t: 'p', k, v: v[k] });
  if (withPad) m.push({ t: 'p', k: 'pad', v: shape === 'Tower' ? pad : 0 }, { t: 'p', k: 'padRef', v: TOWER_REF });
  m.push({ t: 'lvl', v: LVL[shape] || 1 });
  return { g, m };
}
function render(H, evs, secs, rate = RATE) {
  const now = Date.now; Date.now = () => 0;   // the CPU governor's clock held still (see j1_verify)
  try {
    const p = H.makeProc(rate), send = d => p.port.onmessage({ data: structuredClone(d) });
    const Bk = 128, nb = Math.ceil(secs * rate / Bk), L = new Float32Array(nb * Bk), R = new Float32Array(nb * Bk);
    const bl = new Float32Array(Bk), br = new Float32Array(Bk), ev = [...evs].sort((a, b) => a.at - b.at); let e = 0;
    for (let b = 0; b < nb; b++) { const t = b * Bk / rate;
      while (e < ev.length && ev[e].at <= t) { for (const m of ev[e].m) send(m); e++; }
      bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * Bk); R.set(br, b * Bk); }
    return { L, R, p };
  } finally { Date.now = now; }
}
const note = (at, midi, v) => ({ at, m: [{ t: 'note', f: hz(midi), v }] });
const peak = x => { let p = 0; for (const v of x) p = Math.max(p, Math.abs(v)); return p; };
const same = (a, b) => a.L.length === b.L.length && a.L.every((v, i) => Object.is(v, b.L[i])) && a.R.every((v, i) => Object.is(v, b.R[i]));

// ---------- A. the Tank is unchanged ----------
if (want('A')) {
  const tune = [note(0.05, 52, 0.9), note(0.45, 59, 0.55), note(0.8, 55, 0.75), note(1.1, 64, 0.9), note(1.15, 67, 0.6)];
  const cases = [];
  for (let C = 5; C <= 9; C++) cases.push({ name: `Size ${C}`, C, val: {}, ev: tune });
  cases.push({ name: '8 voices, chord', C: 7, val: { voices: 8 }, ev: [note(0.05, 52, 0.8), note(0.06, 56, 0.7), note(0.07, 59, 0.9), note(0.6, 64, 0.6), note(0.61, 68, 0.6)] });
  cases.push({ name: 'hard mallet, glancing, Drive 4, Nonlinearity 6', C: 7, val: { hard: 0, angle: 1, drive: 4, nl: 6 }, ev: tune });
  cases.push({ name: 'Hush + retune mid-ring', C: 7, val: { decay: 20 }, ev: [note(0.05, 52, 0.9), { at: 0.4, m: [{ t: 'p', k: 'ratio', v: 9 }, { t: 'p', k: 'tune', v: -250 }] }, { at: 0.6, m: [{ t: 'hush' }] }, note(0.9, 59, 0.7)] });
  let ok = 0; const bad = [];
  for (const rate of [32000, 48000]) for (const c of cases) {
    const a = render(A, [{ at: 0, m: burst(A, 'Tank', c.C, c.val, { withPad: false }).m }, ...c.ev], 1.6, rate);
    const b = render(B, [{ at: 0, m: burst(B, 'Tank', c.C, c.val).m }, ...c.ev], 1.6, rate);
    if (same(a, b) && peak(a.L) > 0.01) ok++; else bad.push(`${rate} ${c.name}`);
  }
  check('A. Tank: bit-identical to the preview before T1 (the tower\'s additions are off for it)', !bad.length, `${ok}/${ok + bad.length} setups identical` + (bad.length ? '; differ: ' + bad.join(', ') : ''));
}

// ---------- B. the tower's modes ----------
const RES = { n2: [51, 60], cluster: [64, 82], breathing: [118, 138] };     // research table (sphere estimates)
const FE = JSON.parse(fs.readFileSync(path.join(here, 'tower_fe_modes.json'), 'utf8'))['12mm'];   // tower_fe.py: oblate bowl, clamped neck
const tow = {};
for (const E of want('B') ? [10, 12, 14, 16, 18] : []) {
  const S = B.OWN_SHAPES.Tower, g = S.make(E);
  const p = B.makeProc(RATE); const { m } = burst(B, 'Tower', E, {});
  for (const d of m) p.port.onmessage({ data: structuredClone(d) });
  p.calibrate(); p.calDirty = false;   // the body is built before its Stiffness arrives; the page's next note retunes like this
  p.dofMap(); const q0 = p.kLfor(p.kRef); const sp = p.modeSpectrum(p.kRef, q0.kL, p.sub * p.kRef);
  const byOv = [...sp].sort((a, b) => b.ov - a.ov);
  const ga = Object.assign({}, g, { a: g.dims.a * g.dims.s, b: g.dims.b * g.dims.s, yc: g.dims.y0 - g.dims.yc * g.dims.s });
  const { modes } = TP.analyse(ga, S.ratio);
  const ok = q => q.bowlShare > 0.6 && q.radShare > 0.6;
  const fr = p.fRef / Math.sqrt(p.kRef), real = f => f / fr * TOWER_REF;
  const n2 = modes.find(q => ok(q) && q.mAz === 2 && q.azShare > 0.5);
  const cl = modes.filter(q => ok(q) && q.f >= n2.f && q.f < fr * 0.9999).map(q => real(q.f)).sort((a, b) => a - b);
  const Q = pp => cl[Math.min(cl.length - 1, Math.floor(pp * cl.length))];
  tow[E] = { ov: byOv.map(x => x.ov), ovf: byOv.map(x => x.f / p.fRef), isMax: Math.abs(byOv[0].f - p.fRef) < 1e-6 * p.fRef,
             n2: real(n2.f), cl, q: [Q(0.1), Q(0.5), Q(0.9)], mmax: Math.max(...modes.filter(ok).map(q => q.mAz)) };
}
if (want('B')) {
  const def = B.OWN_SHAPES.Tower.def, t = tow[def];
  check('B1. the keys tune the bowl\'s breathing mode: the mode most like the bowl swelling outward; at the default Size clearly so (≥ 1.25× the runner-up), and at every Size any close runner-up lies within 15% in pitch',
    Object.values(tow).every(x => x.isMax && x.ovf.slice(1).every((f, i) => x.ov[i + 1] < 0.8 * x.ov[0] || Math.abs(f - 1) <= 0.15)) && t.ov[0] >= 1.25 * t.ov[1],
    Object.entries(tow).map(([E, x]) => `Size ${E}: ${(x.ov[0] * 100).toFixed(0)}% (next ${(x.ov[1] * 100).toFixed(0)}% at ${(x.ovf[1]).toFixed(3)}×)`).join('; '));
  check('B2. true size: the breathing mode at real size is the finite-element model\'s, inside the research table\'s 118–138 Hz',
    Math.abs(TOWER_REF - FE.breathing) < 0.5 && TOWER_REF >= RES.breathing[0] && TOWER_REF <= RES.breathing[1], `${TOWER_REF} Hz (FE ${FE.breathing} Hz, volume share ${FE.breathing_volume_share})`);
  check('B3. the lowest two-lobed bowl mode at real size within 10% of the research table\'s 51–60 Hz (lowest bending mode)',
    Object.values(tow).every(x => x.n2 >= RES.n2[0] * 0.9 && x.n2 <= RES.n2[1] * 1.1), Object.entries(tow).map(([E, x]) => `Size ${E}: ${x.n2.toFixed(1)} Hz`).join(', ') + ` (FE, oblate: ${FE.m2_lowest} Hz)`);
  const fq = FE.cluster_by_mmax[String(Math.min(8, Math.max(4, t.mmax)))];
  check('B4. the cluster (bowl modes between the two-lobed mode and breathing): median within 10% of the research table\'s 64–82 Hz and of the finite-element model\'s modes of the orders this mesh can hold',
    t.q[1] >= RES.cluster[0] * 0.9 && t.q[1] <= RES.cluster[1] * 1.1 && Math.abs(t.q[1] / fq[1] - 1) <= 0.10 && t.cl.length >= 20,
    `Size ${def}: ${t.cl.length} modes, 10th/50th/90th percentile ${t.q.map(v => v.toFixed(0)).join(' / ')} Hz; FE (orders up to ${t.mmax}) ${fq.slice(0, 3).join(' / ')} Hz; other sizes ` +
    Object.entries(tow).filter(([E]) => +E !== def).map(([E, x]) => `${E}: ${x.q.map(v => v.toFixed(0)).join('/')}`).join(', '));
}

// ---------- C. the padded mallet ----------
const SCRIPT = { 1: { name: 'thick leather', ms: 2.1, f20: 658, e: 0.86 }, 2: { name: 'thick wool', ms: 24.9, f20: 103, e: 0.73 },
                 3: { name: 'compressed Styrofoam (414 kPa)', ms: 12.3, f20: 91, e: 0.45 }, 4: { name: 'rubber', ms: 12.3, f20: 121, e: 0.90 } };
const f20 = (tab, tau) => {   // first frequency where the force spectrum is 20 dB below DC
  const K = tab.length, dt = tau / (K - 1);
  let dc = 0; for (let k = 0; k < K; k++) dc += tab[k];
  for (let f = 1; f < 5000; f += 0.5) { let re = 0, im = 0; for (let k = 0; k < K; k++) { re += tab[k] * Math.cos(2 * Math.PI * f * k * dt); im -= tab[k] * Math.sin(2 * Math.PI * f * k * dt); }
    if (Math.hypot(re, im) < 0.1 * dc) return f; }
  return 5000;
};
if (want('C')) {
  const p = B.makeProc(RATE), rows = [], bad = [];
  for (const law of [1, 2, 3, 4]) {
    const c = p.padContact(law, 4), s = SCRIPT[law], ff = f20(c.tab, c.tau);
    // contact time as the script measures it: how long the force stays above 2% of its peak (a hardening pad
    // touches for longer than that, with very little force at either end)
    const above = c.tab.filter(v => v > 0.02).length, ms = above / (c.tab.length - 1) * c.tau * 1000;
    const okk = Math.abs(ms / s.ms - 1) <= 0.2 && Math.abs(ff / s.f20 - 1) <= 0.2 && Math.abs(c.e / s.e - 1) <= 0.2;
    rows.push(`${s.name}: ${ms.toFixed(1)} ms above 2% (script ${s.ms}; touching ${(c.tau * 1000).toFixed(1)} ms), −20 dB at ${ff.toFixed(0)} Hz (${s.f20}), rebound ${c.e.toFixed(2)} (${s.e})`);
    if (!okk) bad.push(s.name);
  }
  check('C1. each padding\'s contact (4 m/s, real size) matches tower_acoustics.py within 20%: time, bandwidth, rebound', !bad.length, rows.join('; '));
  const soft = p.padContact(2, 2), hard = p.padContact(2, 8), r1 = p.padContact(1, 2), r2 = p.padContact(1, 8);
  check('C2. wool: a harder swing makes a shorter, brighter contact (hardening pad); leather barely changes (linear pad)',
    f20(hard.tab, hard.tau) > 1.2 * f20(soft.tab, soft.tau) && Math.abs(r2.tau / r1.tau - 1) < 0.05,
    `wool 2 → 8 m/s: ${(soft.tau * 1000).toFixed(1)} → ${(hard.tau * 1000).toFixed(1)} ms, ${f20(soft.tab, soft.tau).toFixed(0)} → ${f20(hard.tab, hard.tau).toFixed(0)} Hz; leather ${(r1.tau * 1000).toFixed(2)} → ${(r2.tau * 1000).toFixed(2)} ms`);
  // the strike's length on a body: real size = the real contact; a key an octave up = half
  const q = B.makeProc(RATE); for (const d of burst(B, 'Tower', null, {}).m) q.port.onmessage({ data: structuredClone(d) });
  q.port.onmessage({ data: { t: 'note', f: TOWER_REF, v: 0.8 } }); const real = q.padLast;
  q.port.onmessage({ data: { t: 'note', f: 2 * TOWER_REF, v: 0.8 } }); const half = q.padLast;
  check('C3. the mallet scales with the tower: at real size the strike lasts the real contact time; a tower half the size, half as long',
    Math.abs(real.secs / real.tau - 1) < 1e-9 && Math.abs(half.secs / (real.tau / 2) - 1) < 1e-9, `real ${(real.secs * 1000).toFixed(1)} ms; half-size ${(half.secs * 1000).toFixed(1)} ms`);
}

// ---------- D. each padding audibly different; Real size vs Phone size ----------
function centroid(L, fs, t0, t1) {   // spectral centroid of a window (Hann), and its level
  const a = Math.floor(t0 * fs), N = 1 << Math.floor(Math.log2((t1 - t0) * fs)), re = new Float64Array(N), im = new Float64Array(N);
  for (let i = 0; i < N; i++) re[i] = (L[a + i] || 0) * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / N));
  for (let i = 1, j = 0; i < N; i++) { let bit = N >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit; if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let len = 2; len <= N; len <<= 1) { const w = -2 * Math.PI / len; for (let i = 0; i < N; i += len) for (let k = 0; k < len / 2; k++) {
    const c = Math.cos(w * k), s = Math.sin(w * k), xr = re[i + k + len / 2] * c - im[i + k + len / 2] * s, xi = re[i + k + len / 2] * s + im[i + k + len / 2] * c;
    re[i + k + len / 2] = re[i + k] - xr; im[i + k + len / 2] = im[i + k] - xi; re[i + k] += xr; im[i + k] += xi; } }
  let num = 0, den = 0; for (let k = 1; k < N / 2; k++) { const p = re[k] * re[k] + im[k] * im[k]; num += p * k * fs / N; den += p; }
  return { c: num / den, db: 10 * Math.log10(den / N + 1e-30) };
}
if (want('D')) {
  const res = {};
  for (const pad of [1, 2, 3, 4]) {
    const r = render(B, [{ at: 0, m: burst(B, 'Tower', null, {}, { pad }).m }, note(0.1, 64, 0.8)], 1.2);
    res[pad] = centroid(r.L, RATE, 0.1, 0.6);
  }
  // a just-noticeable change in brightness is roughly 5% in centroid; in level, 1 dB
  const pairs = []; let okAll = true;
  for (let a = 1; a <= 4; a++) for (let b = a + 1; b <= 4; b++) {
    const dc = Math.abs(res[a].c / res[b].c - 1), dl = Math.abs(res[a].db - res[b].db), ok = dc >= 0.05 || dl >= 1;
    okAll = okAll && ok; pairs.push(`${['', 'L', 'W', 'S', 'R'][a]}/${['', 'L', 'W', 'S', 'R'][b]} ${(dc * 100).toFixed(0)}% ${dl.toFixed(1)} dB`);
  }
  check('D1. every padding sounds different from every other (brightness ≥ 5% or level ≥ 1 dB, first half second, phone size E4)', okAll,
    Object.entries(res).map(([k, v]) => `${['', 'leather', 'wool', 'Styrofoam', 'rubber'][k]} ${v.c.toFixed(0)} Hz ${v.db.toFixed(1)} dB`).join(', ') + ' · pairs ' + pairs.join(', '));
  const lo = render(B, [{ at: 0, m: burst(B, 'Tower', null, {}).m }, note(0.1, 48, 0.8)], 1.2), hi = render(B, [{ at: 0, m: burst(B, 'Tower', null, {}).m }, note(0.1, 64, 0.8)], 1.2);
  const cl = centroid(lo.L, RATE, 0.1, 0.6), ch = centroid(hi.L, RATE, 0.1, 0.6);
  check('D2. Real size (C3) is lower than Phone size (E4): centroid ratio near the 2.5× size ratio', ch.c / cl.c > 1.8 && ch.c / cl.c < 3.4, `${cl.c.toFixed(0)} Hz vs ${ch.c.toFixed(0)} Hz (${(ch.c / cl.c).toFixed(2)}×)`);
}

// ---------- E. decay at real size ----------
if (want('E')) {
  const fall = (x, db) => { let pk = 0; for (const v of x) pk = Math.max(pk, Math.abs(v)); const thr = pk * Math.pow(10, -db / 20), W = RATE / 100;
    let last = 0; for (let i = 0; i + W <= x.length; i += W) { let m = 0; for (let j = i; j < i + W; j++) m = Math.max(m, Math.abs(x[j])); if (m > thr) last = i + W; } return last / RATE; };
  const r = render(B, [{ at: 0, m: burst(B, 'Tower', null, {}).m }, note(0, 48, 0.8)], 6);
  const t60 = fall(r.L, 60), t40 = fall(r.L, 40), dec = B.OWN_SHAPES.Tower.decay;
  check('E1. at real size the boom dies away like the low bowl modes in the research (60 dB in 2.9 s, within 25%)', Math.abs(t60 / 2.9 - 1) <= 0.25, `default Sustain ${dec}: 60 dB in ${t60.toFixed(2)} s, 40 dB in ${t40.toFixed(2)} s (the knob shows ${(1.55 * dec).toFixed(1)} s)`);
  check('E2. the Sustain readout (1.55 × the setting, the 40 dB time) holds on the tower within 25%', Math.abs(t40 / (1.55 * dec) - 1) <= 0.25, `shows ${(1.55 * dec).toFixed(2)} s, measured ${t40.toFixed(2)} s`);
}

// ---------- F. loudness, ceiling, determinism ----------
if (want('F')) {
  // the same pattern on each body's own keys (Tank E3, Tower E4, the roots the page gives them)
  const pat = root => Array.from({ length: 16 }, (_, i) => note(0.05 + i * 0.25, root + [0, 3, 5, 7, 10, 12, 7, 3][i % 8], i % 2 ? 0.55 : 0.9));
  const tk = render(B, [{ at: 0, m: burst(B, 'Tank', null, {}).m }, ...pat(52)], 4.2), tw = render(B, [{ at: 0, m: burst(B, 'Tower', null, {}).m }, ...pat(B.OWN_SHAPES.Tower.root)], 4.2);
  const lt = M.lufs(tk.L, tk.R, RATE), lw = M.lufs(tw.L, tw.R, RATE);
  check('F1. the tower at its defaults is as loud as the Tank as played (within 1 LU)', Math.abs(lw - lt) <= 1, `Tank ${lt.toFixed(2)} LUFS, Tower ${lw.toFixed(2)} LUFS (SHAPE_LVL.Tower ${LVL.Tower})`);
  const keys = [36, 43, 48, 55, 64, 71, 76, 83];
  const loud = { voices: 8, drive: 4, nl: 8, gain: 1.6, bite: 2.5, tone: 12000, angle: 1, decay: 26, loss: 0, sub: 0 };
  const rows = []; let okc = true;
  for (const pad of [1, 2, 3, 4]) for (const n of [10, 18]) {
    const ev = [{ at: 0, m: burst(B, 'Tower', n, loud, { pad }).m }, ...keys.map(k => note(0.02, k, 1)), ...Array.from({ length: 16 }, (_, i) => note(0.4 + 0.1 * i, keys[i % 8], 1))];
    const r = render(B, ev, 2.6);
    let bad = 0; for (const v of r.L) if (!Number.isFinite(v)) bad++; for (const v of r.R) if (!Number.isFinite(v)) bad++;
    const pk = Math.max(peak(r.L), peak(r.R)); okc = okc && pk <= 0.78 && bad === 0 && pk > 0.1;
    rows.push(`${['', 'L', 'W', 'S', 'R'][pad]}/${n} ${pk.toFixed(3)}${bad ? ' NaN×' + bad : ''}`);
  }
  check('F2. worst case for every padding, smallest and largest tower (8 voices, Drive 4, Nonlinearity 8, Level max, real size up): peak under the ceiling, no NaN', okc, rows.join(' '));
  const o = [{ at: 0, m: burst(B, 'Tower', 18, loud, { pad: 1 }).m }, ...keys.map(k => note(0.02, k, 1))];
  check('F3. deterministic: the loudest tower renders bit-identically twice', same(render(B, o, 1.5), render(B, o, 1.5)));
}

// ---------- G. cost ----------
if (want('G')) {
  const rows = [];
  for (const [shape, n, midi] of [['Tank', null, 52], ['Tower', null, 64], ['Tower', null, 48], ['Tower', 18, 64]]) {
    const p = B.makeProc(RATE); const { g, m } = burst(B, shape, n, {}); for (const d of m) p.port.onmessage({ data: structuredClone(d) });
    p.port.onmessage({ data: { t: 'note', f: hz(midi), v: 0.8 } });
    const L = new Float32Array(128), R = new Float32Array(128); for (let b = 0; b < 100; b++) p.process([], [[L, R]]);
    const t0 = process.hrtime.bigint(); for (let b = 0; b < 500; b++) p.process([], [[L, R]]); const dt = Number(process.hrtime.bigint() - t0) / 1e9;
    rows.push({ shape, n: n ?? B.OWN_SHAPES[shape].def, midi, springs: g.S.length, os: p.os, load: g.S.length * p.os, rt: dt / (500 * 128 / RATE) });
  }
  const tk = rows[0];
  check('G1. the default tower costs the phone about what the Tank does at its largest (springs × oversampling ≤ 230, the Tank\'s largest is 216)',
    rows[1].load <= 230 && rows[2].load <= 230,
    rows.map(r => `${r.shape} ${r.n} at ${r.midi}: ${r.springs} springs × ${r.os} = ${r.load}, ${(r.rt * 100).toFixed(1)}% of real time here`).join('; '));
}
console.log(failed ? `\n${failed} T1 check(s) FAILED` : '\nall T1 checks pass');
process.exit(failed ? 1 : 0);
