// Measurement helpers: BS.1770-4 loudness, 4x true peak, 1/3-octave short-time bands.

function biquad(x, b0, b1, b2, a1, a2) {
  const y = new Float64Array(x.length); let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < x.length; i++) { const v = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2; x2 = x1; x1 = x[i]; y2 = y1; y1 = v; y[i] = v; }
  return y;
}
// K-weighting coefficients derived for arbitrary rate (Brecher/ITU form)
function kWeight(x, fs) {
  let f0 = 1681.974450955533, G = 3.999843853973347, Q = 0.7071752369554196;
  let K = Math.tan(Math.PI * f0 / fs), Vh = Math.pow(10, G / 20), Vb = Math.pow(Vh, 0.4996667741545416);
  let a0 = 1 + K / Q + K * K;
  const s1 = biquad(x, (Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0);
  f0 = 38.13547087602444; Q = 0.5003270373238773; K = Math.tan(Math.PI * f0 / fs);
  a0 = 1 + K / Q + K * K;
  return biquad(s1, 1, -2, 1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0);
}
export function lufs(L, R, fs) {
  const kl = kWeight(L, fs), kr = kWeight(R, fs);
  const blk = Math.round(0.4 * fs), hop = Math.round(0.1 * fs), z = [];
  for (let s = 0; s + blk <= L.length; s += hop) { let e = 0; for (let i = s; i < s + blk; i++) e += kl[i] * kl[i] + kr[i] * kr[i]; z.push(e / blk); }
  const ld = e => -0.691 + 10 * Math.log10(Math.max(1e-20, e));
  let g = z.filter(e => ld(e) > -70); if (!g.length) return -Infinity;
  const rel = ld(g.reduce((a, b) => a + b, 0) / g.length) - 10;
  g = g.filter(e => ld(e) > rel);
  return ld(g.reduce((a, b) => a + b, 0) / g.length);
}
export function truePeakDb(x) {
  // 4x oversampling with a 48-tap windowed-sinc interpolator per phase
  let pk = 0; const H = 24;
  for (let i = 0; i < x.length; i++) {
    pk = Math.max(pk, Math.abs(x[i]));
    for (let ph = 1; ph < 4; ph++) {
      const fr = ph / 4; let s = 0;
      for (let k = -H + 1; k <= H; k++) { const j = i + k; if (j < 0 || j >= x.length) continue; const t = k - fr;
        const w = 0.5 + 0.5 * Math.cos(Math.PI * t / H); s += x[j] * (Math.sin(Math.PI * t) / (Math.PI * t)) * w; }
      pk = Math.max(pk, Math.abs(s));
    }
  }
  return 20 * Math.log10(Math.max(1e-12, pk));
}
export function health(x) {
  let bad = 0, pk = 0; for (const v of x) { if (!Number.isFinite(v)) bad++; else pk = Math.max(pk, Math.abs(v)); }
  return { nonFinite: bad, peakDb: 20 * Math.log10(Math.max(1e-12, pk)) };
}
// short-time third-octave band energies (dB), 40 ms frames, via direct DFT on a decimated grid
const BANDS = []; for (let n = -16; n <= 13; n++) BANDS.push(1000 * Math.pow(2, n / 3)); // 25 Hz .. 20 kHz
export function bandFrames(x, fs) {
  const N = 2048, hop = Math.round(0.04 * fs), out = [];
  const win = new Float64Array(N).map((_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N));
  const re = new Float64Array(N), im = new Float64Array(N);
  for (let s = 0; s + N <= x.length; s += hop) {
    for (let i = 0; i < N; i++) { re[i] = x[s + i] * win[i]; im[i] = 0; }
    fft(re, im);
    const bands = BANDS.map(fc => { const lo = fc / Math.pow(2, 1 / 6), hi = fc * Math.pow(2, 1 / 6); let e = 1e-14;
      for (let k = Math.max(1, Math.floor(lo * N / fs)); k <= Math.min(N / 2, Math.ceil(hi * N / fs)); k++) e += re[k] * re[k] + im[k] * im[k];
      return 10 * Math.log10(e); });
    out.push(bands);
  }
  return out;
}
function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) { let bit = n >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let len = 2; len <= n; len <<= 1) { const a = -2 * Math.PI / len, wr = Math.cos(a), wi = Math.sin(a);
    for (let i = 0; i < n; i += len) { let cr = 1, ci = 0;
      for (let j = 0; j < len / 2; j++) { const ur = re[i + j], ui = im[i + j], k = i + j + len / 2;
        const vr = re[k] * cr - im[k] * ci, vi = re[k] * ci + im[k] * cr;
        re[i + j] = ur + vr; im[i + j] = ui + vi; re[k] = ur - vr; im[k] = ui - vi;
        const t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t; } } }
}
// Perceptual difference: mean |ΔdB| over frames & audible bands, only where either signal is
// within 60 dB of its own loudest band (ignores differences in silence).
export function diffDb(A, B) {
  let top = -Infinity; for (const f of A) for (const v of f) top = Math.max(top, v);
  for (const f of B) for (const v of f) top = Math.max(top, v);
  let s = 0, n = 0, mx = 0; const F = Math.min(A.length, B.length);
  for (let i = 0; i < F; i++) for (let b = 0; b < A[i].length; b++) {
    if (Math.max(A[i][b], B[i][b]) < top - 60) continue;
    const d = Math.abs(A[i][b] - B[i][b]); s += d; n++; if (d > mx) mx = d; }
  return { mean: n ? s / n : 0, max: mx };
}
export function sameBits(a, b) { if (a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (Object.is(a[i], b[i]) === false) return false; return true; }
