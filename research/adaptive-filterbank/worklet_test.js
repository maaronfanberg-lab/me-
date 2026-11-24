// Stage 7 offline check: run apps/clarity-worklet.js (with a mocked worklet scope and a worker that
// answers one hop later) on a test signal and compare with the offline engine path.
// Pass (fixed before running): streaming output vs offline output SNR >= 60 dB; bypass bit-exact (delayed by 2 hops).
const fs = require('fs'), path = require('path');
const C = require(path.join(__dirname, '../../apps/clarity-engine.js'));
globalThis.Clarity = C;
let Proc = null;
globalThis.AudioWorkletProcessor = class { constructor() { this.port = { onmessage: null, postMessage() {} }; } };
globalThis.registerProcessor = (name, cls) => { Proc = cls; };
require(path.join(__dirname, '../../apps/clarity-worklet.js'));

const FS = 48000, H = C.HOP, n = 3 * FS;
const x = new Float64Array(n); let s = 7;
for (let i = 0; i < n; i++) { s = (s * 16807) % 2147483647; x[i] = 0.1 * Math.sin(2 * Math.PI * 330 * i / FS) + 0.02 * Math.sin(2 * Math.PI * 2500 * i / FS) + 0.01 * ((s / 2147483647) - 0.5); }

function run(bypass) {
  const p = new Proc(); const eng = new C.ClarityEngine({ mode: 'cambridge' }), eq = new C.MinPhaseEQ(1);
  let pend = [];
  const wport = { postMessage(m) { const a = eng.step(m.x); eq.setGains(a.gains); pend.push({ type: 'H', hr: Float32Array.from(eq.hr), hi: Float32Array.from(eq.hi) }); }, onmessage: null };
  p.port.onmessage({ data: { type: 'port', port: wport } });
  p.port.onmessage({ data: { type: 'bypass', on: bypass } });
  const outL = new Float64Array(n), outR = new Float64Array(n);
  for (let b = 0; b < n / 128; b++) {
    const L = Float32Array.from(x.subarray(b * 128, (b + 1) * 128));
    const oL = new Float32Array(128), oR = new Float32Array(128);
    const before = pend.length;
    p.process([[L, L]], [[oL, oR]]);
    // deliver answers produced during this block at the start of the next (worker lags one hop)
    while (pend.length) wport.onmessage({ data: pend.shift() });
    outL.set(oL, b * 128); outR.set(oR, b * 128);
  }
  return outL;
}
// offline reference: same engine, frame j uses gains from hop j (Float32 spectra like the worklet)
function offline() {
  const eng = new C.ClarityEngine({ mode: 'cambridge' }), eq = new C.MinPhaseEQ(1), y = new Float64Array(n);
  const nf = Math.floor(n / H), G = [];
  for (let j = 0; j < nf; j++) G.push(eng.step(x.subarray(j * H, (j + 1) * H)).gains);
  for (let j = 0; j < nf - 1; j++) {
    eq.setGains(G[j]); eq.hr.set(Float32Array.from(eq.hr)); eq.hi.set(Float32Array.from(eq.hi));
    y.set(eq.processFrame(0, x.subarray(j * H, j * H + 2 * H)), j * H);
  }
  return y;
}
const yS = run(false), yB = run(true), yO = offline();
const lat = 2 * H;                     // streaming output is offline output delayed by 2 hops (first frames dry)
let num = 0, den = 0, bmax = 0;
for (let i = 4 * H; i < n - 4 * H; i++) { const r = yO[i - lat], d = yS[i] - r; num += r * r; den += d * d; }
for (let i = lat; i < n; i++) bmax = Math.max(bmax, Math.abs(yB[i] - Math.fround(x[i - lat])));
const rep = { snr_db: 10 * Math.log10(num / Math.max(den, 1e-300)), bypass_max_abs_err: bmax };
rep.pass = rep.snr_db >= 60 && bmax === 0;
fs.writeFileSync(path.join(__dirname, 'stage7-worklet-report.json'), JSON.stringify(rep, null, 1));
console.log(JSON.stringify(rep, null, 1));
// diagnostics
for (const lag of [0, 128, 352, 480, 608, 832, 960, 1088, 1440]) {
  let e = 0; for (let i = 2000; i < n - 2000; i++) e = Math.max(e, Math.abs(yB[i] - Math.fround(x[i - lag])));
  let e2 = 0, r2 = 0; for (let i = 6000; i < n - 6000; i++) { e2 += (yS[i] - yO[i - lag]) ** 2; r2 += yO[i - lag] ** 2; }
  console.log('lag', lag, 'bypass maxerr', e.toFixed(6), 'stream snr', (10 * Math.log10(r2 / e2)).toFixed(1));
}
