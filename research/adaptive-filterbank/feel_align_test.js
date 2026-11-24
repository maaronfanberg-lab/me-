// Feel in the worklet (checks fixed before running):
// A1 alignment: kick onset (50% of peak) in the Feel-only output vs the audio output within +-3 ms, both modes
// A2 Feel off: output bit-identical to the plain worklet (bypass still exact)
// A3 no clipping: |out| <= 1 with Feel High on a full-scale-ish kick track
const path = require('path');
const C = require(path.join(__dirname, '../../apps/clarity-engine.js')); globalThis.Clarity = C;
globalThis.ClarityFeel = require(path.join(__dirname, '../../apps/clarity-feel.js'));
globalThis.sampleRate = 48000;
let Proc; globalThis.AudioWorkletProcessor = class { constructor() { this.port = { onmessage: null, postMessage() {} }; } };
globalThis.registerProcessor = (n, c) => { Proc = c; };
require(path.join(__dirname, '../../apps/clarity-worklet.js'));
const FS = 48000, n = 2 * FS;
const kick = new Float64Array(n); for (let i = 0; i < n; i++) { const tk = i / FS - 1.0; if (tk >= 0 && tk < 0.3) kick[i] = 0.9 * Math.exp(-tk / 0.08) * Math.sin(2 * Math.PI * (45 * tk + 15 * 0.03 * (1 - Math.exp(-tk / 0.03)))); }
function run(x, feel) {
  const p = new Proc(); p.port.onmessage({ data: { type: 'bypass', on: true } });   // audio path dry (delayed) so the only change is Feel
  if (feel) p.port.onmessage({ data: { type: 'feel', amount: feel.amount, mode: feel.mode } });
  const out = new Float64Array(n);
  for (let b = 0; b < n / 128; b++) { const L = Float32Array.from(x.subarray(b * 128, (b + 1) * 128)); const oL = new Float32Array(128), oR = new Float32Array(128); p.process([[L, L]], [[oL, oR]]); out.set(oL, b * 128); }
  return out;
}
function onset50(a) { const e = []; for (let j = 0; j < a.length / 48; j++) { let s = 0; for (let i = 0; i < 48; i++) s += a[j * 48 + i] ** 2; e.push(Math.sqrt(s / 48)); } const pk = Math.max(...e); return e.findIndex(v => v >= 0.5 * pk); }
const rep = {};
const plain = run(kick, null);
for (const mode of ['natural', 'pulse']) {
  const both = run(kick, { amount: 1, mode });
  const feelOnly = both.map((v, i) => v - plain[i]);
  rep[mode] = { audio_onset_ms: onset50(plain), feel_onset_ms: onset50(feelOnly) };
  rep[mode].offset_ms = rep[mode].feel_onset_ms - rep[mode].audio_onset_ms;
  rep[mode].A1_pass = Math.abs(rep[mode].offset_ms) <= 3;
  rep[mode].max_abs = Math.max(...both.map(Math.abs)); rep[mode].A3_pass = rep[mode].max_abs <= 1;
}
const off = run(kick, { amount: 0, mode: 'natural' }); rep.A2_pass = off.every((v, i) => v === plain[i]);
rep.PASS = rep.natural.A1_pass && rep.pulse.A1_pass && rep.natural.A3_pass && rep.pulse.A3_pass && rep.A2_pass;
require('fs').writeFileSync(path.join(__dirname, 'feel-align-report.json'), JSON.stringify(rep, null, 1));
console.log(JSON.stringify(rep, null, 1));
