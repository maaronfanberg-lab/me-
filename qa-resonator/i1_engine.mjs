// Stage I engine checks on the Tank, the one body this version has.
//   node qa-resonator/i1_engine.mjs [page]
// 1. Sustain (the old Decay): how long it actually rings. The Tank at its defaults, one key (E3, strength
//    0.8), Sustain from short to long; the time until the sound has fallen 40 dB and 60 dB below its peak
//    (10 ms blocks), at the phone's default engine rate.
// 2. The worst the Tank page's own controls can do stays under the output ceiling with no NaN, and the same
//    setup renders bit-identically twice. (These used to be covered only through the extra-mic and
//    modulator suites, retired with those features.)
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const H = await import('./harness.mjs?src=' + (process.argv[2] || path.join(root, 'apps/resonator-next.html')));
const RATE = 32000, TANK_LVL = 8.8716;   // the page's SHAPE_LVL.Tank
let failed = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + ' — ' + detail); if (!ok) failed++; };

// ---------- 1. Sustain ----------
const fall = (x, db) => { let pk = 0; for (const v of x) pk = Math.max(pk, Math.abs(v)); const thr = pk * Math.pow(10, -db / 20), W = RATE / 100;
  let last = 0; for (let i = 0; i + W <= x.length; i += W) { let m = 0; for (let j = i; j < i + W; j++) m = Math.max(m, Math.abs(x[j])); if (m > thr) last = i + W; }
  return last / RATE; };
const rows = [];
for (const s of [0.3, 1, 2, 4, 8, 16]) {
  const r = H.render({ rate: RATE, secs: Math.max(3, 1.6 * s + 1), shape: 'Tank', params: { decay: s }, notes: [{ at: 0, semi: 0, v: 0.8 }], lvl: TANK_LVL });
  rows.push({ s, t40: fall(r.L, 40), t60: fall(r.L, 60) });
}
for (const r of rows) console.log(`Sustain ${String(r.s).padStart(4)} s: falls 40 dB in ${r.t40.toFixed(2)} s, 60 dB in ${r.t60.toFixed(2)} s`);
check('each longer Sustain rings clearly longer (60 dB time up by over 30% at every step)',
  rows.every((r, i) => i === 0 || r.t60 > rows[i - 1].t60 * 1.3), rows.map(r => r.t60.toFixed(2) + ' s').join(' → '));
// the knob shows 1.25 x the setting as the time to fade 40 dB (measured: 1.10-1.37 x across Size, Stiffness,
// Damping, mallet and key at Sustain 4)
check('from 1 s up, the time the knob shows (1.25 x the setting) is the measured time to fade 40 dB, within 15%',
  rows.filter(r => r.s >= 1).every(r => Math.abs(r.t40 / (1.25 * r.s) - 1) < 0.15),
  rows.filter(r => r.s >= 1).map(r => `shows ${(1.25 * r.s).toFixed(1)} s, measured ${r.t40.toFixed(2)} s`).join('; '));

// ---------- 2. worst case and determinism ----------
// Every control the Tank page still has, pushed to its loud or unstable end: 8 voices, Drive and Nonlinearity
// at the top, Level, Bite and Mic tone at the top, the hardest mallet, glancing, the longest Sustain, no
// damping, no substrate; both ends of Stiffness, Size and Trim; velocity and displacement pickups. An
// 8-note chord at full strength, then the same keys hammered every 0.1 s on top of the ringing.
const peak = x => { let p = 0; for (const v of x) p = Math.max(p, Math.abs(v)); return p; };
const nonFinite = r => { let b = 0; for (const v of r.L) if (!Number.isFinite(v)) b++; for (const v of r.R) if (!Number.isFinite(v)) b++; return b; };
const keys = [0, 3, 7, 10, 12, 15, 19, 24];
const notes = [...keys.map(semi => ({ at: 0, semi, v: 1 })),
  ...Array.from({ length: 24 }, (_, i) => ({ at: 0.4 + 0.1 * i, semi: keys[i % 8], v: 1 }))];
const loud = { voices: 8, drive: 4, nl: 8, gain: 1.6, bite: 2.5, tone: 12000, hard: 0, angle: 1, decay: 26, loss: 0, sub: 0 };
const cases = [
  { name: 'largest tank, stiffest, Trim +1200, velocity pickup', n: 9, params: { ...loud, ratio: 14, tune: 1200, blend: 0 } },
  { name: 'smallest tank, softest, Trim -1200, displacement pickup', n: 5, params: { ...loud, ratio: 0.25, tune: -1200, blend: 1 } },
  { name: 'one voice (a new key retunes the ringing body), default size', n: 7, params: { ...loud, voices: 1, ratio: 6, tune: 0, blend: 0.12 } },
];
for (const c of cases) {
  const r = H.render({ rate: RATE, secs: 4, shape: 'Tank', n: c.n, params: c.params, notes, lvl: TANK_LVL });
  const bad = nonFinite(r), pl = peak(r.L), pr = peak(r.R);
  check(`worst case, ${c.name}: peak under the ceiling, no NaN`, pl <= 0.78 && pr <= 0.78 && bad === 0 && pl > 0.1,
    `peak L ${pl.toFixed(3)}, R ${pr.toFixed(3)} (limit 0.78), non-finite samples ${bad}`);
}
{ const o = { rate: RATE, secs: 2, shape: 'Tank', n: 9, params: cases[0].params, notes, lvl: TANK_LVL };
  const a = H.render(o), b = H.render(o);
  let same = a.L.length === b.L.length;
  for (let i = 0; same && i < a.L.length; i++) if (!Object.is(a.L[i], b.L[i]) || !Object.is(a.R[i], b.R[i])) same = false;
  check('deterministic: the loudest setup renders bit-identically twice', same, same ? 'two renders bit-identical' : 'renders differ'); }

console.log(failed ? `\n${failed} Stage I engine check(s) FAILED` : '\nall Stage I engine checks pass');
process.exit(failed ? 1 : 0);
