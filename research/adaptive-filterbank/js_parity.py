"""Stage 6 — parity: apps/clarity-engine.js vs the Python fast engine (fast.py + stage4).
Pass conditions (fixed before the first run): PASS. Run: python3 js_parity.py  (needs node)."""
import json, os, sys, subprocess, tempfile
import numpy as np
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import fast, stage4 as S4, hidden_melody as H

PASS = {"lev_p99_db": 0.1, "margin_p99_db": 0.5, "gain_p99_db": 0.1, "audio_snr_db": 60.0}
NODE = r"""
const C = require(process.argv[2]); const fs = require('fs');
const x = new Float64Array(fs.readFileSync(process.argv[3]).buffer.slice(0));
const mode = process.argv[5];
const eng = new C.ClarityEngine({mode}), eq = new C.MinPhaseEQ(1);
const H = C.HOP, n = Math.floor(x.length / H), K = C.K;
const lev = new Float64Array(n*K), mg = new Float64Array(n*K), G = new Float64Array(n*K), y = new Float64Array(n*H);
const t0 = Date.now();
for (let j = 0; j < n; j++) {
  const a = eng.step(x.subarray(j*H, (j+1)*H));
  lev.set(a.lev, j*K); mg.set(a.margin, j*K); G.set(a.gains, j*K);
}
const ta = Date.now();
for (let j = 0; j < n; j++) {               // OLA: frame j = samples jH .. jH+2H (zero-padded at the end)
  eq.setGains(G.subarray(j*K, (j+1)*K));
  const seg = new Float64Array(2*H); seg.set(x.subarray(j*H, Math.min(j*H+2*H, x.length)));
  y.set(eq.processFrame(0, seg), j*H);
}
const tb = Date.now();
const out = process.argv[4];
fs.writeFileSync(out+'.lev', Buffer.from(lev.buffer)); fs.writeFileSync(out+'.mg', Buffer.from(mg.buffer));
fs.writeFileSync(out+'.G', Buffer.from(G.buffer)); fs.writeFileSync(out+'.y', Buffer.from(y.buffer));
fs.writeFileSync(out+'.t', JSON.stringify({analysis_ms: ta-t0, eq_ms: tb-ta, seconds: n*H/48000}));
"""

def py_ref(x, mode):
    lev, th, mg, w = fast.analyse_fast(x, mode)
    G = S4.gains2(lev, w, mode, 1, 1)
    y = S4.process(x, G)
    return lev, mg, G, y

def main():
    rng = np.random.default_rng(1234); FS = fast.FS
    xm, _ = H.make(3.0)
    t = np.arange(3 * FS) / FS
    xs = sum(0.08 / h * np.sin(2 * np.pi * f0 * h * t) for f0 in (110, 138.59, 164.81) for h in range(1, 10))
    for hit in np.arange(0.5, 3, 0.5):
        n0 = int(hit * FS); tt = t[:len(t) - n0]; xs[n0:] += 0.3 * rng.standard_normal(len(tt)) * np.exp(-tt / 0.05)
    x = np.concatenate([xm, xs]).astype(np.float64)
    rep = {"pass_conditions": PASS}
    td = tempfile.mkdtemp()
    js = os.path.join(td, "run.js"); open(js, "w").write(NODE)
    inp = os.path.join(td, "x.f64"); x.tofile(inp)
    eng = os.path.abspath(os.path.join(here, "..", "..", "apps", "clarity-engine.js"))
    for mode in ("cambridge", "munich"):
        out = os.path.join(td, mode)
        subprocess.run(["node", js, eng, inp, out, mode], check=True)
        n = len(x) // fast.HOP; K = len(fast.FC)
        rd = lambda e: np.fromfile(out + e, np.float64)
        jl, jm, jg, jy = rd(".lev").reshape(n, K).T, rd(".mg").reshape(n, K).T, rd(".G").reshape(n, K).T, rd(".y")
        pl, pm, pg, py = py_ref(x, mode)
        fin = np.isfinite(pm) & np.isfinite(jm)
        r = {
            "lev_p99_db": float(np.percentile(np.abs(jl - pl), 99)),
            "margin_p99_db": float(np.percentile(np.abs(jm - pm)[fin], 99)),
            "gain_p99_db": float(np.percentile(np.abs(jg - pg), 99)),
            "gain_max_db": float(np.abs(jg - pg).max()),
            "audio_snr_db": float(10 * np.log10(np.sum(py[:len(jy)] ** 2) / max(np.sum((py[:len(jy)] - jy) ** 2), 1e-300))),
            "node_timing": json.load(open(out + ".t")),
        }
        r = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
        # v5: gains/loudness logic changed in JS (anti-pumping, persistence, loudness hold from the
        # live spectrum) and is now tested directly on the JS engine (pumping_test.py, js_melody.py).
        # Parity here covers the shared analysis + masking model.
        r["pass"] = bool(r["lev_p99_db"] <= PASS["lev_p99_db"] and r["margin_p99_db"] <= PASS["margin_p99_db"])
        rep[mode] = r
    rep["STAGE6_PASS"] = all(rep[m]["pass"] for m in ("cambridge", "munich"))
    json.dump(rep, open(os.path.join(here, "stage6-report.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
