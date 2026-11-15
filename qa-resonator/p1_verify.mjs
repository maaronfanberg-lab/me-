// Phone performance P1 — proofs. Usage:
//   node qa-resonator/p1_verify.mjs [baseline.html]
// baseline defaults to the preview as it was before P1 (git show 4d9404e8d63176c1e1e8ee5e50c494bc4a1fa84f:apps/resonator-next.html;
// on a shallow checkout fetch that commit first). P1_SKIP_COST=1 skips the timing table.
// 1. Sleep and governor off: output bit-identical to the baseline (skipping voices at rest is exact).
// 2. Sleep on: the difference stays below -100 dBFS while voices really do go to sleep.
// 3. CPU: what skipping and sleeping save (this machine, not a phone).
// 4. Governor: sheds the quietest older voice smoothly, respects the limit, recovers.
// 5. The CPU estimate agrees with the measured cost.
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import path from 'node:path';
const here = path.dirname(new URL(import.meta.url).pathname), root = path.join(here, '..');
let base = process.argv[2];
if (!base) { base = '/tmp/resonator-next-before-p1.html'; fs.writeFileSync(base, execSync('git show 4d9404e8d63176c1e1e8ee5e50c494bc4a1fa84f:apps/resonator-next.html', { cwd: root, maxBuffer: 1 << 26 })); }
const B = await import('./harness.mjs?src=' + base);
const N = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
let failed = 0;
const check = (name, ok, detail = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };

// render with optional extra messages (sent after the knobs) and perf settings
function render(H, { rate = 32000, secs = 4, shape = 'String', params = {}, mode = 0, pk = 0, mods = null, notes, extra = [], perf = null, hook = null } = {}) {
  const p = H.makeProc(rate), S = H.SHAPES[shape], g = S.make(S.def), NN = g.P.length;
  const idx = f => Math.min(NN - 1, Math.max(0, Math.round(f * (NN - 1))));
  const pos = new Float32Array(NN * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  const m = d => p.port.onmessage({ data: d });
  m({ t: 'struct', n: NN, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  m({ t: 'mode', v: mode }); m({ t: 'pk', v: pk }); m({ t: 'spec', v: 0 });   // J1 ratchet: as the pages send it
  for (const k in H.KNOBS) if (!['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k)) m({ t: 'p', k, v: k in params ? params[k] : H.KNOBS[k].val });
  for (const k of ['bow']) if (k in params) m({ t: 'p', k, v: params[k] });
  if (mods) mods.forEach((md, i) => m({ t: 'mod', i, ...md }));
  m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'mic2', i: idx(0.62), a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
  for (const d of extra) m(typeof d === 'function' ? d(g, idx) : d);
  if (perf) m({ t: 'perf', ...perf });
  const pat = notes || Array.from({ length: 16 }, (_, i) => ({ at: i * 0.25, semi: [0, 3, 5, 7, 10, 12, 7, 3][i % 8], v: i % 2 ? 0.55 : 0.9 }));
  const Bk = 128, nb = Math.ceil(secs * rate / Bk), L = new Float32Array(nb * Bk), R = new Float32Array(nb * Bk), bl = new Float32Array(Bk), br = new Float32Array(Bk);
  let ni = 0;
  for (let b = 0; b < nb; b++) {
    const t = b * Bk / rate;
    while (ni < pat.length && pat[ni].at <= t) { const n = pat[ni++]; if (n.off) m({ t: 'off', f: 440 * Math.pow(2, (52 + n.semi - 69) / 12) }); else m({ t: 'note', f: 440 * Math.pow(2, (52 + n.semi - 69) / 12), v: n.v }); }
    if (hook) hook(p, b, t, m);
    bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * Bk); R.set(br, b * Bk);
  }
  return { L, R, p };
}
const same = (a, b) => a.L.length === b.L.length && a.L.every((v, i) => Object.is(v, b.L[i])) && a.R.every((v, i) => Object.is(v, b.R[i]));
const maxDiff = (a, b) => { let m = 0; for (let i = 0; i < a.L.length; i++) m = Math.max(m, Math.abs(a.L[i] - b.L[i]), Math.abs(a.R[i] - b.R[i])); return m; };
const sparse = (n, gap) => Array.from({ length: n }, (_, i) => ({ at: 0.05 + i * gap, semi: [0, 7, 3, 10, 5, 12][i % 6], v: 0.85 }));

// ---------- 1. bit-identical with sleep and governor off ----------
const cfgs = [{ name: 'default' }];
for (const s of Object.keys(N.SHAPES).filter(s => s in B.SHAPES)) cfgs.push({ name: 'shape ' + s, shape: s });   // T1: the Tower exists only in the preview
// the baseline's knobs: a control added after P1 (e.g. Reverb) legitimately changes the sound
// J1: only the controls the preview still has (the others no longer exist in its engine)
const J1_KEYS = ['ratio', 'decay', 'loss', 'sub', 'drive', 'hard', 'blend', 'gain', 'tune', 'tone', 'bite', 'nl', 'angle', 'voices'];
for (const k in B.KNOBS) for (const e of ['min', 'max']) if (J1_KEYS.includes(k)) cfgs.push({ name: `${k} ${e}`, params: { [k]: B.KNOBS[k][e] } });
for (const v of [2, 4, 8]) for (const s of ['String', 'Drum', 'Tank']) cfgs.push({ name: `${s} ${v} voices, sparse`, shape: s, params: { voices: v }, notes: sparse(3, 1.1) });
cfgs.push({ name: '8 voices dense', params: { voices: 8 } });
// J1: plectrum, oscillator, wind, bow, feedback, effects, space, extra mics and modulators left the preview
let bad = [];
for (const c of cfgs) { const { name, ...o } = c; if (!same(render(B, o), render(N, o))) bad.push(name); }
check(`sleep and governor off: bit-identical to the baseline (${cfgs.length} setups)`, bad.length === 0, bad.length ? 'differ: ' + bad.join(', ') : '');

// ---------- 2. sleep on: inaudible difference, voices do sleep ----------
const slp = [];
for (const s of ['String', 'Drum', 'Tank', 'Chime']) for (const v of [1, 4, 8]) {
  const o = { shape: s, secs: 6, params: { voices: v, decay: 0.4 }, notes: sparse(4, 1.3) };
  const a = render(N, o), b = render(N, { ...o, perf: { sleep: 1 } });
  slp.push({ s, v, d: maxDiff(a, b), sleeps: b.p.sleeps });
}
const worst = Math.max(...slp.map(r => r.d)), slept = slp.reduce((t, r) => t + r.sleeps, 0);
check('sleep on: largest output difference below -100 dBFS', worst < 1e-5, `worst ${worst.toExponential(2)} (${(20 * Math.log10(Math.max(worst, 1e-30))).toFixed(0)} dBFS) over ${slp.length} setups`);
check('sleep on: voices really go to sleep', slept > 0 && slp.filter(r => r.sleeps > 0).length >= 8, `${slept} sleeps; ` + slp.map(r => `${r.s}/${r.v}:${r.sleeps}`).join(' '));

// ---------- 3. CPU (this machine; a phone differs) ----------
if (!process.env.P1_SKIP_COST) {
// Each number comes from a fresh process (p1_cost_one.mjs): several engine copies in one process share
// compiled code and distort small timings. Steady state after 1.5 s; median of 3 processes.
const costOne = (src, o) => Number(execSync(`node ${JSON.stringify(path.join(here, 'p1_cost_one.mjs'))} ${JSON.stringify(src)} ${JSON.stringify(JSON.stringify(o))}`, { cwd: root }).toString());
const med3 = (src, o) => { const r = [costOne(src, o), costOne(src, o), costOne(src, o)].sort((x, y) => x - y); return r[1]; };
const NEXT = path.join(root, 'apps/resonator-next.html'), rows = [];
for (const [label, o] of [
  ['idle, String, no notes', { notes: [] }],
  ['idle, Tank, no notes', { shape: 'Tank', notes: [] }],
  ['String 8 voices, one note a second', { params: { voices: 8, decay: 1 }, notes: sparse(8, 1), secs: 8 }],
  ['Tank 8 voices, one note a second', { shape: 'Tank', params: { voices: 8, decay: 1 }, notes: sparse(8, 1), secs: 8 }],
  ['Tank 4 voices, dense (all ringing)', { shape: 'Tank', params: { voices: 4 } }],
  ['String 8 voices, dense (all ringing)', { params: { voices: 8 } }],
  ['effects + space, String', { params: { att: 0.8, fxCho: 0.6, fxDly: 0.6, spImg: 0.8, spRefl: 0.6 } }],
]) {
  const b0 = med3(base, o), n0 = med3(NEXT, o), n1 = med3(NEXT, { ...o, perf: { sleep: 1 } });
  rows.push({ case: label, before: (100 * b0).toFixed(1) + '%', 'after (exact)': (100 * n0).toFixed(1) + '%', 'after + sleep': (100 * n1).toFixed(1) + '%' });
}
console.table(rows);
}

// ---------- 4. governor ----------
{
  const NS = { voices: 4, decay: 6 }, notes = sparse(4, 0.25);
  let shed = null, after = null, capNote = null, jumpMute = 0, jumpRef = 0;
  const run = (doGov) => render(N, { secs: 3, params: NS, notes: [...notes, { at: 1.6, semi: 5, v: 0.85 }], perf: { sleep: 1, gov: 1 }, hook: (p, b, t) => {
    if (doGov && b === Math.round(1.2 * 32000 / 128)) { const aw = p.awakeCount(); p.governCpu(0.95); p.governCpu(0.95); shed = { awBefore: aw, muted: [...p.vMute.slice(0, 4)], cap: p.vCap, acts: p.govActs, ages: [...p.vAge.slice(0, 4)] }; }
    if (doGov && b === Math.round(1.55 * 32000 / 128)) after = { rest: [...p.vRest.slice(0, 4)], muted: [...p.vMute.slice(0, 4)], aw: p.awakeCount() };
    if (doGov && b === Math.round(1.7 * 32000 / 128)) capNote = { aw: p.awakeCount(), cap: p.vCap };
  } });
  const g = run(true), ref = run(false);
  const i0 = Math.round(1.2 * 32000), i1 = Math.round(1.25 * 32000);
  for (let i = i0 + 1; i < i1; i++) { jumpMute = Math.max(jumpMute, Math.abs(g.L[i] - g.L[i - 1])); jumpRef = Math.max(jumpRef, Math.abs(ref.L[i] - ref.L[i - 1])); }
  const mutedIdx = shed.muted.indexOf(1), newest = shed.ages.indexOf(Math.max(...shed.ages));
  check('governor: two hot readings mute one older voice and lower the limit', shed.awBefore >= 2 && shed.acts === 1 && shed.muted.filter(x => x).length === 1 && mutedIdx !== newest && shed.cap === shed.awBefore - 1, JSON.stringify(shed));
  check('governor: the muted voice is asleep within 0.35 s', after.rest[mutedIdx] === 1 && after.muted[mutedIdx] === 0, JSON.stringify(after));
  check('governor: a new note stays within the limit', capNote.aw <= capNote.cap, JSON.stringify(capNote));
  check('governor: no click when a voice is let go (largest step vs the same moment unmuted)', jumpMute <= jumpRef * 1.05 + 1e-6, `${jumpMute.toFixed(4)} vs ${jumpRef.toFixed(4)}`);
  check('governor: output finite', g.L.every(Number.isFinite) && g.R.every(Number.isFinite));
  const p = render(N, { secs: 0.1, params: NS, perf: { sleep: 1, gov: 1 }, notes: [] }).p;
  p.vCap = 2; for (let i = 0; i < 8; i++) p.governCpu(0.5);
  check('governor: the limit climbs back after 2 s under 60%', p.vCap === 3, `cap ${p.vCap}`);
  // process() must consult the governor only when the page has switched it on
  const calls = { off: 0, on: 0 };
  for (const mode of ['off', 'on']) render(N, { secs: 1.2, params: NS, notes, perf: mode === 'on' ? { gov: 1 } : null,
    hook: (p, b) => { if (b === 0) { const g0 = p.governCpu.bind(p); p.governCpu = c => { calls[mode]++; return g0(c); }; } } });
  check('governor consulted only when the page turns it on', calls.off === 0 && calls.on >= 4, JSON.stringify(calls));
}

// ---------- 5. the CPU estimate agrees with a precise clock around the same work ----------
{
  const vals = []; let lastN = 0, busy = 0, frames = 0;
  const o = { shape: 'Tank', secs: 6, params: { voices: 4, decay: 4 }, notes: sparse(8, 0.6),
    hook: (p, b) => {
      if (b === 0) { const inner = p.processInner.bind(p);
        p.processInner = (i, out) => { const t = performance.now(); const r = inner(i, out); if (p._on) { busy += performance.now() - t; frames += 128; } return r; }; }
      if (p.cpuN < lastN && p._on) vals.push(p.cpu);
      if (p.cpuN < lastN) p._on = true;   // start at a window boundary, after the first window
      lastN = p.cpuN; } };
  render(N, o);
  const avg = vals.reduce((a, b) => a + b, 0) / Math.max(1, vals.length), exact = busy / 1000 / (frames / 32000);
  check('CPU estimate (1 ms clock) matches a precise clock on the same work, within 10%', vals.length >= 15 && Math.abs(avg - exact) / exact < 0.10,
    `${vals.length} readings: engine ${(100 * avg).toFixed(1)}% vs precise ${(100 * exact).toFixed(1)}%`);
}
console.log(failed ? `\n${failed} check(s) FAILED` : '\nall P1 checks pass');
process.exit(failed ? 1 : 0);
