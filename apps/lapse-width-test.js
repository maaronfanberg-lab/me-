// Checks for apps/lapse-width-core.js. Run: node apps/lapse-width-test.js
const C = require("./lapse-width-core.js");
let pass = 0, fail = 0;
const check = (name, ok, d) => { ok ? pass++ : fail++; console.log((ok ? "PASS " : "FAIL ") + name + (d ? "  " + d : "")); };
function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296) * 2 - 1; }
function music(n, amp, seed) { // correlated stereo: shared part plus some side, deterministic
  const r = rng(seed), L = new Float32Array(n), R = new Float32Array(n);
  for (let i = 0; i < n; i++) { const m = 0.8 * Math.sin(i * 0.031) + 0.2 * r(), s = 0.25 * r(); L[i] = amp * (m + s); R[i] = amp * (m - s); }
  return [L, R];
}
function run(L, R, p, blocks) {
  const st = C.makeState(), B = 128, oL = new Float32Array(L.length), oR = new Float32Array(R.length);
  for (let k = 0; k + B <= L.length; k += B) C.process(L.subarray(k, k + B), R.subarray(k, k + B), oL.subarray(k, k + B), oR.subarray(k, k + B), p, st);
  return { oL, oR, st };
}
const P = { bypass: false, trim: 0.2, target: 0.5, auto: true, mu: 0.05, cap: 0.01, rear: 0.3, width: 1 };
const N = 128 * 4000;
// 1. bypass is bit-identical
{ const [L, R] = music(N, 0.5, 1), o = run(L, R, { ...P, bypass: true });
  check("bypass passes the input through bit-identically", o.oL.every((v, i) => v === L[i]) && o.oR.every((v, i) => v === R[i])); }
// 2. mono in -> mono out (no invented surround content)
{ const [L] = music(N, 0.5, 2), o = run(L, L, P);
  let maxSide = 0; for (let i = 0; i < N; i++) maxSide = Math.max(maxSide, Math.abs(o.oL[i] - o.oR[i]));
  check("pure mono input stays mono (no phantom rear signal)", maxSide === 0, "max |L-R| = " + maxSide); }
// 3. loudness invariance of the adaptation (the NLMS / energy-normalised step)
{ const [L1, R1] = music(N, 0.05, 3), [L2, R2] = music(N, 0.5, 3);
  const g1 = run(L1, R1, P).st.g, g2 = run(L2, R2, P).st.g;
  check("converged width gain is the same at -20 dB and 0 dB input, and off its limits", Math.abs(g1 - g2) < 0.02 && g1 > 0.05 && g1 < 2.95, `g = ${g1.toFixed(4)} vs ${g2.toFixed(4)}`); }
// 4. the adaptation reaches its target side/mid ratio
{ const [L, R] = music(N, 0.5, 4), o = run(L, R, { ...P, trim: 0, rear: 0 }); let em = 0, es = 0;
  for (let i = N / 2; i < N; i++) { const m = 0.5 * (o.oL[i] + o.oR[i]), s = 0.5 * (o.oL[i] - o.oR[i]); em += m * m; es += s * s; }
  const ratio = Math.sqrt(es / em); check("auto-width settles at the target side/mid ratio (0.5)", Math.abs(ratio - 0.5) < 0.03, "ratio " + ratio.toFixed(3)); }
// 5. the cap is respected: gain never moves more than cap per block
{ const [L, R] = music(N, 0.5, 5), st = C.makeState(), B = 128, o = new Float32Array(B); let worst = 0, prev = st.g;
  for (let k = 0; k + B <= N; k += B) { C.process(L.subarray(k, k + B), R.subarray(k, k + B), o, new Float32Array(B), { ...P, mu: 1 }, st); worst = Math.max(worst, Math.abs(st.g - prev)); prev = st.g; }
  check("gain change per block never exceeds the cap (0.01)", worst <= 0.01 + 1e-12, "worst " + worst); }
// 6. output never clips past full scale
{ const [L, R] = music(N, 1.2, 6), o = run(L, R, { ...P, rear: 1, target: 2 });
  check("output stays within [-1, 1]", o.oL.every(v => Math.abs(v) <= 1) && o.oR.every(v => Math.abs(v) <= 1)); }
// 7. determinism
{ const [L, R] = music(N, 0.5, 7), a = run(L, R, P), b = run(L, R, P);
  check("same input and settings give bit-identical output", a.oL.every((v, i) => v === b.oL[i])); }
console.log(`${pass}/${pass + fail} Lapse Width checks passed`); process.exit(fail ? 1 : 0);
