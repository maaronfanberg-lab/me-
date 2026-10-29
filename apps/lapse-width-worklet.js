/* AudioWorklet wrapper: runs LapseWidth.process (lapse-width-core.js, loaded first into the same scope) on each 128-frame block. */
class LapseWidthNode extends AudioWorkletProcessor {
  constructor() {
    super(); this.st = LapseWidth.makeState(); this.n = 0;
    this.p = { bypass: false, trim: 0.2, target: 0.5, auto: true, mu: 0.05, cap: 0.004, rear: 0.3, width: 1 };
    this.port.onmessage = e => Object.assign(this.p, e.data);
  }
  process(inputs, outputs) {
    const i = inputs[0], o = outputs[0];
    if (!i || i.length < 2) { if (i && i.length === 1) { o[0].set(i[0]); o[1].set(i[0]); } return true; }
    LapseWidth.process(i[0], i[1], o[0], o[1], this.p, this.st);
    if (++this.n % 20 === 0) this.port.postMessage({ g: this.st.g, ratio: Math.sqrt(this.st.es / (this.st.em + 1e-12)) });
    return true;
  }
}
registerProcessor("lapse-width", LapseWidthNode);
