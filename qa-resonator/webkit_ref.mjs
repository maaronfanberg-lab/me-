// Node reference for webkit_check.py: the same messages as its in-page offline render
// (one E3 note at t = 0, 32 kHz, 2 s), so WebKit's engine output can be compared with Node's.
// Usage: RESONATOR_SRC=apps/resonator-next.html node qa-resonator/webkit_ref.mjs
import { render, SHAPES } from './harness.mjs';

function stats(L, R) {
  let pk = 0, ss = 0, bad = 0, onset = -1;
  for (let i = 0; i < L.length; i++) {
    const a = L[i], b = R[i];
    if (!Number.isFinite(a) || !Number.isFinite(b)) { bad++; continue; }
    if (onset < 0 && (Math.abs(a) > 1e-4 || Math.abs(b) > 1e-4)) onset = i;
    pk = Math.max(pk, Math.abs(a), Math.abs(b)); ss += a * a + b * b;
  }
  return { pk, rms: Math.sqrt(ss / (2 * L.length)), bad, onset, head: onset < 0 ? [] : Array.from(L.slice(onset, onset + 2048)) };
}
const out = {};
for (const shape of Object.keys(SHAPES)) {
  const r = render({ rate: 32000, secs: 2, shape, notes: [{ at: 0, semi: 0, v: 0.9 }] });
  out[shape] = stats(r.L, r.R);
}
process.stdout.write(JSON.stringify(out));
