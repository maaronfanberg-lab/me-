// Stage 1 audit — measures RESONATOR as it stands. No edits to the app.
import { render, seedRandom, KNOBS, SHAPES } from './harness.mjs';
import { lufs, truePeakDb, health, bandFrames, diffDb, sameBits } from './metrics.mjs';
import fs from 'node:fs';

const SECS = 4, SEED = 12345;
const out = { determinism: [], health: [], knobs: [], mods: [] };
const seeded = (opts, seed = SEED) => { const u = seedRandom(seed); try { return render({ secs: SECS, ...opts }); } finally { u(); } };
const bands = r => ({ L: bandFrames(r.L, r.rate), R: bandFrames(r.R, r.rate), S: bandFrames(r.L.map((v, i) => v - r.R[i]), r.rate) });
const cmp = (A, B) => { const l = diffDb(A.L, B.L), r = diffDb(A.R, B.R), s = diffDb(A.S, B.S);
  return { mean: Math.max(l.mean, r.mean), side: s.mean }; };

// ---------- A. determinism: same inputs, two fresh processors, NO seeding ----------
const FEATURES = {
  default: {}, attractor: { att: 0.8 }, regimes: { regime: 1 }, inference: { infer: 1, voices: 4, spread: 1 },
  memory: { mem: 1 }, bow: { bow: 0.16 }, 'fx stack': { att: 0.8, fxCho: 0.6, fxDly: 0.6, fxWow: 0.6, fxTrem: 0.6, fxSat: 0.6 },
  'random LFO': { __mods: [{ d: 'tune', r: 4, a: 1, sh: 4 }] },
};
for (const [name, p] of Object.entries(FEATURES)) {
  const { __mods, ...params } = p;
  const a = render({ secs: SECS, params, mods: __mods }), b = render({ secs: SECS, params, mods: __mods });
  out.determinism.push({ name, identical: sameBits(a.L, b.L) && sameBits(a.R, b.R) });
}
// with seeding, randomness should be the ONLY source of difference
{ const p = { att: 0.8, regime: 1, infer: 1, mem: 1, voices: 4 };
  const a = seeded({ params: p }), b = seeded({ params: p });
  out.seededAllOn = sameBits(a.L, b.L) && sameBits(a.R, b.R); }

// ---------- B. numeric health & loudness: every shape, default and stress ----------
const STRESS = { drive: 4, nl: 8, fbAmt: 0.9, amp: 1, bass: 2, treb: 2, gain: 1.6, att: 1, regime: 1, infer: 1, mem: 1, voices: 8, fxDly: 1, fxFb: 0.85, fxSat: 1, coup: 1 };
for (const shape of Object.keys(SHAPES)) for (const [tag, params] of [['default', {}], ['stress', STRESS]]) {
  const r = seeded({ shape, params });
  const hL = health(r.L), hR = health(r.R);
  out.health.push({ shape, tag, nonFinite: hL.nonFinite + hR.nonFinite,
    peakDb: +Math.max(hL.peakDb, hR.peakDb).toFixed(2),
    truePeakDb: +Math.max(truePeakDb(r.L), truePeakDb(r.R)).toFixed(2),
    lufs: +lufs(r.L, r.R, r.rate).toFixed(2) });
}

// ---------- C. every knob: does min/max land vs default? ----------
// parents: settings a knob genuinely needs to have anything to act on (tested only if alone fails)
const PARENT = { fxFb: { fxDly: 0.6 }, fxWow: { fxDly: 0.6, att: 0.8 }, attC: { att: 0.8 }, spread: { infer: 1, voices: 4 },
  memSpan: { mem: 1 }, rswitch: { regime: 1 }, rphi: { regime: 1 }, fbTime: { fbAmt: 0.45 }, bowSpd: { bow: 0.16 },
  bowVc: { bow: 0.16 }, pkSpc: { __pk: 1 }, coup: { att: 0.8 }, fxCho: { att: 0.8 }, fxDly: { att: 0.8 }, fxTrem: { att: 0.8 },
  fxSat: { att: 0.8 }, infer: { voices: 4, spread: 1 }, spRefl: { spImg: 0.8 }, spDop: { spImg: 0.8 }, spRot: { spImg: 0.8 },
  spElev: { spImg: 0.8 }, width: {}, splash: {}, bite: {}, regime: {}, mem: {} };
const THRESH = 1.0, FAINT = 0.3;   // dB, mean |Δ| over audible third-octave bands & 40 ms frames
const special = { size: 'geometry', mag: 'visual', hit: 'index', mic: 'index', m1r: 'mod', m1a: 'mod', m2r: 'mod', m2a: 'mod', m3r: 'mod', m3a: 'mod' };
const cache = new Map();
const base = (parent, pk) => { const key = JSON.stringify([parent, pk]); if (!cache.has(key)) cache.set(key, bands(seeded({ params: parent, pk }))); return cache.get(key); };
function probe(k, parent) {
  const { __pk = 0, ...pp } = parent; const B = base(pp, __pk), K = KNOBS[k], res = {};
  for (const end of ['min', 'max']) {
    if (Math.abs(K[end] - K.val) < 1e-12) { res[end] = null; continue; }
    res[end] = cmp(B, bands(seeded({ params: { ...pp, [k]: K[end] }, pk: __pk })));
  }
  return res;
}
const verdict = r => { const m = Math.max(r.min?.mean ?? 0, r.max?.mean ?? 0, r.min?.side ?? 0, r.max?.side ?? 0);
  return { worst: +m.toFixed(2), v: m >= THRESH ? 'lands' : m >= FAINT ? 'faint' : 'inaudible' }; };
for (const k of Object.keys(KNOBS)) {
  if (special[k] === 'visual') { out.knobs.push({ k, label: KNOBS[k].label, v: 'n/a', note: 'drawing only, no audio by design' }); continue; }
  if (special[k] === 'mod') continue;
  let r, note = 'alone';
  if (special[k] === 'geometry') { const B = bands(seeded({ n: SHAPES.String.min })), C = bands(seeded({ n: SHAPES.String.max })), D = bands(seeded({}));
    r = { min: cmp(D, B), max: cmp(D, C) }; note = 'via mass count'; }
  else if (special[k] === 'index') { const key = k === 'hit' ? 'hitF' : 'micF', D = bands(seeded({}));
    r = { min: cmp(D, bands(seeded({ [key]: 0.02 }))), max: cmp(D, bands(seeded({ [key]: 0.5 }))) }; note = 'via node index'; }
  else r = probe(k, {});
  let vd = verdict(r);
  if (vd.v !== 'lands' && PARENT[k] && Object.keys(PARENT[k]).length) {
    const r2 = probe(k, PARENT[k]), v2 = verdict(r2);
    note = `alone ${vd.worst} dB; with ${JSON.stringify(PARENT[k]).replace(/"/g, '')}`; r = r2; vd = v2;
  }
  out.knobs.push({ k, label: KNOBS[k].label, v: vd.v, worstDb: vd.worst, note,
    minDb: r.min ? +Math.max(r.min.mean, r.min.side).toFixed(2) : null, maxDb: r.max ? +Math.max(r.max.mean, r.max.side).toFixed(2) : null });
  process.stderr.write('.');
}
// ---------- D. modulators: depth and rate on a pitch destination ----------
{ const D = bands(seeded({ mods: [{ d: 'tune', r: 5, a: 0, sh: 0 }] }));
  for (const [name, md] of [['depth 0→1 (5 Hz sine → Trim)', { d: 'tune', r: 5, a: 1, sh: 0 }],
                            ['rate slow→fast (0.05→200 Hz, depth 1)', null]]) {
    let d;
    if (md) d = cmp(D, bands(seeded({ mods: [md] })));
    else d = cmp(bands(seeded({ mods: [{ d: 'tune', r: 0.05, a: 1, sh: 0 }] })), bands(seeded({ mods: [{ d: 'tune', r: 200, a: 1, sh: 0 }] })));
    out.mods.push({ name, db: +Math.max(d.mean, d.side).toFixed(2), v: Math.max(d.mean, d.side) >= THRESH ? 'lands' : 'faint/inaudible' });
  }
}
fs.writeFileSync(new URL('./audit-results.json', import.meta.url), JSON.stringify(out, null, 1));
console.log('\n' + JSON.stringify({ determinism: out.determinism, seededAllOn: out.seededAllOn }, null, 0));
console.table(out.health);
console.table(out.knobs);
console.table(out.mods);
