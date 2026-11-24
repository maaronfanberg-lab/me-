/* Clarity engine — JS port of research/adaptive-filterbank (fast.py + stage3 masking + stage4 gains/filter).
   Runs in Node (parity tests) and inside an AudioWorkletProcessor (no DOM, no imports).
   Model: adaptive Fourier/wavelet analysis -> ear masking (cambridge | munich) -> Recover/Tame/Bias
   -> loudness-held, minimum-phase EQ every 10 ms, 20 ms Hann OLA crossfade. Causal. */
(function (root) {
'use strict';
var FS = 48000, HOP = 480, NN = 4096, NW = 1024, NFFT = 4096;
var LN10 = Math.log(10);
function erb(f) { return 24.7 * (4.37 * f / 1000 + 1); }
function erbN(f) { return 21.4 * Math.log10(4.37 * f / 1000 + 1); }
function erbNinv(e) { return (Math.pow(10, e / 21.4) - 1) * 1000 / 4.37; }
function bark(f) { return 13 * Math.atan(0.76 * f / 1000) + 3.5 * Math.atan(Math.pow(f / 7500, 2)); }
function quiet(f) { var k = f / 1000; return 3.64 * Math.pow(k, -0.8) - 6.5 * Math.exp(-0.6 * (k - 3.3) * (k - 3.3)) + 1e-3 * Math.pow(k, 4); }
function hann(n) { var w = new Float64Array(n); for (var i = 0; i < n; i++) w[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1)); return w; }

/* ---------- FFT (radix-2, in place) ---------- */
var fftCache = {};
function fftPlan(n) {
  if (fftCache[n]) return fftCache[n];
  var lev = Math.round(Math.log2(n)), rev = new Uint32Array(n), cs = new Float64Array(n / 2), sn = new Float64Array(n / 2);
  for (var i = 0; i < n; i++) { var r = 0, x = i; for (var b = 0; b < lev; b++) { r = (r << 1) | (x & 1); x >>= 1; } rev[i] = r; }
  for (var k = 0; k < n / 2; k++) { cs[k] = Math.cos(2 * Math.PI * k / n); sn[k] = Math.sin(2 * Math.PI * k / n); }
  return (fftCache[n] = { n: n, rev: rev, cs: cs, sn: sn });
}
function fft(re, im, inverse) {
  var p = fftPlan(re.length), n = p.n, i, j, t;
  for (i = 0; i < n; i++) { j = p.rev[i]; if (j > i) { t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
  var sgn = inverse ? 1 : -1;
  for (var size = 2; size <= n; size <<= 1) {
    var half = size >> 1, step = n / size;
    for (i = 0; i < n; i += size) {
      for (j = 0; j < half; j++) {
        var k = j * step, wr = p.cs[k], wi = sgn * p.sn[k];
        var a = i + j, b = a + half;
        var xr = re[b] * wr - im[b] * wi, xi = re[b] * wi + im[b] * wr;
        re[b] = re[a] - xr; im[b] = im[a] - xi; re[a] += xr; im[a] += xi;
      }
    }
  }
  if (inverse) for (i = 0; i < n; i++) { re[i] /= n; im[i] /= n; }
}

/* ---------- static tables ---------- */
var K = 0, FC = [];
for (var f0 = 50; f0 < 16000; f0 += 25) FC.push(f0);
K = FC.length; FC = Float64Array.from(FC);
var BWN = new Float64Array(K), BWW = new Float64Array(K), EN = new Float64Array(K), ZC = new Float64Array(K), QT = new Float64Array(K), OCTW = new Float64Array(K);
for (var q = 0; q < K; q++) {
  BWN[q] = Math.min(erb(FC[q]), 25); BWW[q] = Math.max(erb(FC[q]), FC[q] / 4);
  EN[q] = erbN(FC[q]); ZC[q] = bark(FC[q]); QT[q] = quiet(FC[q]);
  OCTW[q] = Math.log2((FC[q] + 12.5) / Math.max(FC[q] - 12.5, 1));
}
function bandWeights(n, bws) {          // per band: start bin + weights where >= 1e-9
  var out = [];
  for (var b = 0; b < K; b++) {
    var bb = 1.019 * bws[b], lo = -1, ws = [];
    for (var i = 0; i <= n / 2; i++) {
      var fr = i * FS / n, w = Math.pow(1 + Math.pow((fr - FC[b]) / bb, 2), -4);
      if (w >= 1e-9) { if (lo < 0) lo = i; ws.push(w); } else if (lo >= 0 && fr > FC[b]) break;
      else if (lo >= 0) ws.push(0);
    }
    out.push({ lo: lo, w: Float64Array.from(ws) });
  }
  return out;
}
var WNb = bandWeights(NN, BWN), WWb = bandWeights(NW, BWW);
var HN = hann(NN), HW = hann(NW), CN = 0, CW = 0;
for (var a1 = 0; a1 < NN; a1++) CN += HN[a1] * HN[a1]; CN *= NN;
for (var a2 = 0; a2 < NW; a2++) CW += HW[a2] * HW[a2]; CW *= NW;
var GPPF = 27.31765276498299;           // gamma.ppf(1 - 1e-6, 7)
var HOLD = new Int32Array(K); for (var h = 0; h < K; h++) HOLD[h] = Math.ceil(GPPF / (4 * Math.PI * 1.019 * BWN[h]) * 100 - 1e-9);
var REL = Math.exp(-10 / 20), AA = 1 - Math.pow(1 - 0.045, 10), AR = 1 - Math.pow(1 - 0.02, 10);

// detectors (0.1 ERB grid, as fast.py)
var DET = [], e0 = erbN(50), e1 = erbN(15000);
for (var ee = 0, nE = Math.ceil((e1 - e0) / 0.1); ee < nE; ee++) DET.push(erbNinv(e0 + ee * 0.1));
DET = Float64Array.from(DET); var D = DET.length;
var DETZ = new Float64Array(D), NOISE = new Float64Array(D), P51 = new Float64Array(D);
for (var d0 = 0; d0 < D; d0++) { DETZ[d0] = bark(DET[d0]); NOISE[d0] = Math.pow(10, quiet(DET[d0]) / 10); P51[d0] = 4 * DET[d0] / erb(DET[d0]); }
var P511 = 4 * 1000 / erb(1000);
var OFF = 10 * Math.log10(Math.pow(10, 0.1) - 1);
var nearest = new Int32Array(K);       // detector index nearest each band
for (var nb = 0, dj = 0; nb < K; nb++) { while (dj + 1 < D && Math.abs(DET[dj + 1] - FC[nb]) <= Math.abs(DET[dj] - FC[nb])) dj++; nearest[nb] = dj; }

// K-weighting power at FC (BS.1770 biquads at 48 kHz)
function biq(b, a, f) {
  var w = 2 * Math.PI * f / FS, cr = Math.cos(w), ci = -Math.sin(w), c2r = Math.cos(2 * w), c2i = -Math.sin(2 * w);
  var nr = b[0] + b[1] * cr + b[2] * c2r, ni = b[1] * ci + b[2] * c2i, dr = a[0] + a[1] * cr + a[2] * c2r, di = a[1] * ci + a[2] * c2i;
  return (nr * nr + ni * ni) / (dr * dr + di * di);
}
var KW = new Float64Array(K);
for (var kk = 0; kk < K; kk++) KW[kk] = biq([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585], FC[kk])
  * biq([1, -2, 1], [1, -1.99004745483398, 0.99007225036621], FC[kk]);

/* ---------- masking for one frame ---------- */
// Returns {margin, thr, dstar} and fills C (D x K, column-major by component) for attribution.
function Masker(mode) { this.mode = mode; this.C = new Float64Array(D * K); this.lo = new Int32Array(K); this.hi = new Int32Array(K);
  this.Wcol = new Float64Array(D * K); this.Etot = new Float64Array(D); this.pref = new Float64Array(D * (K + 1)); }
Masker.prototype.weightsAt = function (k, L, X, d) {     // weight of component k at detector d
  if (this.mode === 'cambridge') {
    var g = (FC[k] - DET[d]) / DET[d], p = P51[d];
    if (g < 0) p = Math.max(P51[d] - 0.38 * (P51[d] / P511) * (X - 51), 0.1);
    var ga = Math.abs(g); return (1 + p * ga) * Math.exp(-p * ga);
  }
  var dz = DETZ[d] - ZC[k], s2 = 24 + 230 / FC[k] - 0.2 * L;
  return Math.pow(10, -(dz < 0 ? 27 * (-dz) : s2 * dz) / 10);
};
Masker.prototype.frame = function (lev, bw) {
  var mode = this.mode, I = new Float64Array(K), X = new Float64Array(K), k, d, b;
  for (k = 0; k < K; k++) I[k] = Math.pow(10, lev[k] / 10);
  if (mode === 'cambridge') {             // level per ERB around each component (+-0.5 ERB)
    var a = 0, z = 0, s = 0;
    for (k = 0; k < K; k++) {
      while (z < K && EN[z] - EN[k] <= 0.5) { s += I[z]; z++; }
      while (EN[k] - EN[a] > 0.5) { s -= I[a]; a++; }
      X[k] = 10 * Math.log10(s);
    }
  }
  var C = this.C, W = this.Wcol, Etot = this.Etot, lo = this.lo, hi = this.hi;
  C.fill(0); W.fill(0); Etot.fill(0);
  for (k = 0; k < K; k++) {               // support of each component: weight >= 1e-15
    var c = nearest[k], base = k * D;
    for (d = c; d >= 0; d--) { var w = this.weightsAt(k, lev[k], X[k], d); if (w < 1e-15 || (w < 1e-7 && w * I[k] < 1e-7)) break; W[base + d] = w; C[d * K + k] = w * I[k]; Etot[d] += w * I[k]; }
    lo[k] = d + 1;
    for (d = c + 1; d < D; d++) { var w2 = this.weightsAt(k, lev[k], X[k], d); if (w2 < 1e-15 || (w2 < 1e-7 && w2 * I[k] < 1e-7)) break; W[base + d] = w2; C[d * K + k] = w2 * I[k]; Etot[d] += w2 * I[k]; }
    hi[k] = d;
  }
  // prefix sums of contributions along k at every detector (own-sound subtraction by runs)
  var pref = this.pref, K1 = K + 1;
  for (d = 0; d < D; d++) { var acc = 0, pb = d * K1, cb = d * K; pref[pb] = 0; for (k = 0; k < K; k++) { acc += C[cb + k]; pref[pb + k + 1] = acc; } }
  var margin = new Float64Array(K), thr = new Float64Array(K), dstar = new Int32Array(K), own = new Uint8Array(K);
  this.own = [];
  for (b = 0; b < K; b++) {
    var bp = 1.019 * bw[b], reach = 5.5277 * bp;         // resp > -60 dB <=> |df| < bp*sqrt(10^1.5 - 1)
    var kl = b, kh = b;
    while (kl > 0 && FC[b] - FC[kl - 1] < reach) kl--;
    while (kh < K - 1 && FC[kh + 1] - FC[b] < reach) kh++;
    var list = [], runs = [], rs = -1;
    for (k = kl; k <= kh; k++) {
      var df = (FC[k] - FC[b]) / bp, resp = -40 * Math.log10(1 + df * df);
      if (resp > -60 && lev[k] <= lev[b] + resp + 3) { list.push(k); if (rs < 0) rs = k; }
      else if (rs >= 0) { runs.push(rs, k); rs = -1; }
    }
    if (rs >= 0) runs.push(rs, kh + 1);
    this.own.push(list);
    var best = Infinity, bd = -1;
    for (d = lo[b]; d < hi[b]; d++) {
      var wt = W[b * D + d]; if (wt < 1e-12) continue;
      var em = Etot[d] + NOISE[d], pb2 = d * K1;
      for (var ri = 0; ri < runs.length; ri += 2) em -= pref[pb2 + runs[ri + 1]] - pref[pb2 + runs[ri]];
      var r = em / wt;                                    // min over places of em/W  (one log at the end)
      if (r < best) { best = r; bd = d; }
    }
    best = 10 * Math.log10(best) + OFF;
    thr[b] = best; margin[b] = lev[b] - best; dstar[b] = bd;
  }
  return { margin: margin, thr: thr, dstar: dstar };
};
Masker.prototype.mainMasker = function (b, d) {         // largest contributor at d outside b's own sound
  var C = this.C, ownL = this.own[b], bestK = 0, bestV = -1, j = 0, base = d * K;
  for (var k = 0; k < K; k++) {
    while (j < ownL.length && ownL[j] < k) j++;
    if (j < ownL.length && ownL[j] === k) continue;
    var v = C[base + k]; if (v > bestV) { bestV = v; bestK = k; }
  }
  return bestK;
};

/* ---------- analysis + gains ---------- */
function ClarityEngine(opts) {
  opts = opts || {};
  this.mode = opts.mode || 'cambridge';
  this.recover = opts.recover == null ? 1 : opts.recover;
  this.tame = opts.tame == null ? 1 : opts.tame;
  this.bias = opts.bias || 0;
  this.masker = new Masker(this.mode);
  this.buf = new Float64Array(NN);
  this.Lhist = []; for (var i = 0; i < 7; i++) { var r = new Float64Array(K); r.fill(-1e9); this.Lhist.push(r); }
  this.w = new Float64Array(K); this.cnt = new Int32Array(K); this.s = null;
  this.prevG = new Float64Array(K);
  this.re = new Float64Array(NN); this.im = new Float64Array(NN);
  this.re2 = new Float64Array(NW); this.im2 = new Float64Array(NW);
}
ClarityEngine.prototype.setMode = function (m) { this.mode = m; this.masker = new Masker(m); };
ClarityEngine.prototype.analyse = function (hop) {
  var buf = this.buf, i, b, k;
  buf.copyWithin(0, HOP); for (i = 0; i < HOP; i++) buf[NN - HOP + i] = hop[i];
  var re = this.re, im = this.im;
  for (i = 0; i < NN; i++) { re[i] = buf[i] * HN[i]; im[i] = 0; }
  fft(re, im, false);
  var Xn = new Float64Array(NN / 2 + 1); for (i = 0; i <= NN / 2; i++) Xn[i] = re[i] * re[i] + im[i] * im[i];
  var re2 = this.re2, im2 = this.im2;
  for (i = 0; i < NW; i++) { re2[i] = buf[NN - NW + i] * HW[i]; im2[i] = 0; }
  fft(re2, im2, false);
  var Xw = new Float64Array(NW / 2 + 1); for (i = 0; i <= NW / 2; i++) Xw[i] = re2[i] * re2[i] + im2[i] * im2[i];
  var Pn = new Float64Array(K), Pw = new Float64Array(K);
  for (b = 0; b < K; b++) {
    var s1 = 0, wb = WNb[b]; for (i = 0; i < wb.w.length; i++) s1 += wb.w[i] * Xn[wb.lo + i]; Pn[b] = s1 / CN;
    var s2 = 0, wv = WWb[b]; for (i = 0; i < wv.w.length; i++) s2 += wv.w[i] * Xw[wv.lo + i]; Pw[b] = s2 / CW;
  }
  // onset weight
  var L = new Float64Array(K), rise = new Float64Array(K), oct = 0;
  for (b = 0; b < K; b++) {
    L[b] = 10 * Math.log10(Pw[b] + 1e-7);
    var mx = -Infinity; for (k = 1; k < 7; k++) if (this.Lhist[k][b] > mx) mx = this.Lhist[k][b];
    rise[b] = L[b] - mx; if (rise[b] > 6) oct += OCTW[b];
  }
  var last = this.Lhist.pop(); last.set(L); this.Lhist.unshift(last);
  var gate = Math.min(Math.max(oct - 1, 0), 1);
  var w = this.w, cnt = this.cnt, P = new Float64Array(K);
  for (b = 0; b < K; b++) {
    var loc = Math.min(Math.max((rise[b] - 6) / 6, 0), 1), tg = Math.max(loc, gate);
    var trig = tg >= w[b] && tg > 0;
    w[b] = trig ? tg : (cnt[b] > 0 ? w[b] : w[b] * REL);
    cnt[b] = trig ? HOLD[b] : Math.max(cnt[b] - 1, 0);
    var amp = (1 - w[b]) * Math.sqrt(Pn[b]) + w[b] * Math.sqrt(Pw[b]); P[b] = amp * amp;
  }
  if (!this.s) this.s = Float64Array.from(P);
  var lev = new Float64Array(K), bw = new Float64Array(K);
  for (b = 0; b < K; b++) {
    var s = this.s[b]; s = P[b] > s ? s + AA * (P[b] - s) : s + AR * (P[b] - s); this.s[b] = s;
    lev[b] = 10 * Math.log10(2 * s / 0.5 + 1e-20) + 100;
    bw[b] = (1 - w[b]) * BWN[b] + w[b] * BWW[b];
  }
  var m = this.masker.frame(lev, bw);
  return { lev: lev, thr: m.thr, margin: m.margin, dstar: m.dstar, w: Float64Array.from(w) };
};
var GA = Math.exp(-10 / 30);
ClarityEngine.prototype.step = function (hop) {          // one 480-sample hop -> gains (dB) for this frame
  var a = this.analyse(hop), lev = a.lev, mg = a.margin, b, k;
  var up = new Float64Array(K), down = new Float64Array(K), touched = [];
  for (b = 0; b < K; b++) {
    var left = b > 0 ? lev[b - 1] : -Infinity, right = b < K - 1 ? lev[b + 1] : -Infinity;
    var peak = lev[b] >= left && lev[b] >= right;
    if (!(peak && mg[b] > -12 && mg[b] < 0 && lev[b] > QT[b] + 10)) continue;
    var Dd = 1 - mg[b];
    var u = Math.min((1 + this.bias) / 2 * Dd, 6) * this.recover; if (u > up[b]) up[b] = u;
    var km = this.masker.mainMasker(b, a.dstar[b]);
    var dn = Math.min((1 - this.bias) / 2 * Dd, 6) * this.tame; if (dn > down[km]) down[km] = dn;
    touched.push(b, km);
  }
  var g = new Float64Array(K);
  // full-depth 0.25-ERB bumps (max over sources), lifts minus cuts
  var gu = new Float64Array(K), gd = new Float64Array(K);
  for (var t = 0; t < touched.length; t++) {
    var src = touched[t]; if (up[src] === 0 && down[src] === 0) continue;
    var k0 = src; while (k0 > 0 && EN[src] - EN[k0 - 1] <= 1.5) k0--;
    for (k = k0; k < K; k++) {
      var de = (EN[k] - EN[src]) / 0.25; if (de > 6) break;
      var ker = Math.exp(-0.5 * de * de);
      if (up[src] * ker > gu[k]) gu[k] = up[src] * ker;
      if (down[src] * ker > gd[k]) gd[k] = down[src] * ker;
    }
  }
  var num = 0, den = 0;
  for (k = 0; k < K; k++) { g[k] = gu[k] - gd[k]; var Pk = Math.pow(10, lev[k] / 10) * KW[k]; num += Pk * Math.pow(10, g[k] / 10); den += Pk; }
  var off = 10 * Math.log10(num / den);
  for (k = 0; k < K; k++) { this.prevG[k] = GA * this.prevG[k] + (1 - GA) * (g[k] - off); }
  a.gains = Float64Array.from(this.prevG);
  return a;
};

/* ---------- minimum-phase EQ filter with OLA ---------- */
var FG = new Float64Array(NFFT / 2 + 1); for (var fg = 0; fg <= NFFT / 2; fg++) FG[fg] = fg * FS / NFFT;
var WIN = new Float64Array(2 * HOP); (function () { var hw = hann(2 * HOP + 1); for (var i = 0; i < 2 * HOP; i++) WIN[i] = hw[i]; })();
function interpDb(gdb, out) {            // np.interp(FG, FC, g, left=g0, right=gK-1)
  var j = 0;
  for (var i = 0; i < FG.length; i++) {
    var f = FG[i];
    if (f <= FC[0]) { out[i] = gdb[0]; continue; }
    if (f >= FC[K - 1]) { out[i] = gdb[K - 1]; continue; }
    while (FC[j + 1] < f) j++;
    var t = (f - FC[j]) / (FC[j + 1] - FC[j]); out[i] = gdb[j] + t * (gdb[j + 1] - gdb[j]);
  }
}
function MinPhaseEQ(channels) {
  this.ch = channels; this.tails = []; for (var c = 0; c < channels; c++) this.tails.push(new Float64Array(NFFT));
  this.hr = new Float64Array(NFFT / 2 + 1); this.hi = new Float64Array(NFFT / 2 + 1);
  this.re = new Float64Array(NFFT); this.im = new Float64Array(NFFT); this.gd = new Float64Array(NFFT / 2 + 1);
}
MinPhaseEQ.prototype.setGains = function (gdb) {
  var re = this.re, im = this.im, n = NFFT, i, gd = this.gd;
  interpDb(gdb, gd);
  for (i = 0; i <= n / 2; i++) { re[i] = gd[i] * LN10 / 20; im[i] = 0; }
  for (i = 1; i < n / 2; i++) { re[n - i] = re[i]; im[n - i] = 0; }
  fft(re, im, true);                                      // real cepstrum
  for (i = 0; i < n; i++) im[i] = 0;
  for (i = 1; i < n / 2; i++) re[i] *= 2;
  for (i = n / 2 + 1; i < n; i++) re[i] = 0;
  fft(re, im, false);
  for (i = 0; i <= n / 2; i++) { var mag = Math.exp(re[i]); this.hr[i] = mag * Math.cos(im[i]); this.hi[i] = mag * Math.sin(im[i]); }
};
// seg: 2*HOP samples of one channel (frame j covers samples j*HOP .. j*HOP+2*HOP). Returns HOP finished samples.
MinPhaseEQ.prototype.processFrame = function (c, seg) {
  var re = this.re, im = this.im, n = NFFT, i;
  for (i = 0; i < n; i++) { re[i] = i < 2 * HOP ? seg[i] * WIN[i] : 0; im[i] = 0; }
  fft(re, im, false);
  for (i = 0; i <= n / 2; i++) {
    var xr = re[i], xi = im[i], hr = this.hr[i], hi = this.hi[i];
    re[i] = xr * hr - xi * hi; im[i] = xr * hi + xi * hr;
    if (i > 0 && i < n / 2) { re[n - i] = re[i]; im[n - i] = -im[i]; }
  }
  fft(re, im, true);
  var tail = this.tails[c];
  for (i = 0; i < n; i++) tail[i] += re[i];
  var out = tail.slice(0, HOP);
  tail.copyWithin(0, HOP); tail.fill(0, n - HOP);
  return out;
};

var api = { ClarityEngine: ClarityEngine, MinPhaseEQ: MinPhaseEQ, FS: FS, HOP: HOP, K: K, FC: FC, D: D, fft: fft };
if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.Clarity = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
