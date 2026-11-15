// Stage J1 proof: the stripped engine is the old engine for everything the Tank page can do.
//   node qa-resonator/j1_verify.mjs [old.html] [new.html]
// old.html defaults to the preview just before J1 (git show e3010d51298f79982a0e2cc1f960cb3824784764:apps/resonator-next.html;
// on a shallow checkout fetch that commit first).
// For every setup, the old engine gets the messages the page sent before J1 (every removed control at its
// default, pk/mode/spec/mic2), the new engine gets what the page sends now; both are rendered sample by sample
// and must agree exactly (Object.is on every sample, both channels). The new engine is also fed the OLD
// message stream, to prove that stray messages for removed controls change nothing.
// Setups: every Size; each kept control at its minimum, a middle value and its maximum; voices 1, 3 and 8 with
// chords; strike/mic moves; a mass moved; Hush in the middle of a ring; retuning mid-ring; two sample rates.
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
const here = path.dirname(new URL(import.meta.url).pathname), root = path.resolve(here, '..');
let oldSrc = process.argv[2];
if (!oldSrc) { oldSrc = '/tmp/resonator-next-before-j1.html'; fs.writeFileSync(oldSrc, execSync('git show e3010d51298f79982a0e2cc1f960cb3824784764:apps/resonator-next.html', { cwd: root, maxBuffer: 1 << 26 })); }
const newSrc = process.argv[3] || path.join(root, 'apps/resonator-next.html');
const A = await import('./harness.mjs?src=' + oldSrc), B = await import('./harness.mjs?src=' + newSrc);
const OLD_SENDS = ['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','width','pkAp','pkSpc','pkRes','pkQ','amp','bass','treb','cab','splash','fbAmt','fbTime','voices','coup','regime','rswitch','rphi','mem','memSpan','infer','spread','att','attC','fxCho','fxDly','fxFb','fxWow','fxTrem','fxSat','spImg','spDist','spRefl','spDop','spRot','spElev','bowSpd','bowVc','wind','inGain','rvMix','rvTime','rvTone','rvPre'];
const NEW_SENDS = ['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices'];
const KEEP = ['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices'];
const LVL = 8.8716;

function body(C) {
  const g = B.SHAPES.Tank.make(C), pos = new Float32Array(g.P.length * 3);
  g.P.forEach((q, i) => pos.set(q, i * 3));
  return { g, struct: { t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis } };
}
// one setup = a list of timed events; 'build' expands to the page's message burst for that version
function stream(kind, setup) {
  const KN = kind === 'old' ? A.KNOBS : B.KNOBS, out = [];
  const val = {}; for (const k in KN) val[k] = KN[k].val; Object.assign(val, setup.val || {});
  const { g, struct } = body(setup.C);
  const free = g.P.map((_, i) => i).filter(i => !g.F[i]);
  const burst = () => {
    const m = [{ ...struct }];
    for (const k of (kind === 'new' ? NEW_SENDS : OLD_SENDS)) m.push({ t: 'p', k, v: val[k] });
    if (kind !== 'new') m.push({ t: 'pk', v: 0 }, { t: 'mode', v: 0 }, { t: 'spec', v: 0 });
    m.push({ t: 'lvl', v: LVL });
    return m;
  };
  for (const ev of setup.events) {
    if (ev.t === 'build') out.push({ at: ev.at, m: burst() });
    else if (ev.t === 'mic') { const m = [{ t: 'mic', i: free[ev.k % free.length], a: ev.a ?? g.axis }]; if (kind !== 'new') m.push({ t: 'mic2', i: free[(ev.k + (free.length >> 1)) % free.length] }); out.push({ at: ev.at, m }); }
    else out.push({ at: ev.at, m: [ev.m] });
  }
  return out;
}
// The CPU meter reads Date.now around each block, and the governor acts on what it measures; that is the
// machine's timing, not the page's, so the clock is held still while rendering (both engines alike).
function render(H, rate, evs, secs) {
  const now = Date.now; Date.now = () => 0;
  try { return render1(H, rate, evs, secs); } finally { Date.now = now; }
}
function render1(H, rate, evs, secs) {
  const p = H.makeProc(rate), send = d => p.port.onmessage({ data: d });
  const Bk = 128, nb = Math.ceil(secs * rate / Bk), L = new Float32Array(nb * Bk), R = new Float32Array(nb * Bk);
  const bl = new Float32Array(Bk), br = new Float32Array(Bk); let e = 0;
  const ev = [...evs].sort((a, b) => a.at - b.at);
  for (let b = 0; b < nb; b++) {
    const t = b * Bk / rate;
    while (e < ev.length && ev[e].at <= t) { for (const m of ev[e].m) send(structuredClone(m)); e++; }
    bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * Bk); R.set(br, b * Bk);
  }
  return { L, R };
}
const note = (at, semi, v) => ({ at, m: { t: 'note', f: 440 * Math.pow(2, (52 + semi - 69) / 12), v } });
const off = (at, semi) => ({ at, m: { t: 'off', f: 440 * Math.pow(2, (52 + semi - 69) / 12) } });
const tune = [note(0.05, 0, 0.9), note(0.45, 7, 0.55), off(0.5, 7), note(0.8, 3, 0.75), note(1.1, 12, 0.9), note(1.15, 15, 0.6)];

const setups = [];
for (let C = 5; C <= 9; C++) setups.push({ name: `Size ${C}`, C, events: [{ t: 'build', at: 0 }, ...tune] });
for (const k of KEEP) {
  const K = B.KNOBS[k];
  for (const v of [K.min, +(K.min + (K.max - K.min) * 0.37).toFixed(6), K.max]) {
    if (k === 'voices' && v !== K.min && v !== K.max) continue;
    setups.push({ name: `${k}=${v}`, silent: k === 'gain' && v === 0, C: 7, val: { [k]: k === 'voices' ? Math.round(v) : v }, events: [{ t: 'build', at: 0 }, ...tune] });
  }
}
setups.push({ name: 'voices 3, chord', C: 7, val: { voices: 3 }, events: [{ t: 'build', at: 0 }, note(0.05, 0, 0.8), note(0.06, 4, 0.7), note(0.07, 7, 0.9), note(0.6, 12, 0.6), note(0.61, 16, 0.6), note(0.62, 19, 0.6), note(0.63, 24, 0.6)] });
setups.push({ name: 'strike + mic moved, axis Z', C: 7, events: [{ t: 'build', at: 0 }, { t: 'mic', at: 0.02, k: 11, a: 2 }, { at: 0.03, m: { t: 'hit', i: 20, a: 2 } }, ...tune] });
setups.push({ name: 'mass moved mid-ring', C: 7, events: [{ t: 'build', at: 0 }, note(0.05, 0, 0.9), { at: 0.4, m: { t: 'mv', i: 9, x: 0.02, y: 0.21, z: 0.11 } }, note(0.7, 5, 0.8)] });
setups.push({ name: 'Hush mid-ring', C: 7, val: { decay: 20 }, events: [{ t: 'build', at: 0 }, note(0.05, 0, 0.9), { at: 0.5, m: { t: 'hush' } }, note(0.9, 7, 0.7)] });
setups.push({ name: 'retune mid-ring (Stiffness, Substrate, Trim, Nonlinearity, Angle)', C: 7, val: { nl: 2 }, events: [{ t: 'build', at: 0 }, note(0.05, 0, 1),
  { at: 0.3, m: { t: 'p', k: 'ratio', v: 9.5 } }, { at: 0.5, m: { t: 'p', k: 'tune', v: -300 } }, { at: 0.7, m: { t: 'p', k: 'sub', v: 0.004 } }, note(0.8, 3, 0.7),
  { at: 1.0, m: { t: 'p', k: 'nl', v: 6 } }, { at: 1.1, m: { t: 'p', k: 'angle', v: 0.9 } }, note(1.2, 7, 1)] });
setups.push({ name: 'new body mid-ring (Size)', C: 6, events: [{ t: 'build', at: 0 }, note(0.05, 0, 0.9), { t: 'build', at: 0.6 }, note(0.8, 2, 0.9)] });
setups.push({ name: 'P1 sleep + governor, 8 voices', C: 9, val: { voices: 8, decay: 0.5 }, events: [{ t: 'build', at: 0 }, { at: 0.01, m: { t: 'perf', sleep: 1, gov: 1 } },
  ...Array.from({ length: 14 }, (_, i) => note(0.05 + i * 0.09, [0, 3, 5, 7, 10, 12, 15][i % 7], 0.5 + 0.03 * i)), { at: 1.0, m: { t: 'perfTest', c: 0.95 } }, { at: 1.3, m: { t: 'perfTest', c: 0.95 } }, note(1.5, 0, 1)] });
setups.push({ name: 'buffered engine (osMax 10)', C: 9, events: [{ t: 'build', at: 0 }, { at: 0.01, m: { t: 'p', k: 'osMax', v: 10 } }, { at: 0.02, m: { t: 'p', k: 'ratio', v: 14 } }, note(0.05, 24, 1), note(0.5, 31, 1)] });

let fails = 0, n = 0, peakMin = 1;
const t0 = Date.now();
const quick = !!process.env.J1_QUICK;   // a few setups at one rate, for mutation tests
for (const rate of quick ? [32000] : [32000, 48000]) for (const su of quick ? setups.slice(0, 3) : setups) {
  const secs = 1.8;
  const a = render(A, rate, stream('old', su), secs), b = render(B, rate, stream('new', su), secs), c = render(B, rate, stream('old', su), secs);
  let same = true, sameC = true, pk = 0, md = 0;
  for (let i = 0; i < a.L.length; i++) {
    if (!Object.is(a.L[i], b.L[i]) || !Object.is(a.R[i], b.R[i])) { same = false; md = Math.max(md, Math.abs(a.L[i] - b.L[i])); }
    if (!Object.is(a.L[i], c.L[i]) || !Object.is(a.R[i], c.R[i])) sameC = false;
    pk = Math.max(pk, Math.abs(a.L[i]));
  }
  n++; if (!su.silent) peakMin = Math.min(peakMin, pk);
  if (!same || !sameC || !(pk > 1e-3 || su.silent)) { fails++; console.log(`FAIL ${rate} ${su.name}: new==old ${same} (max diff ${md}), new fed old messages==old ${sameC}, peak ${pk.toFixed(4)}`); }
}
console.log(`J1 bit-identity: ${n - fails}/${n} setups identical (both channels, every sample; quietest sounding setup peak ${peakMin.toFixed(4)}; Level 0 is silent in both) in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
process.exit(fails ? 1 : 0);
