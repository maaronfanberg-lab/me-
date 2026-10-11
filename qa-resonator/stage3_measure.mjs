// Stage 3 measurements: level of each new exciter relative to the mallet, plus character checks.
// Run from the repo root: node qa-resonator/stage3_measure.mjs [--json]
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const H = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
const RATE = 32000, B = 128, E3 = 440 * Math.pow(2, (52 - 69) / 12);

// script: [[block, message]...]; input(blockIndex) -> Float32Array(128) or null
function run(shape, script, blocks, input = null, extra = {}) {
  const p = H.makeProc(RATE), S = H.SHAPES[shape], g = S.make(S.def), m = d => p.port.onmessage({ data: d });
  const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i*3]=q[0]; pos[i*3+1]=q[1]; pos[i*3+2]=q[2]; });
  m({ t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  for (const k in H.KNOBS) if (!['size','mag','hit','mic','m1r','m1a','m2r','m2a','m3r','m3a'].includes(k)) m({ t: 'p', k, v: k in extra ? extra[k] : H.KNOBS[k].val });
  for (const k in extra) if (!(k in H.KNOBS)) m({ t: 'p', k, v: extra[k] });
  m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'mic2', i: g.mic, a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
  const L = new Float32Array(blocks * B), R = new Float32Array(blocks * B), bl = new Float32Array(B), br = new Float32Array(B);
  let si = 0;
  for (let b = 0; b < blocks; b++) {
    while (si < script.length && script[si][0] <= b) m(script[si++][1]);
    bl.fill(0); br.fill(0);
    const inp = input ? [[input(b)]] : [];
    p.process(inp, [[bl, br]]); L.set(bl, b * B); R.set(br, b * B);
  }
  return { L, R, p };
}
const sec = s => Math.round(s * RATE / B);
const peak = (x, a = 0, b = x.length) => { let m = 0; for (let i = a; i < b; i++) m = Math.max(m, Math.abs(x[i])); return m; };
const rms = (x, a = 0, b = x.length) => { let s = 0; for (let i = a; i < b; i++) s += x[i] * x[i]; return Math.sqrt(s / Math.max(1, b - a)); };
const bad = x => { let n = 0; for (const v of x) if (!Number.isFinite(v)) n++; return n; };
function centroid(x, a, len) { let num = 0, den = 0; const N = 4096;
  for (let k = 1; k < N / 2; k += 2) { let re = 0, im = 0; for (let i = 0; i < N; i++) { const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N), v = (x[a + i] || 0) * w; re += v * Math.cos(2 * Math.PI * k * i / N); im -= v * Math.sin(2 * Math.PI * k * i / N); }
    const e = re * re + im * im; num += e * k * RATE / N; den += e; } return num / den; }
function domFreq(x, a) { const N = 16384; let best = 0, bk = 0;
  for (let k = 20; k < 400; k++) { const f = k * RATE / N; if (f < 60 || f > 1200) continue; let re = 0, im = 0;
    for (let i = 0; i < N; i += 2) { const v = x[a + i] || 0; re += v * Math.cos(2 * Math.PI * k * i / N); im -= v * Math.sin(2 * Math.PI * k * i / N); }
    const e = re * re + im * im; if (e > best) { best = e; bk = k; } } return bk * RATE / N; }
function onset(x, frac = 0.5) { const pk = peak(x); for (let i = 0; i < x.length; i++) if (Math.abs(x[i]) >= frac * pk) return i / RATE; return -1; }

const SHAPES = ['String', 'Tine', 'Chime', 'Drum', 'Hoop', 'Web', 'Twins'];
const note = (f = E3, v = 0.9) => ({ t: 'note', f, v });
const rows = [];
let seed = 12345; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff * 2 - 1; };
const noise = () => { const a = new Float32Array(B); for (let i = 0; i < B; i++) a[i] = 0.1 * 1.732 * rnd(); return a; };   // RMS 0.1
for (const shape of SHAPES) {
  const mal = run(shape, [[1, note()]], sec(1.5));
  const ple = run(shape, [[1, { t: 'mode', v: 2 }], [1, note()]], sec(1.5));
  const osc = run(shape, [[1, { t: 'mode', v: 3 }], [1, note()], [sec(1.0), { t: 'off', f: E3 }]], sec(2.0));
  const wnd = run(shape, [], sec(2.0), null, { wind: 1 });
  const mic = run(shape, [], sec(1.5), noise, { micIn: 1, inGain: 0.5 });
  const mp = peak(mal.L);
  rows.push({ shape, mallet: +mp.toFixed(3),
    plectrum: +(peak(ple.L) / mp).toFixed(2),
    osc_hold: +(peak(osc.L, sec(0.5) * B, sec(1.0) * B) / mp).toFixed(2),
    osc_after_off: +(peak(osc.L, sec(1.6) * B, sec(2.0) * B) / Math.max(1e-9, peak(osc.L, sec(0.5) * B, sec(1.0) * B))).toFixed(3),
    wind: +(peak(wnd.L, sec(0.5) * B) / mp).toFixed(2), mic_noise: +(peak(mic.L, sec(0.3) * B) / mp).toFixed(2),
    nonFinite: bad(mal.L) + bad(ple.L) + bad(osc.L) + bad(wnd.L) + bad(mic.L) });
}
const med = k => { const v = rows.map(r => r[k]).sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };
// character checks on String
const pk = run('String', [[1, { t: 'mode', v: 2 }], [1, note()]], sec(1.2), null, { hard: 0 });
const ps = run('String', [[1, { t: 'mode', v: 2 }], [1, note()]], sec(1.2), null, { hard: 1 });
const ob = run('String', [[1, { t: 'mode', v: 3 }], [1, note()]], sec(1.5));
const w1 = run('String', [], sec(1), null, { wind: 0.6 }), w2 = run('String', [], sec(1), null, { wind: 0.6 });
let same = true; for (let i = 0; i < w1.L.length; i++) if (!Object.is(w1.L[i], w2.L[i])) { same = false; break; }
const out = { rows, median: { plectrum: med('plectrum'), osc_hold: med('osc_hold'), wind: med('wind'), mic_noise: med('mic_noise') },
  character: { plectrum_centroid_pick_Hz: Math.round(centroid(pk.L, sec(0.1) * B)), plectrum_centroid_finger_Hz: Math.round(centroid(ps.L, sec(0.1) * B)),
    plectrum_onset_ms: Math.round(1000 * onset(pk.L)), oscillator_pitch_Hz: +domFreq(ob.L, sec(0.6) * B).toFixed(1), wind_deterministic: same } };
if (process.argv.includes('--json')) console.log(JSON.stringify(out)); else { console.table(rows); console.log(JSON.stringify({ median: out.median, character: out.character }, null, 1)); }

// --check: fail the run when levels or character drift out of their measured ranges
if (process.argv.includes('--check')) {
  const m = out.median, c = out.character; const errs = [];
  const within = (name, v, lo, hi) => { if (!(v >= lo && v <= hi)) errs.push(`${name} ${v} outside ${lo}–${hi}`); };
  within('plectrum/mallet median', m.plectrum, 0.5, 1.3); within('oscillator/mallet median', m.osc_hold, 0.5, 1.3);
  within('wind/mallet median', m.wind, 0.35, 1.0); within('mic/mallet median', m.mic_noise, 0.3, 1.0);
  const nonFinite = rows.reduce((n, r) => n + r.nonFinite, 0); if (nonFinite) errs.push(`${nonFinite} non-finite samples`);
  const top = Math.max(...rows.map(r => Math.max(r.plectrum, r.osc_hold, r.wind, r.mic_noise) * r.mallet)); if (top > 0.78) errs.push(`peak ${top} above the ceiling`);
  within('oscillator pitch (Hz, E3 = 164.8)', c.oscillator_pitch_Hz, 163.5, 166.0); within('plectrum onset (ms)', c.plectrum_onset_ms, 3, 40);
  if (!c.wind_deterministic) errs.push('wind is not deterministic');
  console.log(errs.length ? 'FAIL Stage 3 levels — ' + errs.join('; ') : `PASS Stage 3 levels — plectrum ${m.plectrum}, oscillator ${m.osc_hold}, wind ${m.wind}, mic ${m.mic_noise} × mallet; peak ${top.toFixed(3)}; oscillator ${c.oscillator_pitch_Hz} Hz; onset ${c.plectrum_onset_ms} ms`);
  process.exit(errs.length ? 1 : 0);
}
