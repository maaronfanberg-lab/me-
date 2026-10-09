// RESONATOR offline harness — Stage 1 audit (read-only; does not modify resonator.html)
import fs from 'node:fs';

const SRC = new URL(import.meta.url).searchParams.get('src') || new URL('../apps/resonator.html', import.meta.url).pathname;
const html = fs.readFileSync(SRC, 'utf8');
const wStart = html.indexOf('const WORKLET = String.raw`') + 'const WORKLET = String.raw`'.length;
const wEnd = html.indexOf('`;', wStart);
export const WORKLET = html.slice(wStart, wEnd);
const sStart = html.indexOf('const SHAPES = {');
const sEnd = html.indexOf('\n};', sStart) + 3;
export const SHAPES = new Function(html.slice(sStart, sEnd) + '\nreturn SHAPES;')();
const kStart = html.indexOf('const KNOBS={');
const kEnd = html.indexOf('\n};', kStart) + 3;
const stateStub = { n: 14, hitIdx: 0, micIdx: 0 };
export const KNOBS = new Function('state', 'fmtRate', html.slice(kStart, kEnd) + '\nreturn KNOBS;')(stateStub, () => '');

// seeded PRNG (mulberry32) — installed on Math.random only when requested
export function seedRandom(seed) {
  let a = seed >>> 0;
  const orig = Math.random;
  Math.random = () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return () => { Math.random = orig; };
}

export function makeProc(rate) {
  let K = null;
  class Shim { constructor() { this.port = { onmessage: null, postMessage: () => {} }; } }
  new Function('AudioWorkletProcessor', 'registerProcessor', 'sampleRate', WORKLET)(Shim, (n, k) => { K = k; }, rate);
  return new K();
}

// Render a fixed, deterministic performance: shape, params, note pattern.
export function render({ rate = 48000, secs = 4, shape = 'String', params = {}, pk = 0, mode = 0,
                         mods = null, notes = null, n = null, hitF = null, micF = null, mic2F = 0.62, lvl = null } = {}) {
  const p = makeProc(rate);
  const S = SHAPES[shape];
  const g = S.make(n ?? S.def);
  const NN = g.P.length, idx = f => Math.min(NN - 1, Math.max(0, Math.round(f * (NN - 1))));
  const hitI = hitF == null ? g.hit : idx(hitF), micI = micF == null ? g.mic : idx(micF), mic2I = idx(mic2F);
  const pos = new Float32Array(g.P.length * 3);
  g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  const m = (d) => p.port.onmessage({ data: d });
  m({ t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])),
      sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  m({ t: 'mode', v: mode }); m({ t: 'pk', v: pk });
  if (lvl != null) m({ t: 'lvl', v: lvl });
  for (const k in KNOBS) if (!['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k))
    m({ t: 'p', k, v: k in params ? params[k] : KNOBS[k].val });
  for (const k of ['bow']) if (k in params) m({ t: 'p', k, v: params[k] });
  if (mods) mods.forEach((md, i) => m({ t: 'mod', i, ...md }));
  m({ t: 'mic', i: micI, a: g.axis }); m({ t: 'mic2', i: mic2I, a: g.axis }); m({ t: 'hit', i: hitI, a: g.axis });
  // pattern: 16 notes, 0.25 s apart, minor-pentatonic around E3, alternating velocity
  const pat = notes || Array.from({ length: 16 }, (_, i) => ({ at: i * 0.25, semi: [0, 3, 5, 7, 10, 12, 7, 3][i % 8], v: i % 2 ? 0.55 : 0.9 }));
  const B = 128, nb = Math.ceil(secs * rate / B);
  const L = new Float32Array(nb * B), R = new Float32Array(nb * B);
  const bl = new Float32Array(B), br = new Float32Array(B);
  let ni = 0;
  for (let b = 0; b < nb; b++) {
    const t = b * B / rate;
    while (ni < pat.length && pat[ni].at <= t) { const n = pat[ni++]; m({ t: 'note', f: 440 * Math.pow(2, (52 + n.semi - 69) / 12), v: n.v }); }
    bl.fill(0); br.fill(0);
    p.process([], [[bl, br]]);
    L.set(bl, b * B); R.set(br, b * B);
  }
  return { L, R, rate };
}
