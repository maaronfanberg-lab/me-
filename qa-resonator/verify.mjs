// Verification of F1-F3 against the original engine.
import { lufs, truePeakDb, health, sameBits, bandFrames, diffDb } from './metrics.mjs';
const OLD = await import('./harness.mjs?src=' + new URL('./resonator.orig.html', import.meta.url).pathname);
const NEW = await import('./harness.mjs');
const SEED = 0x2545F491, SECS = 4;
const oldR = o => { const u = OLD.seedRandom(SEED); try { return OLD.render({ secs: SECS, ...o }); } finally { u(); } };
const newR = o => NEW.render({ secs: SECS, ...o });   // NEW must not depend on Math.random at all
const peakOf = r => Math.max(...[r.L, r.R].map(x => { let m = 0; for (const v of x) m = Math.max(m, Math.abs(v)); return m; }));
// new output = old output delayed by exactly 16 samples (the limiter lookahead), bit for bit
const shifted = (o, n) => { for (let i = 0; i < 16; i++) if (n[i] !== 0) return false;
  for (let i = 0; i + 16 < n.length; i++) if (!Object.is(o[i], n[i + 16])) return false; return true; };
const rep = { additive: { identical: 0, limited: 0, broke: [] }, determinism: [], shapes: [], ceiling: [], knobs: [] };

// 1. ADDITIVE: every config the audit used. Where the old output never crossed the new
// ceiling, the new engine (lvl=1) must be bit-identical — randomness included.
const configs = [{}];
for (const s of Object.keys(NEW.SHAPES)) configs.push({ shape: s });
for (const k in NEW.KNOBS) for (const e of ['min', 'max']) configs.push({ params: { [k]: NEW.KNOBS[k][e] } });
for (const p of [{ att: 0.8 }, { regime: 1 }, { infer: 1, voices: 4, spread: 1 }, { mem: 1 }, { bow: 0.16 },
  { att: 0.8, fxCho: 0.6, fxDly: 0.6, fxWow: 0.6, fxTrem: 0.6, fxSat: 0.6 }, { att: 0.8, regime: 1, infer: 1, mem: 1, voices: 4, coup: 1 }])
  configs.push({ params: p });
configs.push({ mods: [{ d: 'tune', r: 4, a: 1, sh: 4 }] }, { mode: 1 }, { pk: 1 }, { pk: 2 });
for (const c of configs) {
  const a = oldR(c), b = newR(c);
  if (Math.max(truePeakDb(a.L), truePeakDb(a.R)) < -2.5) { if (shifted(a.L, b.L) && shifted(a.R, b.R)) rep.additive.identical++; else rep.additive.broke.push(JSON.stringify(c)); }
  else rep.additive.limited++;
}
// 2. DETERMINISM with no seeding anywhere
for (const [name, c] of Object.entries({ attractor: { params: { att: 0.8 } }, regimes: { params: { regime: 1 } },
  inference: { params: { infer: 1, voices: 4, spread: 1 } }, 'fx stack': { params: { att: 0.8, fxCho: 0.6, fxDly: 0.6, fxWow: 0.6, fxTrem: 0.6, fxSat: 0.6 } },
  'random LFO': { mods: [{ d: 'tune', r: 4, a: 1, sh: 4 }] } })) {
  const a = newR(c), b = newR(c); rep.determinism.push({ name, identical: sameBits(a.L, b.L) && sameBits(a.R, b.R) });
}
// 3. SHAPE LEVELS with calibration as the app sends it
const LV = { String: 1.4928, Tine: 0.8082, Chime: 0.866, Drum: 0.9784, Hoop: 1.5171, Web: 0.7379, Tank: 8.8716, Twins: 1.8793 };
for (const s in LV) { const r = newR({ shape: s, lvl: LV[s] }); rep.shapes.push({ shape: s, lufs: +lufs(r.L, r.R, r.rate).toFixed(2), tp: +Math.max(truePeakDb(r.L), truePeakDb(r.R)).toFixed(2) }); }
// 4. CEILING: worst cases from the audit, each shape, calibrated
const STRESS = { drive: 4, nl: 8, fbAmt: 0.9, amp: 1, bass: 2, treb: 2, gain: 1.6, att: 1, regime: 1, infer: 1, mem: 1, voices: 8, fxDly: 1, fxFb: 0.85, fxSat: 1, coup: 1 };
if (!process.env.SKIP_CEIL) for (const s in LV) for (const [tag, params] of [['stress', STRESS], ['feedback max', { fbAmt: 1 }], ['gain max', { gain: 1.6 }], ['drive max', { drive: 4 }]]) {
  const r = newR({ shape: s, params, lvl: LV[s] }); const h = health(r.L).nonFinite + health(r.R).nonFinite;
  rep.ceiling.push({ shape: s, tag, nonFinite: h, tp: +Math.max(truePeakDb(r.L), truePeakDb(r.R)).toFixed(2), lufs: +lufs(r.L, r.R, r.rate).toFixed(1) });
}
console.log(JSON.stringify({ additive: rep.additive, determinism: rep.determinism }, null, 1));
console.table(rep.shapes); console.table(rep.ceiling);
