/* Lapse Width core: pure per-block DSP, shared by the AudioWorklet and the node tests (apps/lapse-width-test.js).
   Principles from the lapse-meter research, applied to a 2-channel signal feeding a matrix (virtual-surround) decoder:
   - the common (mid) component is the "shared vector"; too much of it collapses the image to the centre -> centre trim
   - adaptation steps are normalised by signal energy (NLMS / the per-step readout fix) -> same behaviour at any volume
   - each block's gain change is capped (the kick cap) -> no pumping
   State is a plain object; process() is deterministic: the same input and state give the same output. */
(function (root) {
  function makeState() { return { g: 1, em: 0, es: 0 }; }
  // p: {bypass, trim (0..0.5), target (side/mid RMS ratio, 0..2), auto (bool), mu (0..1), cap (max |dg| per block), rear (0..1), width (manual side gain)}
  function process(L, R, oL, oR, p, st) {
    var n = L.length, i;
    if (p.bypass) { for (i = 0; i < n; i++) { oL[i] = L[i]; oR[i] = R[i]; } return st; }
    var em = 0, es = 0;
    for (i = 0; i < n; i++) { var m = 0.5 * (L[i] + R[i]), s = 0.5 * (L[i] - R[i]); em += m * m; es += s * s; }
    st.em = 0.9 * st.em + 0.1 * em / n; st.es = 0.9 * st.es + 0.1 * es / n;
    var g = st.g;
    if (p.auto) {
      // NLMS-style: move side gain so g^2*E_s approaches target^2*E_m; the step is divided by total energy, so loudness cancels
      var err = p.target * p.target * st.em - g * g * st.es, tot = st.em + st.es + 1e-9;
      var dg = p.mu * err / tot;
      if (dg > p.cap) dg = p.cap; else if (dg < -p.cap) dg = -p.cap; // the cap: no lurches
      g = Math.max(0, Math.min(3, g + dg));
      if (st.es < 1e-12) g = st.g; // pure mono: nothing to widen, hold gain (never invent a side signal)
    } else {
      var d = p.width - g; if (d > p.cap) d = p.cap; else if (d < -p.cap) d = -p.cap; g = g + d;
    }
    var mg = 1 - p.trim, sg0 = st.g, sg1 = g, rg = 1 + p.rear;
    for (i = 0; i < n; i++) {
      var t = n > 1 ? i / (n - 1) : 1, sg = (sg0 + (sg1 - sg0) * t) * rg; // per-sample ramp inside the block: no zipper steps
      var m2 = mg * 0.5 * (L[i] + R[i]), s2 = sg * 0.5 * (L[i] - R[i]);
      var l = m2 + s2, r = m2 - s2;
      oL[i] = l > 1 ? 1 : l < -1 ? -1 : l; oR[i] = r > 1 ? 1 : r < -1 ? -1 : r;
    }
    st.g = g; return st;
  }
  var api = { makeState: makeState, process: process };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.LapseWidth = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
