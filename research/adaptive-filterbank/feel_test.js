// Feel stage 1 checks (fixed before the first run). Both modes unless noted.
// F1 lag: onset of the vibration envelope vs the kick's onset (10% of peak) <= 5 ms (detectable at ~12 ms; rest is hardware budget)
//     -- 'natural' is a minimum-phase low-pass, so its group delay at 50 Hz is reported separately (must also be <= 12 ms)
// F2 band: >= 90% of vibration energy below 120 Hz (keeps the shaker from radiating audible sound)
// F3 congruence: correlation of 20 ms vibration envelope with the music's 20 ms low-band (<200 Hz) envelope >= 0.8
// F4 no noise lift: a -70 dBFS input gives output <= -80 dBFS
// F5 off: amount 0 -> exact zeros
// F6 filter shape (two ways): Butterworth |H| at 100 Hz = -3.01 dB +-0.1 by measurement; analytic -3.0103 dB
const path = require('path'); const { Feel } = require(path.join(__dirname, '../../apps/clarity-feel.js'));
const FS = 48000, N = 4 * FS;
function music() {   // kick every 0.5 s (60->45 Hz sweep), bass line, hi-hat noise, chord
  const x = new Float64Array(N); let s = 3;
  for (let i = 0; i < N; i++) {
    const t = i / FS, tk = t % 0.5;
    const kick = tk < 0.3 ? 0.5 * Math.exp(-tk / 0.08) * Math.sin(2 * Math.PI * (45 * tk + 15 * 0.03 * (1 - Math.exp(-tk / 0.03)))) : 0;
    s = (s * 16807) % 2147483647; const nz = (s / 2147483647) - 0.5;
    const hat = (t % 0.25) < 0.05 ? 0.05 * nz * Math.exp(-(t % 0.25) / 0.01) : 0;
    x[i] = kick + 0.15 * Math.sin(2 * Math.PI * 82.4 * t) + 0.05 * Math.sin(2 * Math.PI * 440 * t) + hat;
  }
  return x;
}
function run(mode, x, amount) { const f = new Feel(FS, { mode, amount: amount == null ? 1 : amount }); const y = new Float64Array(x.length); for (let i = 0; i < x.length; i++) y[i] = f.sample(x[i]); return y; }
function env(x, w) { const n = Math.floor(x.length / w), e = new Float64Array(n); for (let j = 0; j < n; j++) { let a = 0; for (let i = 0; i < w; i++) a += x[j * w + i] ** 2; e[j] = Math.sqrt(a / w); } return e; }
function corr(a, b) { const n = Math.min(a.length, b.length); let ma = 0, mb = 0; for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; } ma /= n; mb /= n; let s = 0, sa = 0, sb = 0; for (let i = 0; i < n; i++) { s += (a[i] - ma) * (b[i] - mb); sa += (a[i] - ma) ** 2; sb += (b[i] - mb) ** 2; } return s / Math.sqrt(sa * sb); }
function bandShare(y, fc) {     // energy share below fc via DFT on 1 s segments
  let lo = 0, all = 0; const L = 8192;
  for (let st = 0; st + L <= y.length; st += L) {
    for (let k = 1; k < L / 2; k++) { const f = k * FS / L; if (f > 2000) break; let re = 0, im = 0; for (let n = 0; n < L; n += 1) { const a = 2 * Math.PI * k * n / L; re += y[st + n] * Math.cos(a); im -= y[st + n] * Math.sin(a); } const p = re * re + im * im; all += p; if (f < fc) lo += p; }
    break;   // one segment is enough (stationary loop)
  }
  return lo / all;
}
const x = music(), rep = {};
// reference low band envelope (<200 Hz), zero-phase-ish by FFT mask would be ideal; use the same causal filter for fairness
const lpRef = new Feel(FS, { mode: 'natural' }).lp200; const xl = new Float64Array(N); for (let i = 0; i < N; i++) { let v = x[i]; for (const s of lpRef) { const y = s.b0 * v + s.z1; s.z1 = s.b1 * v - s.a1 * y + s.z2; s.z2 = s.b2 * v - s.a2 * y; v = y; } xl[i] = v; }
for (const mode of ['natural', 'pulse']) {
  const y = run(mode, x), r = {};
  // F1: kick at 1.0 s; 10% of local peak crossing, input vs output (1 ms envelope)
  // (test fix) kick ALONE: with the bass line under it, 10% of peak sat below the steady floor and both
  // onsets read as index 0 (a false 0 ms)
  const k = new Float64Array(FS * 2); for (let i = 0; i < k.length; i++) { const tk = i / FS - 1.0; if (tk >= 0 && tk < 0.3) k[i] = 0.5 * Math.exp(-tk / 0.08) * Math.sin(2 * Math.PI * (45 * tk + 15 * 0.03 * (1 - Math.exp(-tk / 0.03)))); }
  const yk = run(mode, k);
  const on = (a) => { const e = env(a.subarray(FS - 480, FS + 14400), 48); const pk = Math.max(...e); return { i10: e.findIndex(v => v >= 0.1 * pk), i50: e.findIndex(v => v >= 0.5 * pk) }; };
  const oi = on(k), oo = on(yk);
  r.F1_lag_ms = oo.i10 - oi.i10; r.F1_lag50_ms = oo.i50 - oi.i50;
  // group delay of natural at 50 Hz: measure with a 50 Hz tone burst envelope (50% crossings)
  if (mode === 'natural') {
    const tb = new Float64Array(FS); for (let i = 9600; i < FS; i++) tb[i] = 0.3 * Math.sin(2 * Math.PI * 50 * i / FS);
    const yt = run('natural', tb); const e1 = env(tb, 48), e2 = env(yt, 48);
    r.natural_tone_lag_ms = e2.findIndex(v => v >= 0.5 * 0.3 / Math.SQRT2 * 0.5) - e1.findIndex(v => v >= 0.5 * 0.3 / Math.SQRT2 * 0.5);
  }
  r.F1_pass = r.F1_lag_ms <= 5 && (r.natural_tone_lag_ms == null || r.natural_tone_lag_ms <= 12);
  r.F2_share_below_120 = bandShare(y.subarray(FS), 120); r.F2_pass = r.F2_share_below_120 >= 0.9;
  r.F3_corr = corr(env(y, 960), env(xl, 960)); r.F3_pass = r.F3_corr >= 0.8;
  const q = new Float64Array(FS); let s = 9; for (let i = 0; i < FS; i++) { s = (s * 16807) % 2147483647; q[i] = Math.pow(10, -70 / 20) * Math.sqrt(3) * 2 * ((s / 2147483647) - 0.5); }
  const yq = run(mode, q); let rq = 0; for (let i = FS / 2; i < FS; i++) rq += yq[i] ** 2; r.F4_out_dbfs = 10 * Math.log10(rq / (FS / 2) + 1e-30); r.F4_pass = r.F4_out_dbfs <= -80;
  const y0 = run(mode, x, 0); r.F5_pass = y0.every(v => v === 0);
  rep[mode] = r;
}
// F6: measured |H(100 Hz)| of the 10th-order low-pass vs analytic -3.0103 dB
{ const tone = new Float64Array(FS); for (let i = 0; i < FS; i++) tone[i] = Math.sin(2 * Math.PI * 100 * i / FS);
  const f = new Feel(FS, {}); let a = 0, b = 0; for (let i = 0; i < FS; i++) { let v = tone[i]; for (const s of f.lp100) { const y = s.b0 * v + s.z1; s.z1 = s.b1 * v - s.a1 * y + s.z2; s.z2 = s.b2 * v - s.a2 * y; v = y; } if (i > FS / 2) { a += tone[i] ** 2; b += v * v; } }
  rep.F6_measured_db = 10 * Math.log10(b / a); rep.F6_analytic_db = -10 * Math.log10(2); rep.F6_pass = Math.abs(rep.F6_measured_db - rep.F6_analytic_db) <= 0.1; }
rep.PASS = ['natural', 'pulse'].every(m => ['F1_pass', 'F2_pass', 'F3_pass', 'F4_pass', 'F5_pass'].every(k => rep[m][k])) && rep.F6_pass;
require('fs').writeFileSync(path.join(__dirname, 'feel-report.json'), JSON.stringify(rep, null, 1));
console.log(JSON.stringify(rep, null, 1));
