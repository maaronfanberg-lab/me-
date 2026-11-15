# Stage 3 browser checks: plectrum, oscillator with hold-to-sustain, wind, Mic in (Chromium's fake
# microphone), audition auto-release, mode switching. Run from the repo root:
#   python3 qa-resonator/stage3_browser.py [repo_root]
import sys, os, threading, functools, http.server
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..'))
PAGE = 'apps/resonator-next.html'
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
failed = 0
def check(name, ok, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (' — ' + detail if detail else '')); failed += 0 if ok else 1

# peak of the speaker-bound output over `ms`, after running `pre` (JS) — no key pressed unless pre does it
LEVEL = """async([pre, ms])=>{ if(!window._an){window._an=ctx.createAnalyser();window._an.fftSize=2048;(master||node).connect(window._an);}
  const an=window._an,buf=new Float32Array(2048); let pk=0, bad=0; if(pre) eval(pre);
  const n=Math.round(ms/25); for(let i=0;i<n;i++){ await new Promise(r=>setTimeout(r,25)); an.getFloatTimeDomainData(buf); for(const v of buf){ if(!isFinite(v)) bad++; else pk=Math.max(pk,Math.abs(v)); } }
  return {pk:+pk.toFixed(4), bad}; }"""
PAD_DOWN = "document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));"
PAD_UP = "document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));"
def mode_chip(pg, name): pg.click(f'#modes .chip:text-is("{name}")'); pg.wait_for_timeout(150)

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    c = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    c.grant_permissions(['microphone'], origin=f'http://127.0.0.1:{PORT}')
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(300)
    pg.tap('#start'); pg.wait_for_timeout(1800)
    pg.tap('.tab[data-page=strike]'); pg.wait_for_timeout(150)
    chips = pg.evaluate("[...document.querySelectorAll('#modes .chip')].map(c=>c.textContent)")
    check('excitation modes offered', chips == ['Mallet', 'Worthington splash', 'Plectrum', 'Oscillator'], str(chips))

    # --- plectrum ---
    mode_chip(pg, 'Plectrum')
    pl = pg.evaluate(LEVEL, [PAD_DOWN + PAD_UP, 1200])
    check('plectrum plays', pl['pk'] > 0.05 and pl['bad'] == 0, f"peak {pl['pk']}")
    pg.wait_for_timeout(1500)

    # --- oscillator: sustains while held, dies away after release ---
    mode_chip(pg, 'Oscillator')
    pg.evaluate(f"(()=>{{ {PAD_DOWN} }})()")
    held = pg.evaluate(LEVEL, [None, 900]); pg.wait_for_timeout(600)
    still = pg.evaluate(LEVEL, [None, 400])           # key still down: should keep going
    pg.evaluate(f"(()=>{{ {PAD_UP} }})()")
    pg.wait_for_timeout(2600)
    after = pg.evaluate(LEVEL, [None, 400])
    check('oscillator sustains while the key is held', held['pk'] > 0.05 and still['pk'] > 0.5 * held['pk'], f"held {held['pk']}, 1.5 s later {still['pk']}")
    check('oscillator dies away after the key is released', after['pk'] < 0.35 * still['pk'], f"2.6 s after release {after['pk']} (was {still['pk']})")

    # --- audition from the strike tool releases itself in oscillator mode ---
    pg.wait_for_timeout(2000)
    pg.click('.tool[data-tool=strike]'); pg.wait_for_timeout(150)
    xy = pg.evaluate("(()=>{const r=cv.getBoundingClientRect();const i=state.free[2];return [r.left+_px[i],r.top+_py[i]];})()")
    aud = pg.evaluate(LEVEL, [f"(()=>{{}})()", 10])
    pg.mouse.click(xy[0], xy[1]); a1 = pg.evaluate(LEVEL, [None, 500]); pg.wait_for_timeout(3000); a2 = pg.evaluate(LEVEL, [None, 400])
    check('strike-tool audition releases itself (oscillator mode)', a1['pk'] > 0.03 and a2['pk'] < 0.35 * a1['pk'], f"during {a1['pk']}, 3 s later {a2['pk']}")
    pg.click('.tool[data-tool=orbit]')

    # --- leaving oscillator mode releases a held note ---
    pg.evaluate(f"(()=>{{ {PAD_DOWN} }})()"); pg.wait_for_timeout(700)
    mode_chip(pg, 'Mallet'); pg.wait_for_timeout(2800)
    rel = pg.evaluate(LEVEL, [None, 400]); pg.evaluate(f"(()=>{{ {PAD_UP} }})()")
    check('switching away from Oscillator releases held notes', rel['pk'] < 0.08, f"level 2.8 s after switching: {rel['pk']}")
    pg.wait_for_timeout(1500)

    # --- wind: tap-only knob; sound with no key; back to still → dies away ---
    quiet = pg.evaluate(LEVEL, [None, 400])
    for _ in range(19): pg.tap('.knob[data-k=wind] .step[data-d="1"]')   # ≈ 60 %
    lab = pg.inner_text('.knob[data-k=wind] .lab b')
    w = pg.evaluate(LEVEL, [None, 1200])
    pg.tap('.knob[data-k=wind] .lab'); pg.wait_for_timeout(120); pg.tap('.knob[data-k=wind] .lab')   # double-tap: back to default (still)
    pg.wait_for_timeout(3000); w0 = pg.evaluate(LEVEL, [None, 400]); lab0 = pg.inner_text('.knob[data-k=wind] .lab b')
    check('wind sings with no key pressed (tap-only knob)', w['pk'] > 0.03 and w['pk'] > 5 * max(quiet['pk'], 1e-4), f"wind {lab}: {w['pk']} (silence before: {quiet['pk']})")
    check('wind back to still: sound dies away', lab0 == 'still' and w0['pk'] < 0.2 * w['pk'], f"{lab0}: {w0['pk']}")

    # --- Mic in (fake microphone) ---
    before = pg.evaluate(LEVEL, [None, 500])
    pg.tap('#micin'); pg.wait_for_timeout(1500)
    label_on = pg.inner_text('#micin')
    on = pg.evaluate(LEVEL, [None, 1200])
    pg.tap('#micin'); pg.wait_for_timeout(2500)
    label_off = pg.inner_text('#micin'); tracks = pg.evaluate("MIC.stream===null && !MIC.on")
    off = pg.evaluate(LEVEL, [None, 500])
    check('Mic in: the microphone drives the body', label_on == 'Mic in: on' and on['pk'] > 0.02 and on['pk'] > 5 * max(before['pk'], 1e-4), f"{label_on}: {on['pk']} (before {before['pk']})")
    check('Mic in off: stream stopped, sound dies away', label_off == 'Mic in' and tracks and off['pk'] < 0.25 * on['pk'], f"{label_off!r}: {off['pk']}")

    check('no page errors', not errs, str(errs[:3]))
    b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage 3 browser checks pass')
sys.exit(1 if failed else 0)
