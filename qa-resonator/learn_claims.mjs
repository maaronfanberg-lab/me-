// Checks every sound claim taught in the RESONATOR learning path against the engine itself,
// plus a reproduction of the known "octave trap". Prints PASS/FAIL per claim; exits 1 on any FAIL.
// Run: node qa-resonator/learn_claims.mjs
import { render, makeProc, SHAPES, KNOBS } from './harness.mjs';

const RATE = 48000, E3 = 440 * Math.pow(2, (52 - 69) / 12);
let failed = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + ' — ' + detail); if (!ok) failed++; };

// ---------- helpers ----------
function fftMag(x, start, len) {
  const N = 1 << Math.ceil(Math.log2(len)), re = new Float64Array(N), im = new Float64Array(N);
  for (let i = 0; i < len && start + i < x.length; i++) re[i] = x[start + i] * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / len));
  for (let i = 1, j = 0; i < N; i++) { let b = N >> 1; for (; j & b; b >>= 1) j ^= b; j ^= b; if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let L = 2; L <= N; L <<= 1) { const a = -2 * Math.PI / L; for (let i = 0; i < N; i += L) for (let k = 0; k < L / 2; k++) {
    const c = Math.cos(a * k), s = Math.sin(a * k), p = i + k, q = p + L / 2, tr = re[q] * c - im[q] * s, ti = re[q] * s + im[q] * c;
    re[q] = re[p] - tr; im[q] = im[p] - ti; re[p] += tr; im[p] += ti; } }
  const mag = new Float64Array(N / 2); for (let k = 0; k < N / 2; k++) mag[k] = Math.hypot(re[k], im[k]);
  return { mag, df: RATE / N };
}
const oneNote = (o) => render({ rate: RATE, secs: 2.5, notes: [{ at: 0.02, semi: 0, v: 0.9 }], ...o });
const centroid = (x) => { const { mag, df } = fftMag(x, Math.round(0.02 * RATE), Math.round(0.6 * RATE));
  let a = 0, b = 0; for (let k = 1; k < mag.length; k++) { const e = mag[k] * mag[k]; a += e * k * df; b += e; } return a / b; };
const decay40 = (x) => { let pk = 0; for (const v of x) pk = Math.max(pk, Math.abs(v)); const W = 480; let last = 0;
  for (let i = 0; i + W < x.length; i += W) { let m = 0; for (let j = i; j < i + W; j++) m = Math.max(m, Math.abs(x[j])); if (m > pk * 0.01) last = i + W; }
  return last / RATE; };

// A processor set up exactly the way the app loads a shape: structure (default strike & mic), every knob, then mic/hit.
function appLoad(shape, n, rate = RATE) {
  const p = makeProc(rate), S = SHAPES[shape], g = S.make(n ?? S.def), m = d => p.port.onmessage({ data: d });
  const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  m({ t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  for (const k in KNOBS) if (!['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k)) m({ t: 'p', k, v: k === 'bite' ? 0 : KNOBS[k].val });
  m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'mic2', i: g.mic, a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
  return { p, m, g };
}
// The engine's own modes at the pitch it is currently playing (same stiffness matrix as the simulation).
const playedModes = (p) => { const kT = p.vkTt[0], q = p.kLfor(kT);
  return p.modeSpectrum(kT, q.kL, Math.max(p.sub, p.anchored ? 0 : 1e-5) * kT); };

// ---------- 1. Mallet: hard is brighter than soft ----------
{ const hard = centroid(oneNote({ params: { hard: 0 } }).L), soft = centroid(oneNote({ params: { hard: 1 } }).L);
  check('Mallet hard vs soft', hard > 2 * soft, `brightness centre ${hard.toFixed(0)} Hz vs ${soft.toFixed(0)} Hz (E3 = ${E3.toFixed(1)} Hz)`); }

// ---------- 2. Decay: short is a pluck, longer rings longer ----------
{ const s = decay40(oneNote({ params: { decay: 0.3 } }).L), l = decay40(oneNote({ params: { decay: 2 } }).L);
  check('Decay short vs long', l > 2.5 * s, `time to -40 dB ${s.toFixed(2)} s vs ${l.toFixed(2)} s`); }

// ---------- 3. Damping in the springs: more is darker ----------
{ const lo = centroid(oneNote({ params: { loss: 0 } }).L), hi = centroid(oneNote({ params: { loss: 3 } }).L);
  check('Spring damping low vs high', hi < 0.9 * lo, `brightness centre ${lo.toFixed(0)} Hz vs ${hi.toFixed(0)} Hz`); }

// ---------- 4. Strike / mic at the exact centre removes the even partials ----------
// String with 15 masses: 17 points, ends clamped at 0 and 16, centre index 8. Mode m ~ sin(m*pi*x/L) = 0 at x = L/2 for even m.
for (const [label, hit, mic] of [['strike at centre', 8, 1], ['mic at centre', 2, 8]]) {
  const { p, m, g } = appLoad('String', 15);
  m({ t: 'mic', i: mic, a: g.axis }); m({ t: 'mic2', i: mic, a: g.axis }); m({ t: 'hit', i: hit, a: g.axis });
  m({ t: 'note', f: E3, v: 0.9 });
  const sp = playedModes(p), fs = [...new Set(sp.map(s => +s.f.toFixed(3)))].slice(0, 4);
  const B = 128, nb = Math.ceil(1.6 * RATE / B), L = new Float32Array(nb * B), bl = new Float32Array(B), br = new Float32Array(B);
  for (let b = 0; b < nb; b++) { bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * B); }
  const { mag, df } = fftMag(L, 2400, L.length - 2400);
  const lv = fs.map(f => { let mx = 0; for (let k = Math.floor(f * 0.99 / df); k <= Math.ceil(f * 1.01 / df); k++) mx = Math.max(mx, mag[k] || 0); return mx; });
  const db = lv.map(v => 20 * Math.log10(v / Math.max(...lv)));
  check('String, ' + label + ': partials 2 and 4 inaudible', db[1] < -60 && db[3] < -60 && db[0] > -10,
    `partials ${fs.map(f => f.toFixed(0)).join('/')} Hz at ${db.map(d => d.toFixed(0)).join('/')} dB`);
}

// ---------- 5. String has near-whole-number partials; Drum does not ----------
{ const ratios = (shape) => { const { p, m } = appLoad(shape); m({ t: 'note', f: E3, v: 0.9 });
    const fs = [...new Set(playedModes(p).map(s => +s.f.toFixed(3)))].slice(0, 4); return fs.map(f => f / fs[0]); };
  const dev = r => Math.max(...r.map(x => Math.abs(x - Math.round(x))));
  const s = ratios('String'), d = ratios('Drum');
  check('String partials near whole numbers', dev(s) < 0.15, s.map(x => x.toFixed(2)).join(' : '));
  check('Drum partials not whole numbers', dev(d) > 0.2, d.map(x => x.toFixed(2)).join(' : ')); }

// ---------- 6. Known issue: the octave trap (report only, pending Alex's decision at gate 1) ----------
// Moving the strike point and then touching Stiffness re-picks the tuned partial with the new strike point.
{ const NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];
  const name = f => { const mm = Math.round(69 + 12 * Math.log2(f / 440)); return NAMES[(mm % 12 + 12) % 12] + (Math.floor(mm / 12) - 1); };
  for (const shape of ['String', 'Twins']) {
    const { p, m, g } = appLoad(shape, null, 32000), free = g.P.map((_, i) => i).filter(i => !g.F[i]);
    const heard = () => { m({ t: 'note', f: E3, v: 0.9 }); return playedModes(p)[0].f; };
    const a = heard(); m({ t: 'hit', i: free[1], a: g.axis }); const b = heard();
    m({ t: 'p', k: 'ratio', v: 6.45 }); const c = heard();
    console.log(`INFO known issue, ${shape}: key E3 sounds ${name(a)} on load, ${name(b)} after moving strike near the end, ${name(c)} after one Stiffness tap`);
  }
}
console.log(failed ? `\n${failed} claim(s) FAILED` : '\nall taught claims verified');
process.exit(failed ? 1 : 0);
