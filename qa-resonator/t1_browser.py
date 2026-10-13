# Stage T1 (the water tower) — browser checks, by taps.
#   python3 qa-resonator/t1_browser.py [repo_root] [--browser=webkit]
# Chromium by default (a 390 px touch phone); --browser=webkit runs Safari's engine with iPhone 13 emulation.
# 1. Tank → Water tower by a tap: the body, its defaults, the label, Padding shown and the Mallet knob hidden,
#    the keys an octave up (phone size), the probe sent with the body, pad sent; it plays.
# 2. Each Padding chip by a tap: chosen, the engine told, a message saying what it is; each one plays.
# 3. Real size / Phone size by taps: the keys, the size note, the readout.
# 4. Size on the tower builds a new tower; the strike circle moves round the bowl by tap-then-tap.
# 5. Presets: a tower saved, the Tank loaded, the tower loaded back with its padding, keys and probe.
# 6. Back to the Tank: its own defaults, Mallet knob back, Padding hidden, pad 0 sent.
# 7. Width, script errors.
import sys, os, json, threading, functools, http.server
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if not a.startswith('--')]
ROOT = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..'))
BROWSER = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--browser=')), 'chromium')
PAGE = 'apps/resonator-next.html'
def serve(d):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=d); h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
srv = serve(ROOT); PORT = srv.server_address[1]
failed = 0
def check(name, ok, detail=''):
    global failed
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f' — {detail}' if detail else ''), flush=True); failed += 0 if ok else 1

RECORD = """(() => { const rec = window.__msgs = []; const orig = MessagePort.prototype.postMessage;
  MessagePort.prototype.postMessage = function (m, t) {
    try { const c = {}; for (const k in m) { const v = m[k]; c[k] = (v && ArrayBuffer.isView(v)) ? { __t: v.constructor.name, n: v.length } : v; } rec.push(c); } catch (e) {}
    return orig.apply(this, arguments); }; })();"""
LISTEN = """async (ms) => { const an = ctx.createAnalyser(); master.connect(an); const buf = new Float32Array(2048); let pk = 0;
  const t = performance.now(); while (performance.now() - t < ms) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf); for (const v of buf) pk = Math.max(pk, Math.abs(v)); }
  try { master.disconnect(an); } catch (e) {} return pk; }"""
XY = "(i) => { const r = cv.getBoundingClientRect(); return [r.left + _px[i], r.top + _py[i]]; }"
TARGET = """(avoid) => { const g = state.geo; let best = -1, bs = -1e9;
  for (const i of state.free) { const x = _px[i], y = _py[i]; if (y > H - 60 || y < 40 || x < 30 || x > W - 30) continue;
    let near = 1e9; for (const j of avoid) near = Math.min(near, Math.hypot(x - _px[j], y - _py[j]));
    let crowd = 1e9; for (let k = 0; k < g.P.length; k++) if (k !== i) crowd = Math.min(crowd, Math.hypot(x - _px[k], y - _py[k]));
    const sc = Math.min(near, 160) + 3 * Math.min(crowd, 20) + 40 * (_pf[i] || 0); if (near > 60 && sc > bs) { bs = sc; best = i; } }
  return best; }"""

def tap(pg, sel):
    pg.evaluate("s => { const e = document.querySelector(s); if (e) e.scrollIntoView({block:'center'}); }", sel); pg.tap(sel)

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True, 'device_scale_factor': 2}
    c = b.new_context(**dev); c.add_init_script(RECORD)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400); tap(pg, '#start'); pg.wait_for_timeout(2500)
    msgs = lambda: pg.evaluate('window.__msgs')
    def play_peak(semi=0):
        pg.evaluate(f'() => {{ play({semi}, 0.8); }}')
        return pg.evaluate(LISTEN, 1600)

    # ---------- 1. Tank → Water tower ----------
    t0 = pg.evaluate("() => ({ shape: state.shape, masses: state.geo.P.length, ratio: val.ratio, decay: val.decay, root: state.root })")
    pg.evaluate('window.__msgs.length = 0')
    tap(pg, '[data-shape="Tower"]'); pg.wait_for_timeout(3000)
    st = pg.evaluate("""() => ({ shape: state.shape, masses: state.geo.P.length, springs: state.geo.S.length, ratio: val.ratio, decay: val.decay, root: state.root,
      brand: document.getElementById('brand').textContent, padsShown: !document.getElementById('towerbits').hidden,
      hardHidden: document.querySelector('.knob[data-k="hard"]').hidden, pad1: document.querySelector('#pads .pad').textContent,
      pressed: [...document.querySelectorAll('[data-shape]')].filter(x => x.getAttribute('aria-pressed') === 'true').map(x => x.dataset.shape),
      info: state.info && state.info.probeOv })""")
    m = msgs(); structs = [x for x in m if x.get('t') == 'struct']; pads = [x['v'] for x in m if x.get('t') == 'p' and x.get('k') == 'pad']
    check('1a. a tap on Water tower builds the tower with its own defaults (Size 14: 89 masses, 220 springs; Stiffness 14; Sustain 1.6)',
          st['shape'] == 'Tower' and st['masses'] == 89 and st['springs'] == 220 and st['ratio'] == 14 and abs(st['decay'] - 1.6) < 1e-9 and st['pressed'] == ['Tower'],
          f"from {t0} to {st}")
    check('1b. the label says Tower; Padding and Size are shown, the Mallet knob is hidden', st['brand'] == 'RESONATOR · TOWER' and st['padsShown'] and st['hardHidden'], f"{st['brand']!r}, padding shown {st['padsShown']}, Mallet hidden {st['hardHidden']}")
    check('1c. the keys start at E4 (phone size)', st['root'] == 64 and st['pad1'] == 'E4', f"root {st['root']}, first key {st['pad1']}")
    check('1d. the body reaches the engine with its tuning probe, and the padding (Wool) with it', bool(structs) and structs[-1].get('probe', {}).get('n') == 89 * 3 and pads and pads[-1] == 2,
          f"probe {structs[-1].get('probe') if structs else None}, pad sent {pads}")
    pk = play_peak(0)
    check('1e. it plays', pk > 0.01, f'peak {pk:.3f}')

    # ---------- 2. Padding ----------
    rows = []; ok = True
    tap(pg, '.tab[data-page="strike"]')
    for i, nm in enumerate(['Leather', 'Wool', 'Styrofoam', 'Rubber']):
        pg.evaluate("node.port.postMessage({t:'hush'}); window.__msgs.length = 0"); pg.wait_for_timeout(300)
        tap(pg, f'[data-pad="{i + 1}"]'); pg.wait_for_timeout(200)
        sent = [x['v'] for x in msgs() if x.get('t') == 'p' and x.get('k') == 'pad']
        pressed = pg.evaluate("[...document.querySelectorAll('[data-pad]')].filter(x => x.getAttribute('aria-pressed') === 'true').map(x => x.dataset.pad)")
        msg = pg.evaluate("document.getElementById('msg').textContent"); pk = play_peak(0)
        good = sent == [i + 1] and pressed == [str(i + 1)] and len(msg) > 10 and pk > 0.01; ok = ok and good
        rows.append(f"{nm}: sent {sent}, chosen {pressed}, plays {pk:.3f}, says {msg[:38]!r}")
    check('2. each Padding chip by a tap: chosen, the engine told, says what it is, and plays', ok, ' · '.join(rows))

    # ---------- 3. Real size / Phone size ----------
    tap(pg, '#realsize'); pg.wait_for_timeout(200)
    r = pg.evaluate("() => ({ root: state.root, key: document.querySelector('#pads .pad').textContent, note: document.getElementById('sizenote').textContent, ro: document.getElementById('readout').textContent })")
    check('3a. Real size: the keys start at C3, and the page says it is the real 35 m tower', r['root'] == 48 and r['key'] == 'C3' and 'real size' in r['note'] and '35 m' in r['ro'], json.dumps(r))
    pk = play_peak(0)
    check('3b. it plays at real size', pk > 0.005, f'peak {pk:.3f}')
    tap(pg, '#phonesize'); pg.wait_for_timeout(200)
    r = pg.evaluate("() => ({ root: state.root, key: document.querySelector('#pads .pad').textContent, note: document.getElementById('sizenote').textContent })")
    check('3c. Phone size: the keys start at E4, a tower about 14 m tall', r['root'] == 64 and r['key'] == 'E4' and '14 m' in r['note'], json.dumps(r))

    # ---------- 4. Size; the strike circle on the bowl ----------
    tap(pg, '.tab[data-page="body"]'); n0 = pg.evaluate('state.geo.P.length')
    for q in range(40):
        if pg.evaluate('state.geo.P.length') != n0: break
        tap(pg, '.knob[data-k="size"] .step[data-d="1"]'); pg.wait_for_timeout(40)
    pg.wait_for_timeout(2500)
    n1 = pg.evaluate('state.geo.P.length'); probe = [x for x in msgs() if x.get('t') == 'struct'][-1].get('probe', {}).get('n')
    check('4a. Size + builds a bigger tower, with its probe', n1 > n0 and probe == n1 * 3, f'{n0} → {n1} masses, probe {probe}')
    pg.evaluate('state.spin = false'); pg.wait_for_timeout(300)
    h0 = pg.evaluate('state.hitIdx'); tgt = pg.evaluate(TARGET, [h0, pg.evaluate('state.micIdx')])
    x, y = pg.evaluate(XY, h0); pg.touchscreen.tap(x, y); pg.wait_for_timeout(150)
    x, y = pg.evaluate(XY, tgt); pg.evaluate('window.__msgs.length = 0'); pg.touchscreen.tap(x, y); pg.wait_for_timeout(300)
    h1 = pg.evaluate('state.hitIdx'); told = [x['i'] for x in msgs() if x.get('t') == 'hit']
    check('4b. tap the strike circle, then a ball of the tower: the strike moves there and the engine is told', h1 == tgt and told and told[-1] == tgt, f'#{h0} → #{h1} (wanted #{tgt}), engine told {told}')

    # ---------- 5. presets ----------
    tap(pg, '.tab[data-page="strike"]'); tap(pg, '[data-pad="4"]'); tap(pg, '#realsize')
    tap(pg, '.tab[data-page="body"]'); tap(pg, '#psave'); pg.wait_for_timeout(200)
    saved = pg.evaluate("document.getElementById('plist').value")
    tap(pg, '[data-shape="Tank"]'); pg.wait_for_timeout(2500)
    pg.evaluate('window.__msgs.length = 0'); pg.select_option('#plist', saved); tap(pg, '#pload'); pg.wait_for_timeout(2500)
    r = pg.evaluate("() => ({ shape: state.shape, pad: state.pad, root: state.root, masses: state.geo.P.length, n: state.n, ratio: val.ratio, hard: document.querySelector('.knob[data-k=\"hard\"]').hidden, brand: document.getElementById('brand').textContent })")
    m = msgs(); st = [x for x in m if x.get('t') == 'struct']; pads = [x['v'] for x in m if x.get('t') == 'p' and x.get('k') == 'pad']
    check('5. a saved tower (Rubber, real size) comes back from the Tank as saved: body, padding, keys, probe', r['shape'] == 'Tower' and r['pad'] == 4 and r['root'] == 48 and r['masses'] == n1
          and st and st[-1].get('probe', {}).get('n') == n1 * 3 and pads and pads[-1] == 4 and r['hard'] and r['brand'].endswith('TOWER'), f"{saved}: {r}; probe {st[-1].get('probe') if st else None}; pad sent {pads}")

    # ---------- 6. back to the Tank ----------
    pg.evaluate('window.__msgs.length = 0'); tap(pg, '[data-shape="Tank"]'); pg.wait_for_timeout(2500)
    r = pg.evaluate("() => ({ shape: state.shape, masses: state.geo.P.length, ratio: val.ratio, decay: val.decay, root: state.root, hard: !document.querySelector('.knob[data-k=\"hard\"]').hidden, bits: document.getElementById('towerbits').hidden, brand: document.getElementById('brand').textContent })")
    m = msgs(); st = [x for x in m if x.get('t') == 'struct']; pads = [x['v'] for x in m if x.get('t') == 'p' and x.get('k') == 'pad']
    check('6. back to the Tank: its own body and defaults, Mallet knob back, Padding hidden, no probe, pad 0', r['shape'] == 'Tank' and r['masses'] == 58 and r['ratio'] == 6 and r['decay'] == 4 and r['root'] == 52
          and r['hard'] and r['bits'] and st and 'probe' not in st[-1] and pads and pads[-1] == 0 and r['brand'].endswith('TANK'), f"{r}; pad sent {pads}")
    pk = play_peak(0)
    check('6b. the Tank plays', pk > 0.01, f'peak {pk:.3f}')

    # ---------- 7. ----------
    w = pg.evaluate('() => [innerWidth, document.documentElement.scrollWidth]')
    check('7a. nothing wider than the phone', w[1] <= w[0], f'{w[1]} px in {w[0]} px')
    check('7b. no script errors', not errs, str(errs[:5]))
    c.close(); b.close()
print(f'\n{failed} check(s) FAILED' if failed else '\nall T1 browser checks pass')
sys.exit(1 if failed else 0)
