"""Hidden-melody ground truth on the JS engine (the product). Same pass conditions as hidden_melody.py:
H1 median melody margin gain >= 3 dB, H2 >= 50% melody frames audible, H3 loudness within 1 dB.
Margins are measured by running the JS engine (Recover=Tame=0, so it only listens) on input and output."""
import json, os, sys, subprocess, tempfile
import numpy as np
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import hidden_melody as H, stage4 as S4
NODE = r"""
const C = require(process.argv[2]); const fs = require('fs');
const x = new Float64Array(fs.readFileSync(process.argv[3]).buffer.slice(0));
const [rec, tam, bia, proc] = process.argv[5].split(',').map(Number);
const eng = new C.ClarityEngine({mode:'cambridge', recover:rec, tame:tam, bias:bia}), eq = new C.MinPhaseEQ(1);
const H = C.HOP, n = Math.floor(x.length / H), K = C.K, y = new Float64Array(n*H), mg = new Float64Array(n*K);
for (let j = 0; j < n; j++) {
  const a = eng.step(x.subarray(j*H, (j+1)*H)); mg.set(a.margin, j*K);
  if (proc) { eq.setGains(a.gains); const seg = new Float64Array(2*H); seg.set(x.subarray(j*H, Math.min(j*H+2*H, x.length))); y.set(eq.processFrame(0, seg), j*H); }
}
fs.writeFileSync(process.argv[4] + '.y', Buffer.from(y.buffer)); fs.writeFileSync(process.argv[4] + '.mg', Buffer.from(mg.buffer));
"""
def run(js, eng, x, st, td, tag):
    fi = os.path.join(td, tag + ".x"); x.astype(np.float64).tofile(fi); fo = os.path.join(td, tag)
    subprocess.run(["node", js, eng, fi, fo, st], check=True)
    n = len(x) // 480
    return np.fromfile(fo + ".y", np.float64), np.fromfile(fo + ".mg", np.float64).reshape(n, -1).T
def main():
    td = tempfile.mkdtemp(); js = os.path.join(td, "m.js"); open(js, "w").write(NODE)
    eng = os.path.abspath(os.path.join(here, "..", "..", "apps", "clarity-engine.js"))
    x, notes = H.make(3.0); FC = np.arange(50.0, 16000.0, 25.0)
    def mel(mg):
        out = []
        for t0, f, Ln, thr in notes:
            b = int(np.argmin(np.abs(FC - f))); out.append(mg[b, int((t0 + 0.12) * 100):int((t0 + H.NOTE_S - 0.03) * 100)])
        return np.concatenate(out)
    rep = {"pass_conditions": H.PASS}
    _, mg_in = run(js, eng, x, "0,0,0,0", td, "in")
    for st in ["1,1,0", "1.5,1.5,0", "2,2,0", "0.5,0,1", "2,2,-1"]:
        y, _ = run(js, eng, x, st + ",1", td, "p")
        _, mg_out = run(js, eng, y, "0,0,0,0", td, "o")
        mi, mo = mel(mg_in), mel(mg_out)
        r = {"in_median": round(float(np.median(mi)), 2), "median_gain": round(float(np.median(mo - mi)), 2),
             "audible_out_pct": round(float((mo > 0).mean() * 100), 1), "lufs_delta": round(float(S4.lufs(y) - S4.lufs(x[:len(y)])), 2)}
        r["pass"] = bool(r["median_gain"] >= 3 and r["audible_out_pct"] >= 50 and abs(r["lufs_delta"]) <= 1)
        rep[st] = r
    rep["PASS_default"] = rep["1,1,0"]["pass"]
    json.dump(rep, open(os.path.join(here, "js-melody-report.json"), "w"), indent=1); print(json.dumps(rep, indent=1))
if __name__ == "__main__":
    main()
