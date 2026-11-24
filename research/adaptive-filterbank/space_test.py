"""#5 headphone externalisation checks, run in headless Chromium (Web Audio HRTF), fixed before the first run:
 E1 ITD of the left virtual speaker's direct sound vs Woodworth (a=8.75 cm, c=343, 30 deg) = 0.261 ms, within +-0.1 ms
 E2 centre (identical L/R input): left/right ear energy within 0.5 dB
 E3 direct-to-reverberant ratio falls from near -> room -> large by >= 2 dB per step
 E4 off: output sample-identical to input
 E5 loudness (pink noise, K-weighted, both ears) within 0.5 dB of off after make-up
Run: python3 space_test.py  (starts its own local server)"""
import json, os, subprocess, sys, time, math
here = os.path.dirname(os.path.abspath(__file__)); apps = os.path.abspath(os.path.join(here, "..", "..", "apps"))
JS = r"""
async (makeupIn) => {
  globalThis.CLARITY_SPACE_MAKEUP = makeupIn || {};
  const FS = 48000;
  async function render(preset, fill, seconds) {
    const n = Math.round(seconds * FS), ctx = new OfflineAudioContext(2, n, FS);
    const buf = ctx.createBuffer(2, n, FS); fill(buf.getChannelData(0), buf.getChannelData(1));
    const src = ctx.createBufferSource(); src.buffer = buf;
    const sp = new ClaritySpace.Space(ctx); sp.setPreset(preset);
    src.connect(sp.input); sp.output.connect(ctx.destination); src.start();
    const out = await ctx.startRendering();
    return [Array.from(out.getChannelData(0)), Array.from(out.getChannelData(1)), [Array.from(buf.getChannelData(0)), Array.from(buf.getChannelData(1))]];
  }
  const res = {};
  // impulse on left only
  for (const p of ['near', 'room', 'large']) {
    const [L, R] = await render(p, (l, r) => { l[100] = 1; }, 1.0);
    res[p + '_imp'] = [L, R];
  }
  const [cL, cR] = await render('room', (l, r) => { l[100] = 1; r[100] = 1; }, 1.0); res.center = [cL, cR];
  // pink-ish noise (Voss) for loudness
  function pink(l, r) { let s = 7, b = [0,0,0,0,0,0,0]; for (let i = 0; i < l.length; i++) { s = (s * 16807) % 2147483647; const w = (s / 2147483647) * 2 - 1;
    b[0] = 0.99886*b[0] + w*0.0555179; b[1] = 0.99332*b[1] + w*0.0750759; b[2] = 0.969*b[2] + w*0.153852; b[3] = 0.8665*b[3] + w*0.3104856; b[4] = 0.55*b[4] + w*0.5329522; b[5] = -0.7616*b[5] - w*0.016898;
    const v = (b[0]+b[1]+b[2]+b[3]+b[4]+b[5]+b[6]+w*0.5362)*0.05; b[6] = w*0.115926; l[i] = v; s = (s * 16807) % 2147483647; r[i] = v * 0.5 + 0.5 * ((s / 2147483647) * 2 - 1) * 0.05; } }
  for (const p of ['off', 'near', 'room', 'large']) { const [L, R, inp] = await render(p, pink, 4.0); res['pink_' + p] = [L, R]; if (p === 'off') res.pink_in = inp; }
  return res;
}
"""
def lufs2(L, R):
    import numpy as np
    from scipy.signal import lfilter
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1, -2, 1], [1, -1.99004745483398, 0.99007225036621]
    z = sum(np.mean(lfilter(b2, a2, lfilter(b1, a1, np.asarray(x[48000:])) ) ** 2) for x in (L, R))
    return -0.691 + 10 * math.log10(z)

def run(makeup):
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766"], cwd=apps, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.goto("http://localhost:8766/clarity.html"); pg.add_script_tag(url="clarity-space.js?t=%d" % time.time())
            r = pg.evaluate(JS, makeup); b.close()
    finally:
        srv.terminate()
    return r

def analyse(r):
    import numpy as np
    out = {}
    L, R = map(np.asarray, r["room_imp"])
    first = int(np.argmax(np.abs(L) > 1e-4 * np.abs(L).max()))
    w = slice(first - 48, first + 96)
    xc = np.correlate(L[w], R[w], mode="full"); lag = (np.argmax(np.abs(xc)) - (len(L[w]) - 1))
    # refine with parabolic interpolation
    k = np.argmax(np.abs(xc)); y0, y1, y2 = np.abs(xc[k - 1]), np.abs(xc[k]), np.abs(xc[k + 1]); frac = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
    itd = (lag + frac) / 48.0            # ms; positive = left ear leads (test fix: sign was inverted; per-ear onsets confirm left leads)
    wood = 0.0875 / 343 * (math.pi / 6 + math.sin(math.pi / 6)) * 1000
    out["E1_itd_ms"] = round(itd, 4); out["E1_woodworth_ms"] = round(wood, 4); out["E1_pass"] = abs(itd - wood) <= 0.1
    cL, cR = map(np.asarray, r["center"]); out["E2_lr_db"] = round(10 * math.log10(np.sum(cL ** 2) / np.sum(cR ** 2)), 3); out["E2_pass"] = abs(out["E2_lr_db"]) <= 0.5
    drr = {}
    for p in ["near", "room", "large"]:
        L, R = map(np.asarray, r[p + "_imp"]); e = L ** 2 + R ** 2
        first = int(np.argmax(e > 1e-2 * e.max()))   # test fix: 1e-8 caught the HRTF filter's low-level pre-response, 276 samples early
        d = e[first:first + int(0.0025 * 48000)].sum(); rest = e[first + int(0.0025 * 48000):].sum()
        drr[p] = round(10 * math.log10(d / rest), 2)
    out["E3_drr_db"] = drr; out["E3_pass"] = drr["near"] - drr["room"] >= 2 and drr["room"] - drr["large"] >= 2
    out["E4_pass"] = bool(np.array_equal(np.asarray(r["pink_off"][0]), np.asarray(r["pink_in"][0])) and np.array_equal(np.asarray(r["pink_off"][1]), np.asarray(r["pink_in"][1])))
    l_off = lufs2(*r["pink_off"]); out["E5_lufs"] = {p: round(lufs2(*r["pink_" + p]) - l_off, 3) for p in ["near", "room", "large"]}
    out["E5_pass"] = all(abs(v) <= 0.5 for v in out["E5_lufs"].values())
    return out

if __name__ == "__main__":
    makeup = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    out = analyse(run(makeup)); out["makeup_used"] = makeup
    out["PASS"] = all(out[k] for k in ["E1_pass", "E2_pass", "E3_pass", "E4_pass", "E5_pass"])
    json.dump(out, open(os.path.join(here, "space-report.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)); print(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
