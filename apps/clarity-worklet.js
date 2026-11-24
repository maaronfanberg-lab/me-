/* Clarity worklet: stereo in -> mono hops to the analysis worker; applies the latest minimum-phase EQ
   spectrum to both channels with 20 ms Hann frames, 10 ms hop (OLA). Requires clarity-engine.js to be
   added to the same AudioWorklet first (shares globalThis.Clarity). Latency: 2 hops (20 ms). */
class ClarityProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    const C = globalThis.Clarity; this.C = C; this.HOP = C.HOP;
    this.eq = new C.MinPhaseEQ(2);
    this.inL = new Float64Array(2 * this.HOP); this.inR = new Float64Array(2 * this.HOP);
    this.fill = 0; this.outL = []; this.outR = []; this.outPos = 0; this.bypass = false;
    this.mono = new Float32Array(this.HOP); this.wport = null; this.cpu = 0; this.n = 0; this.havePrimed = false;
    this.port.onmessage = (e) => {
      const m = e.data;
      if (m.type === 'port') { this.wport = m.port; this.wport.onmessage = (ev) => this.onH(ev.data); }
      else if (m.type === 'bypass') this.bypass = !!m.on;
    };
    this.pendingH = null; this.ready = false;
  }
  onH(d) { if (d.type === 'H') this.pendingH = d; }
  process(inputs, outputs) {
    const inp = inputs[0], out = outputs[0], H = this.HOP;
    const L = inp[0] || new Float32Array(128), R = inp[1] || L;
    const oL = out[0], oR = out[1] || out[0];
    for (let i = 0; i < L.length; i++) {
      // output first, then take the input sample: latency is exactly 2 hops (960 samples, 20 ms)
      if (this.outL.length) {
        const f = this.outL[0];
        oL[i] = f.bypass ? f.dl[this.outPos] : f.l[this.outPos];
        oR[i] = f.bypass ? f.dr[this.outPos] : f.r[this.outPos];
        this.outPos++;
        if (this.outPos === H) { this.outL.shift(); this.outPos = 0; }
      } else { oL[i] = 0; oR[i] = 0; }
      this.inL[H + this.fill] = L[i]; this.inR[H + this.fill] = R[i]; this.fill++;
      if (this.fill === H) this.hop();
    }
    return true;
  }
  hop() {
    const H = this.HOP;
    // frame covers the previous hop + this hop (2H samples)
    for (let i = 0; i < H; i++) this.mono[i] = 0.5 * (this.inL[H + i] + this.inR[H + i]);
    if (this.wport) { const x = new Float64Array(this.mono); this.wport.postMessage({ type: 'hop', x }, [x.buffer]); }
    if (this.pendingH) { const h = this.pendingH; this.pendingH = null; this.eq.hr.set(h.hr); this.eq.hi.set(h.hi); this.ready = true; }
    let yl, yr;
    if (this.ready) { yl = this.eq.processFrame(0, this.inL); yr = this.eq.processFrame(1, this.inR); }
    else { yl = this.inL.slice(0, H); yr = this.inR.slice(0, H); }       // before the first EQ arrives: dry, same delay
    // each output frame carries its processed and dry versions (same delay: bit-exact bypass)
    this.outL.push({ l: Float32Array.from(yl), r: Float32Array.from(yr), dl: Float32Array.from(this.inL.subarray(0, H)),
                     dr: Float32Array.from(this.inR.subarray(0, H)), bypass: this.bypass });
    this.inL.copyWithin(0, H); this.inR.copyWithin(0, H); this.fill = 0;
  }
}
registerProcessor('clarity-processor', ClarityProcessor);
