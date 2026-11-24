"""Anti-pumping check (fixed before running): momentary loudness (BS.1770, 400 ms blocks every 100 ms)
of output minus input: std <= 0.5 dB and max |diff| <= 1.5 dB, at default (100/100/0) and at the extreme
setting Alex used (200/200/-100), on the chord+drums signal and the hidden-melody signal. Uses the JS engine."""
import json, os, sys, subprocess, tempfile
import numpy as np
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import stage4 as S4, hidden_melody as H
from scipy.signal import lfilter
NODE = r"""
const C = require(process.argv[2]); const fs = require('fs');
const x = new Float64Array(fs.readFileSync(process.argv[3]).buffer.slice(0));
const [rec, tam, bia] = process.argv[5].split(',').map(Number);
const eng = new C.ClarityEngine({mode:'cambridge', recover:rec, tame:tam, bias:bia}), eq = new C.MinPhaseEQ(1);
const H = C.HOP, n = Math.floor(x.length / H), y = new Float64Array(n*H);
for (let j = 0; j < n; j++) {
  const a = eng.step(x.subarray(j*H, (j+1)*H)); eq.setGains(a.gains);
  const seg = new Float64Array(2*H); seg.set(x.subarray(j*H, Math.min(j*H+2*H, x.length)));
  y.set(eq.processFrame(0, seg), j*H);
}
fs.writeFileSync(process.argv[4], Buffer.from(y.buffer));
"""
PASS = {"std_db": 0.5, "max_db": 1.5}
def momentary(x):
    y = lfilter(S4.KB2, S4.KA2, lfilter(S4.KB1, S4.KA1, x)); b, s = int(0.4 * 48000), int(0.1 * 48000)
    return np.array([-0.691 + 10 * np.log10(np.mean(y[i:i + b] ** 2) + 1e-20) for i in range(0, len(y) - b + 1, s)])
def main():
    rng = np.random.default_rng(1234); FS = 48000; t = np.arange(6 * FS) / FS
    xs = sum(0.08 / h * np.sin(2 * np.pi * f0 * h * t) for f0 in (110, 138.59, 164.81) for h in range(1, 10))
    for hit in np.arange(0.5, 6, 0.5):
        n0 = int(hit * FS); tt = t[:len(t) - n0]; xs[n0:] += 0.3 * rng.standard_normal(len(tt)) * np.exp(-tt / 0.05)
    xm, _ = H.make(3.0)
    td = tempfile.mkdtemp(); js = os.path.join(td, "r.js"); open(js, "w").write(NODE)
    eng = os.path.abspath(os.path.join(here, "..", "..", "apps", "clarity-engine.js"))
    rep = {"pass_conditions": PASS}; ok = True
    for name, x in [("chord_drums", xs), ("hidden_melody", xm)]:
        for st in ["1,1,0", "2,2,-1", "2,0,1"]:
            fi, fo = os.path.join(td, "x"), os.path.join(td, "y"); x.astype(np.float64).tofile(fi)
            subprocess.run(["node", js, eng, fi, fo, st], check=True)
            y = np.fromfile(fo, np.float64); xin = x[:len(y)]
            # compare with the 20 ms frame latency removed is unnecessary: OLA output is aligned to input
            d = momentary(y)[5:] - momentary(xin)[5:]
            r = {"std_db": round(float(d.std()), 3), "max_db": round(float(np.abs(d).max()), 3), "mean_db": round(float(d.mean()), 3)}
            r["pass"] = bool(r["std_db"] <= PASS["std_db"] and r["max_db"] <= PASS["max_db"]); ok &= r["pass"]
            rep[f"{name}@{st}"] = r
    rep["PASS"] = bool(ok)
    json.dump(rep, open(os.path.join(here, "pumping-report.json"), "w"), indent=1); print(json.dumps(rep, indent=1))
if __name__ == "__main__":
    main()
