/* Clarity Feel — a vibration ("feel") channel generated from the music, for a bass shaker / tactile
   transducer. Design from the literature (Merchel & Altinsoy, in "Musical Haptics", Springer 2018;
   Siedenburg et al., Sci. Rep. 14:7764, 2024):
     - congruent with the music (incongruent vibration lowers engagement and preference)
     - low-pass 100 Hz recommended (less spurious sound from the shaker); 200 Hz pre-filter for octave work
     - substitute tones at 40-80 Hz shaped by the music's envelope rated well; 20 Hz did not
     - 2:1 compression with a threshold (5 ms attack/release) improved ratings without lifting the noise floor
     - vibration must not lag the sound by more than ~12 ms (detectable); so the path here is causal and
       sample-by-sample (no block delay), leaving the budget for the hardware
   Modes: 'natural' = 10th-order Butterworth low-pass at 100 Hz, then 2:1 compression
          'pulse'   = 50 Hz sine carrier shaped by the low band's envelope, then 2:1 compression */
(function (root) {
'use strict';
function butterLP(fs, fc, order) {          // cascade of RBJ low-pass biquads with Butterworth Qs
  var secs = [], n = order / 2;
  for (var k = 1; k <= n; k++) {
    var Q = 1 / (2 * Math.cos((2 * k - 1) * Math.PI / (2 * order)));
    var w = 2 * Math.PI * fc / fs, c = Math.cos(w), al = Math.sin(w) / (2 * Q), a0 = 1 + al;
    secs.push({ b0: (1 - c) / 2 / a0, b1: (1 - c) / a0, b2: (1 - c) / 2 / a0, a1: -2 * c / a0, a2: (1 - al) / a0, z1: 0, z2: 0 });
  }
  return secs;
}
function runBiquads(secs, x) {
  for (var i = 0; i < secs.length; i++) {
    var s = secs[i], y = s.b0 * x + s.z1;
    s.z1 = s.b1 * x - s.a1 * y + s.z2; s.z2 = s.b2 * x - s.a2 * y; x = y;
  }
  return x;
}
function Feel(fs, opts) {
  opts = opts || {};
  this.fs = fs; this.mode = opts.mode || 'natural'; this.amount = opts.amount == null ? 1 : opts.amount;
  this.lp100 = butterLP(fs, 100, 10); this.lp200 = butterLP(fs, 200, 10);
  this.env = 0; this.ea = Math.exp(-1 / (0.002 * fs)); this.er = Math.exp(-1 / (0.050 * fs));   // envelope 2 ms / 50 ms
  this.ph = 0; this.dph = 2 * Math.PI * 50 / fs;
  this.cenv = 0; this.ca = Math.exp(-1 / (0.005 * fs));                                          // compressor 5 ms / 5 ms
  this.thr = Math.pow(10, -30 / 20); this.ratio = 2; this.floor = Math.pow(10, -60 / 20);
}
Feel.prototype.sample = function (x) {
  var y;
  if (this.mode === 'pulse') {
    var b = runBiquads(this.lp200, x), a = Math.abs(b) * Math.SQRT2;        // sine peak from rectified value
    this.env = a > this.env ? this.ea * this.env + (1 - this.ea) * a : this.er * this.env + (1 - this.er) * a;
    this.ph += this.dph; if (this.ph > 2 * Math.PI) this.ph -= 2 * Math.PI;
    y = this.env * Math.sin(this.ph);
  } else {
    y = runBiquads(this.lp100, x);
  }
  // 2:1 compressor above -30 dBFS with a -60 dBFS gate (does not lift the noise floor)
  var r = Math.abs(y);
  this.cenv = this.ca * this.cenv + (1 - this.ca) * r;
  var g = 1;
  if (this.cenv > this.thr) g = Math.pow(this.cenv / this.thr, 1 / this.ratio - 1);
  if (this.cenv < this.floor) g *= this.cenv / this.floor;
  return y * g * this.amount;
};
Feel.prototype.process = function (inp, out) { for (var i = 0; i < inp.length; i++) out[i] = this.sample(inp[i]); return out; };
var api = { Feel: Feel, butterLP: butterLP };
if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ClarityFeel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
