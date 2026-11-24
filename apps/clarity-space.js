/* Clarity Space — headphone externalisation: "speakers in a room" instead of "music inside your head".
   Literature basis: reverberation, especially early reflections, is essential for externalisation (Li et al.,
   Appl. Sci. 9:460, 2019); HRTF-only virtualisers externalise poorly without room reverberation (Dolby
   US 12028701); gains are limited if the virtual room diverges from the real one (Amengual Gari et al.),
   so the rooms here are ordinary living-room sizes.
   Graph per channel: direct path (HRTF panner at +-30 deg, 2 m) + 6 first-order image-source reflections
   (HRTF panners at their true directions, delays and 1/r losses) + a decorrelated late tail (ConvolverNode).
   Off = the input goes straight to the output (no nodes in between). */
(function (root) {
'use strict';
var C_SOUND = 343;
var PRESETS = {
  near:  { room: [4.0, 3.5, 2.6], spk: 1.5, refl: 0.45, rt60: 0.25, tail: 0.06 },
  room:  { room: [5.5, 4.5, 2.7], spk: 2.0, refl: 0.70, rt60: 0.35, tail: 0.18 },
  large: { room: [8.0, 6.5, 3.2], spk: 2.8, refl: 0.85, rt60: 0.70, tail: 0.40 }
};
function noiseTail(ctx, rt60, seed) {           // decorrelated stereo exponential-decay noise
  var len = Math.ceil(rt60 * 1.2 * ctx.sampleRate), b = ctx.createBuffer(2, len, ctx.sampleRate), s = seed;
  for (var ch = 0; ch < 2; ch++) {
    var d = b.getChannelData(ch), e = 0;
    for (var i = 0; i < len; i++) {
      s = (s * 16807) % 2147483647; var n = (s / 2147483647) * 2 - 1;
      var t = i / ctx.sampleRate, fade = Math.min(1, t / 0.02);       // 20 ms onset so it sits behind the reflections
      d[i] = n * Math.pow(10, -3 * t / rt60) * fade; e += d[i] * d[i];
    }
    var g = 1 / Math.sqrt(e); for (var j = 0; j < len; j++) d[j] *= g;  // unit-energy tail
  }
  return b;
}
function panner(ctx, x, y, z) {
  var p = ctx.createPanner(); p.panningModel = 'HRTF'; p.distanceModel = 'inverse'; p.refDistance = 1e9; p.rolloffFactor = 0;
  if (p.positionX) { p.positionX.value = x; p.positionY.value = y; p.positionZ.value = z; } else p.setPosition(x, y, z);
  return p;
}
// Listener at the origin facing -z (Web Audio default). Speaker at azimuth az (deg, + = right), distance r.
function Space(ctx) {
  this.ctx = ctx; this.input = ctx.createGain(); this.output = ctx.createGain(); this.preset = 'off'; this.nodes = [];
  this.input.connect(this.output);
}
Space.prototype.setPreset = function (name) {
  var ctx = this.ctx, self = this;
  this.nodes.forEach(function (n) { try { n.disconnect(); } catch (e) {} });
  this.nodes = []; try { this.input.disconnect(); } catch (e) {}
  this.preset = name;
  if (name === 'off' || !PRESETS[name]) { this.input.connect(this.output); return; }
  var P = PRESETS[name], split = ctx.createChannelSplitter(2), sum = ctx.createGain();
  this.input.connect(split); this.nodes.push(split, sum);
  var W = P.room[0], D = P.room[1], H = P.room[2];
  // listener 1/3 into the room from the back wall, centred; ears at 1.2 m
  var lx = W / 2, lz = D * 2 / 3, ly = 1.2;
  [-30, 30].forEach(function (az, ch) {
    var a = az * Math.PI / 180, sx = lx + P.spk * Math.sin(a), sz = lz - P.spk * Math.cos(a), sy = 1.2;
    var srcs = [[sx, sy, sz, 1]];
    // first-order images in the 6 walls
    srcs.push([-sx, sy, sz, P.refl], [2 * W - sx, sy, sz, P.refl], [sx, -sy, sz, P.refl], [sx, 2 * H - sy, sz, P.refl], [sx, sy, -sz, P.refl], [sx, sy, 2 * D - sz, P.refl]);
    var d0 = Math.hypot(sx - lx, sy - ly, sz - lz);
    srcs.forEach(function (s) {
      var dx = s[0] - lx, dy = s[1] - ly, dz = s[2] - lz, d = Math.hypot(dx, dy, dz);
      var delay = ctx.createDelay(0.1); delay.delayTime.value = (d - d0) / C_SOUND;
      var g = ctx.createGain(); g.gain.value = s[3] * d0 / d;
      var p = panner(ctx, dx / d, dy / d, dz / d);
      split.connect(delay, ch); delay.connect(g); g.connect(p); p.connect(sum);
      self.nodes.push(delay, g, p);
    });
  });
  // late tail fed from the mono sum, decorrelated left/right
  var mono = ctx.createGain(); mono.gain.value = 0.5; split.connect(mono, 0); split.connect(mono, 1);
  var conv = ctx.createConvolver(); conv.normalize = false; conv.buffer = noiseTail(ctx, P.rt60, 12345);
  var tg = ctx.createGain(); tg.gain.value = P.tail;
  mono.connect(conv); conv.connect(tg); tg.connect(sum);
  var make = ctx.createGain(); make.gain.value = this.makeup(name);
  sum.connect(make); make.connect(this.output);
  this.nodes.push(mono, conv, tg, make);
};
// loudness make-up per preset (measured in space_test.html: matches 'off' integrated loudness on pink noise)
var MAKEUP = { near: 0.6755, room: 0.6456, large: 0.5811 };   // pink noise, K-weighted, both ears (space_test.py)
Space.prototype.makeup = function (name) { var m = root.CLARITY_SPACE_MAKEUP; return (m && m[name]) || MAKEUP[name] || 1; };
var api = { Space: Space, PRESETS: PRESETS };
if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ClaritySpace = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
