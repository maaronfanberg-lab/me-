// Stage F (plate reverb) — proofs.  node qa-resonator/f1_verify.mjs [baseline.html]
// baseline defaults to the preview before the reverb (git show <P1 commit>:apps/resonator-next.html).
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import path from 'node:path';
import { lufs, truePeakDb } from './metrics.mjs';
const here = path.dirname(new URL(import.meta.url).pathname), root = path.join(here, '..');
const P1 = '969aac50dcc8daa40e44c0acc07effb314c09986';   // the preview before the reverb
let base = process.argv[2];
if (!base) { base = '/tmp/resonator-next-before-f1.html'; fs.writeFileSync(base, execSync(`git show ${P1}:apps/resonator-next.html`, { cwd: root, maxBuffer: 1 << 26 })); }
const B = await import('./harness.mjs?src=' + base);
const N = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
let failed = 0;
const check = (name, ok, detail = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };
const SR = 32000;

function render(H, { secs = 4, shape = 'String', params = {}, notes, hook = null, mode = 0 } = {}) {
  const p = H.makeProc(SR), S = H.SHAPES[shape], g = S.make(S.def), NN = g.P.length;
  const idx = f => Math.min(NN - 1, Math.max(0, Math.round(f * (NN - 1))));
  const pos = new Float32Array(NN * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  const m = d => p.port.onmessage({ data: d });
  const struct = () => m({ t: 'struct', n: NN, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  struct(); m({ t: 'mode', v: mode }); m({ t: 'pk', v: 0 });
  for (const k in H.KNOBS) if (!['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k)) m({ t: 'p', k, v: k in params ? params[k] : H.KNOBS[k].val });
  m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'mic2', i: idx(0.62), a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
  const pat = notes || Array.from({ length: 16 }, (_, i) => ({ at: i * 0.25, semi: [0, 3, 5, 7, 10, 12, 7, 3][i % 8], v: i % 2 ? 0.55 : 0.9 }));
  const Bk = 128, nb = Math.ceil(secs * SR / Bk), L = new Float32Array(nb * Bk), R = new Float32Array(nb * Bk), bl = new Float32Array(Bk), br = new Float32Array(Bk);
  let ni = 0;
  for (let b = 0; b < nb; b++) {
    const t = b * Bk / SR;
    while (ni < pat.length && pat[ni].at <= t) { const n = pat[ni++]; m({ t: 'note', f: 440 * Math.pow(2, (52 + n.semi - 69) / 12), v: n.v }); }
    if (hook) hook(p, b, t, m, struct);
    bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * Bk); R.set(br, b * Bk);
  }
  return { L, R, p };
}
const same = (a, b) => a.L.every((v, i) => Object.is(v, b.L[i])) && a.R.every((v, i) => Object.is(v, b.R[i]));

// ---------- 1. Reverb at 0: bit-identical to the preview before the reverb ----------
{
  const cfgs = [{ name: 'default' }];
  for (const s of Object.keys(N.SHAPES)) cfgs.push({ name: 'shape ' + s, shape: s });
  for (const k in B.KNOBS) for (const e of ['min', 'max']) if (!['size', 'mag', 'hit', 'mic'].includes(k)) cfgs.push({ name: `${k} ${e}`, params: { [k]: B.KNOBS[k][e] } });
  cfgs.push({ name: 'plectrum', mode: 2 }, { name: '4 voices', params: { voices: 4 } }, { name: 'effects + space', params: { att: 0.8, fxCho: 0.6, fxDly: 0.6, spImg: 0.8, spRefl: 0.6 } });
  const bad = [];
  for (const c of cfgs) { const { name, ...o } = c; if (!same(render(B, o), render(N, o))) bad.push(name); }
  check(`Reverb 0: bit-identical to the preview before the reverb (${cfgs.length} setups)`, bad.length === 0, bad.join(', '));
}

// ---------- the reverb alone: an impulse in, its response out ----------
function impulse(params, secs) {
  const p = N.makeProc(SR);
  p.port.onmessage({ data: { t: 'p', k: 'rvMix', v: 1 } });
  for (const [k, v] of Object.entries(params)) { p[k] = v; }
  p.rvSet();
  const n = Math.round(secs * SR), L = new Float64Array(n), R = new Float64Array(n);
  for (let i = 0; i < n; i++) { p.reverbSample(i === 0 ? 1 : 0, i === 0 ? 1 : 0); L[i] = p.rvOutL; R[i] = p.rvOutR; }
  return { L, R, p };
}
function lowpass(x, fc) { const a = Math.exp(-2 * Math.PI * fc / SR); const y = new Float64Array(x.length); let s = 0; for (let i = 0; i < x.length; i++) { s = (1 - a) * x[i] + a * s; y[i] = s; } for (let i = x.length - 1, z = 0; i >= 0; i--) { z = (1 - a) * y[i] + a * z; y[i] = z; } return y; }
// Schroeder backward integration; T60 from the -5..-35 dB slope (T30 x 2), as in ISO 3382-1
function t60(x) {
  const n = x.length, E = new Float64Array(n); let acc = 0;
  for (let i = n - 1; i >= 0; i--) { acc += x[i] * x[i]; E[i] = acc; }
  const db = i => 10 * Math.log10(E[i] / E[0]);
  let i5 = 0; while (i5 < n && db(i5) > -5) i5++;
  let i35 = i5; while (i35 < n && db(i35) > -35) i35++;
  let sx = 0, sy = 0, sxx = 0, sxy = 0, k = 0;
  for (let i = i5; i <= i35 && i < n; i += 16) { const t = i / SR, y = db(i); sx += t; sy += y; sxx += t * t; sxy += t * y; k++; }
  const slope = (k * sxy - sx * sy) / (k * sxx - sx * sx);
  return -60 / slope;
}

// ---------- 2. Reverb time: formula vs measurement (two ways) ----------
{
  const rows = [];
  for (const T of [0.6, 1.0, 1.5, 2.5, 4.0, 6.0, 12.0]) {
    const { L, R } = impulse({ rvTime: T, rvTone: 16000, rvPre: 0 }, T * 2.5 + 1);
    const mono = L.map((v, i) => v + R[i]);
    const tm = t60(lowpass(mono, 1000));   // low band: the design equation is for low frequencies
    rows.push({ set: T, measured: +tm.toFixed(2), err: +(100 * (tm - T) / T).toFixed(1) });
  }
  console.table(rows);
  check('Reverb time: measured T60 (below 1 kHz, Schroeder/ISO 3382) within 5% of the setting (5% ≈ the audible step)', rows.every(r => Math.abs(r.err) <= 5), rows.map(r => `${r.set}s→${r.measured}s`).join(' · '));
  // derived the other way: Dattorro's default decay 0.50 = 1.8 s by the trip-time formula, before the measured correction
  const trip = 21589 / 29761, tFormula = Math.log(0.001) * trip / (4 * Math.log(0.5));
  check("Dattorro's default decay 0.50 corresponds to 1.81 s by the trip-time formula", Math.abs(tFormula - 1.81) < 0.01, `${tFormula.toFixed(3)} s`);
  // tone: darker setting shortens the high band more than the low band
  const dark = impulse({ rvTime: 2.5, rvTone: 2000, rvPre: 0 }, 6), brt = impulse({ rvTime: 2.5, rvTone: 16000, rvPre: 0 }, 6);
  // narrow band around 4.5 kHz (RBJ band-pass, Q 4, run forward and backward: zero phase), so one
  // frequency's decay is compared with the filter's prediction at that frequency
  const bp = (x, f0, Q) => { const w0 = 2 * Math.PI * f0 / SR, al = Math.sin(w0) / (2 * Q), a0 = 1 + al;
    const b0 = al / a0, b2 = -al / a0, a1 = -2 * Math.cos(w0) / a0, a2 = (1 - al) / a0;
    const run = (xs) => { const y = new Float64Array(xs.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
      for (let i = 0; i < xs.length; i++) { const v = b0 * xs[i] + b2 * x2 - a1 * y1 - a2 * y2; x2 = x1; x1 = xs[i]; y2 = y1; y1 = v; y[i] = v; } return y; };
    return run(run(x).reverse()).reverse(); };
  const hi = x => bp(x, 4500, 4);
  const tD = t60(hi(dark.L)), tB = t60(hi(brt.L));
  // prediction: per trip, decay costs 4*20log10(dec) dB and the damping filter 2*20log10|H(f)| dB (twice per trip)
  const pd = N.makeProc(SR); pd.rvMix = 1; pd.rvTime = 2.5; pd.rvTone = 2000; pd.rvSet(); const decD = pd.rvDec, dmD = pd.rvDamp;
  pd.rvTone = 16000; pd.rvSet(); const dmB = pd.rvDamp;
  const Hdb = (d, f) => { const w = 2 * Math.PI * f / SR; return 20 * Math.log10((1 - d) / Math.sqrt(1 - 2 * d * Math.cos(w) + d * d)); };
  const perTrip = (dm, f) => 4 * 20 * Math.log10(decD) + 2 * Hdb(dm, f);
  const pred = perTrip(dmB, 4500) / perTrip(dmD, 4500);   // T60 ratio dark/bright at the band's centre
  check('Reverb tone: around 4.5 kHz the darker plate decays as its damping filter predicts (within 15%)', Math.abs(tD / tB - pred) / pred < 0.15,
    `measured ${(tD / tB).toFixed(3)} (${tD.toFixed(2)} s vs ${tB.toFixed(2)} s), predicted ${pred.toFixed(3)}`);
}

// ---------- 3. stereo, pre-delay, stability ----------
{
  const { L, R } = impulse({ rvTime: 2.5, rvTone: 9000, rvPre: 0 }, 3);
  let sll = 0, srr = 0, slr = 0; for (let i = Math.round(0.05 * SR); i < L.length; i++) { sll += L[i] * L[i]; srr += R[i] * R[i]; slr += L[i] * R[i]; }
  const corr = slr / Math.sqrt(sll * srr);
  check('stereo: left and right tails decorrelated', Math.abs(corr) < 0.2, `correlation ${corr.toFixed(3)}`);
  const onset = x => { let pk = 0; for (const v of x) pk = Math.max(pk, Math.abs(v)); for (let i = 0; i < x.length; i++) if (Math.abs(x[i]) > 0.01 * pk) return i; return -1; };
  const a = impulse({ rvTime: 2.5, rvPre: 0 }, 1), b = impulse({ rvTime: 2.5, rvPre: 100 }, 1);
  const dms = (onset(b.L) - onset(a.L)) / SR * 1000;
  check('pre-delay: 100 ms setting delays the reverb by 100 ms', Math.abs(dms - 100) < 1, `${dms.toFixed(2)} ms`);
  const long = impulse({ rvTime: 12, rvTone: 16000, rvPre: 0 }, 30);
  let fin = true, last = 0; for (let i = 0; i < long.L.length; i++) { if (!Number.isFinite(long.L[i])) fin = false; if (i > long.L.length - SR) last = Math.max(last, Math.abs(long.L[i])); }
  check('longest setting (12 s) stays stable and keeps decaying', fin && last < 1e-2, `level in the last second of 30 s: ${last.toExponential(2)}`);
}

// ---------- 4. level calibration (Reverb 100% vs dry) ----------
{
  const dry = render(N, { secs: 6 }), wet = render(N, { secs: 6, params: { rvMix: 1 } });
  const wetOnly = { L: wet.L.map((v, i) => v - dry.L[i]), R: wet.R.map((v, i) => v - dry.R[i]) };
  const lD = lufs(dry.L, dry.R, SR), lW = lufs(wetOnly.L, wetOnly.R, SR);
  console.log(`  dry ${lD.toFixed(2)} LUFS · reverb alone at 100% ${lW.toFixed(2)} LUFS (rvK ${N.makeProc(SR).rvK})`);
  check('Reverb 100% adds a tail as loud as the dry sound (within 1 dB)', Math.abs(lW - lD) <= 1, `difference ${(lW - lD).toFixed(2)} dB`);
}

// ---------- 5. ceiling, determinism, Hush, shape change ----------
{
  const worst = { drive: 4, nl: 8, amp: 1, gain: 1.6, bass: 2, voices: 8, rvMix: 1, rvTime: 12, rvTone: 16000 };
  let tp = -99;
  for (const s of ['String', 'Chime', 'Tank']) { const r = render(N, { shape: s, secs: 5, params: worst }); tp = Math.max(tp, truePeakDb(r.L), truePeakDb(r.R)); }
  check('true peak with the longest, loudest reverb stays at or below -1 dBTP', tp <= -1, `${tp.toFixed(2)} dBTP`);
  const o = { secs: 4, params: { rvMix: 0.6, rvTime: 3 } };
  check('deterministic: same input, same output', same(render(N, o), render(N, o)));
  // Hush at 1.0 s: the tail must be gone a moment later
  const h = render(N, { secs: 2, params: { rvMix: 1, rvTime: 6 }, notes: [{ at: 0.02, semi: 0, v: 0.9 }], hook: (p, b, t, m) => { if (b === Math.round(1.0 * SR / 128)) m({ t: 'hush' }); } });
  let after = 0; for (let i = Math.round(1.3 * SR); i < h.L.length; i++) after = Math.max(after, Math.abs(h.L[i]));
  // audibility bar: below -90 dBFS (16-bit audio's floor is -96). Without reverb the residue is ~1e-11;
  // with it, the output filters' last millionths echo into the cleared reverb (about -108 dBFS).
  check('Hush silences the reverb tail too (inaudible: below -90 dBFS)', after < 3.2e-5, `peak after Hush ${after.toExponential(2)} (${(20 * Math.log10(Math.max(after, 1e-30))).toFixed(0)} dBFS)`);
  // a new body (shape change re-sends every knob) must not cut a ringing tail
  const keep = render(N, { secs: 2, params: { rvMix: 1, rvTime: 6, decay: 0.2 }, notes: [{ at: 0.02, semi: 0, v: 0.9 }], hook: (p, b, t, m, struct) => {
    if (b === Math.round(1.0 * SR / 128)) { struct(); for (const k of ['rvMix', 'rvTime', 'rvTone', 'rvPre']) m({ t: 'p', k, v: p[k] }); } } });
  let tail = 0; for (let i = Math.round(1.2 * SR); i < Math.round(1.4 * SR); i++) tail = Math.max(tail, Math.abs(keep.L[i]));
  check('a new body keeps the reverb tail ringing', tail > 1e-3, `tail level 0.2 s after the new body ${tail.toFixed(4)}`);
}

// ---------- 6. cost (fresh processes, this machine) ----------
if (!process.env.F1_SKIP_COST) {
  const costOne = (src, o) => Number(execSync(`node ${JSON.stringify(path.join(here, 'p1_cost_one.mjs'))} ${JSON.stringify(src)} ${JSON.stringify(JSON.stringify(o))}`, { cwd: root }).toString());
  const med = (o) => [costOne(path.join(root, 'apps/resonator-next.html'), o), costOne(path.join(root, 'apps/resonator-next.html'), o), costOne(path.join(root, 'apps/resonator-next.html'), o)].sort((a, b) => a - b)[1];
  const off = med({}), on = med({ params: { rvMix: 0.5 } });
  console.log(`  cost, String 1 voice: reverb off ${(100 * off).toFixed(1)}% · on ${(100 * on).toFixed(1)}% of real time`);
}
console.log(failed ? `\n${failed} check(s) FAILED` : '\nall Stage F checks pass');
process.exit(failed ? 1 : 0);
