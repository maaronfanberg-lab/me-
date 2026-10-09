import { lufs, truePeakDb, health } from './metrics.mjs';
const NEW = await import('./harness.mjs');
const LV = { String: 1.4928, Tine: 0.8082, Chime: 0.866, Drum: 0.9784, Hoop: 1.5171, Web: 0.7379, Tank: 8.8716, Twins: 1.8793 };
const STRESS = { drive: 4, nl: 8, fbAmt: 0.9, amp: 1, bass: 2, treb: 2, gain: 1.6, att: 1, regime: 1, infer: 1, mem: 1, voices: 8, fxDly: 1, fxFb: 0.85, fxSat: 1, coup: 1 };
const CASES = [['stress', STRESS], ['feedback max', { fbAmt: 1 }], ['gain max', { gain: 1.6 }], ['drive max', { drive: 4 }],
  ['amp+treble', { amp: 1, treb: 2, gain: 1.6 }], ['bite+nl', { bite: 2.5, nl: 8, gain: 1.6 }], ['fb+fx', { fbAmt: 1, fxDly: 1, fxFb: 0.85, fxSat: 1, att: 1 }]];
let worst = -99, bad = 0, rows = [];
for (const s in LV) for (const [tag, params] of CASES) for (const mode of [0, 1]) {
  const r = NEW.render({ secs: 4, shape: s, params, lvl: LV[s], mode });
  const tp = Math.max(truePeakDb(r.L), truePeakDb(r.R)); bad += health(r.L).nonFinite + health(r.R).nonFinite;
  if (tp > worst) worst = tp; rows.push({ s, tag, mode, tp: +tp.toFixed(2) });
}
rows.sort((a, b) => b.tp - a.tp); console.table(rows.slice(0, 6));
console.log('cases', rows.length, 'worst TP', worst.toFixed(2), 'dBTP', worst <= -1 ? 'PASS' : 'FAIL', 'nonFinite', bad);
