// User EQ check (fixed before running): with Clarity off and EQ +6 dB at 1 kHz only, a 1 kHz tone gains
// 6.0 +-0.2 dB, a 100 Hz and a 10 kHz tone change by <= 0.2 dB; flat EQ is bit-exact bypass (worklet).
const path = require('path'); const C = require(path.join(__dirname, '../../apps/clarity-engine.js'));
const eq = new C.MinPhaseEQ(1), H = C.HOP;
const curve = C.userCurve([0, 0, 0, 6, 0, 0, 0, 0]); eq.setGains(curve);
function gainAt(f) {
  const n = 48000, x = new Float64Array(n); for (let i = 0; i < n; i++) x[i] = 0.1 * Math.sin(2 * Math.PI * f * i / 48000);
  const y = new Float64Array(n); const e2 = new C.MinPhaseEQ(1); e2.setGains(curve);
  for (let j = 0; j < n / H - 1; j++) y.set(e2.processFrame(0, x.subarray(j * H, j * H + 2 * H)), j * H);
  let a = 0, b = 0; for (let i = 12000; i < 36000; i++) { a += x[i] * x[i]; b += y[i] * y[i]; }
  return 10 * Math.log10(b / a);
}
const r = { g1k: gainAt(1000), g100: gainAt(100), g10k: gainAt(10000) };
r.pass = Math.abs(r.g1k - 6) <= 0.2 && Math.abs(r.g100) <= 0.2 && Math.abs(r.g10k) <= 0.2;
console.log(JSON.stringify(r));
