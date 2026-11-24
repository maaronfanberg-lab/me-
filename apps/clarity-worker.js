/* Clarity analysis worker: receives 480-sample mono hops from the worklet, runs the engine
   (analysis + masking + Recover/Tame/Bias), sends the minimum-phase EQ spectrum back.
   Heavy work lives here so the audio thread never blocks. */
importScripts('clarity-engine.js?v=1');
var C = self.Clarity, eng = new C.ClarityEngine({ mode: 'cambridge' }), eq = new C.MinPhaseEQ(1);
var port = null, settings = { recover: 1, tame: 1, bias: 0, mode: 'cambridge', on: true };
var stats = { frames: 0, busyMs: 0, worstMs: 0, dropped: 0, last: 0 };
var queue = [], running = false;

function apply() {
  if (settings.mode !== eng.mode) eng.setMode(settings.mode);
  eng.recover = settings.recover; eng.tame = settings.tame; eng.bias = settings.bias;
}
function pump() {
  if (running) return; running = true;
  while (queue.length) {
    if (queue.length > 8) { stats.dropped += queue.length - 2; queue.splice(0, queue.length - 2); }   // fell behind: keep newest
    var hop = queue.shift(), t0 = performance.now();
    var a = eng.step(hop);
    var g = settings.on ? a.gains : new Float64Array(C.K);
    eq.setGains(g);
    var dt = performance.now() - t0;
    stats.frames++; stats.busyMs += dt; if (dt > stats.worstMs) stats.worstMs = dt;
    var hr = new Float32Array(eq.hr), hi = new Float32Array(eq.hi);
    port.postMessage({ type: 'H', hr: hr, hi: hi }, [hr.buffer, hi.buffer]);
    var now = performance.now();
    if (now - stats.last > 500) {
      stats.last = now;
      var hidden = 0, audible = 0;
      for (var b = 0; b < C.K; b++) { if (a.lev[b] > 20) { if (a.margin[b] <= 0) hidden++; else audible++; } }
      var gview = new Float32Array(C.K); for (var k = 0; k < C.K; k++) gview[k] = g[k];
      self.postMessage({ type: 'stats', frames: stats.frames, load: stats.busyMs / (stats.frames * 10), worstMs: stats.worstMs,
        dropped: stats.dropped, hiddenShare: hidden / Math.max(hidden + audible, 1), gains: gview });
      stats.frames = 0; stats.busyMs = 0; stats.worstMs = 0;
    }
  }
  running = false;
}
self.onmessage = function (e) {
  var m = e.data;
  if (m.type === 'port') { port = m.port; port.onmessage = function (ev) { if (ev.data.type === 'hop') { queue.push(ev.data.x); pump(); } }; }
  else if (m.type === 'settings') { for (var k in m.s) settings[k] = m.s[k]; apply(); }
};
