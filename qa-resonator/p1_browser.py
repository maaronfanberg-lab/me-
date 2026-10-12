# Phone performance P1 — browser checks (Playwright + Chromium; also runs in WebKit via --browser=webkit).
#   python3 qa-resonator/p1_browser.py [repo_root] [--browser=webkit]
import sys, os, json, threading, functools, http.server
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if not a.startswith('--')]
ROOT = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..'))
BROWSER = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--browser=')), 'chromium')
PAGE = 'apps/resonator-next.html'
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
failed = 0
def check(name, ok, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (' — ' + detail if detail else ''), flush=True); failed += 0 if ok else 1

PEAK_JS = """async (ms) => { if (!window._an) { window._an = ctx.createAnalyser(); window._an.fftSize = 2048; (master || node).connect(window._an); }
  const an = window._an, buf = new Float32Array(2048); let pk = 0, bad = 0;
  const pad = document.querySelector('#pads .pad');
  pad.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); pad.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
  for (let i = 0; i < ms / 25; i++) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf);
    for (const v of buf) { if (!isFinite(v)) bad++; else pk = Math.max(pk, Math.abs(v)); } }
  return { pk: +pk.toFixed(3), bad }; }"""
PLAY_N = """async (n) => { const pads = [...document.querySelectorAll('#pads .pad')];
  for (let i = 0; i < n; i++) { const p = pads[i % pads.length]; p.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
    p.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); await new Promise(r => setTimeout(r, 120)); } }"""
SET = "([k, v]) => { val[k] = v; syncKnob(k); send(k); }"

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True}
    c = b.new_context(**dev)
    if BROWSER == 'chromium':
        c.grant_permissions(['clipboard-read', 'clipboard-write'], origin=f'http://127.0.0.1:{PORT}')
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    sent = []
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.add_init_script("""window.__perfSent=[]; const _pm=MessagePort.prototype.postMessage;
      MessagePort.prototype.postMessage=function(d,...r){ try{ if(d&&d.t==='perf') window.__perfSent.push(JSON.stringify(d)); }catch(e){} return _pm.call(this,d,...r); };""")
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400)
    pg.tap('#start'); pg.wait_for_timeout(2200)
    live = pg.evaluate("ctx.state") == 'running'

    perf = pg.evaluate("window.__perfSent")
    check('page turns on sleep and the governor for live play', any('"sleep":1' in s and '"gov":1' in s for s in perf), str(perf))
    r = pg.evaluate("({cpu: state.cpu, max: state.cpuMax, txt: (document.getElementById('cpuinfo')||{}).textContent || ''})")
    check('CPU shown on the page, measured by the engine', r['cpu'] is not None and r['txt'].startswith('CPU ') and r['txt'].endswith('%'), json.dumps(r))

    # live load: idle vs Tank with 4 voices all ringing. Since Stage I the preview has only the Tank (no shape chips).
    def shape(name):
        if pg.evaluate("!!document.getElementById('shapes')"):
            pg.click(f'#shapes .chip:text-is("{name}")'); pg.wait_for_timeout(1500)
    idle = pg.evaluate("state.cpu")
    shape('Tank')
    pg.evaluate(SET, ['voices', 4]); pg.wait_for_timeout(300)
    pg.evaluate(PLAY_N, 8); pg.wait_for_timeout(1500)
    busy = pg.evaluate("state.cpu")
    check('live CPU reading rises with work (idle vs Tank, 4 voices ringing)', live and busy > idle, f'idle {idle:.3f} · Tank 4 voices {busy:.3f}')

    # governor: two hot readings (test hook) shed a voice and the page says so
    ga0 = pg.evaluate("state.ga||0")
    pg.evaluate(PLAY_N, 4)
    pg.evaluate("node.port.postMessage({t:'perfTest',c:0.95}); node.port.postMessage({t:'perfTest',c:0.95});")
    pg.wait_for_timeout(600)
    g = pg.evaluate("({ga: state.ga||0, aw: state.aw, cap: state.cap, msg: document.getElementById('msg').textContent})")
    # >= : on a busy machine the real governor may act as well as the test's two hot readings
    check('governor sheds a voice when the phone runs out of time, and the page explains', g['ga'] >= ga0 + 1 and g['cap'] < 4 and 'running out of time' in g['msg'], json.dumps(g)[:240])
    pk = pg.evaluate(PEAK_JS, 1200)
    check('still plays after the governor acted', pk['pk'] > 0.05 and pk['bad'] == 0, f"peak {pk['pk']}")

    # sleep: short decay, a few notes, then quiet: voices fall asleep
    shape('String')
    pg.evaluate(SET, ['voices', 4]); pg.evaluate(SET, ['decay', 0.3]); pg.wait_for_timeout(200)
    sl0 = pg.evaluate("state.sl||0")
    pg.evaluate(PLAY_N, 4); pg.wait_for_timeout(2500)
    s = pg.evaluate("({sl: state.sl||0, aw: state.aw})")
    check('voices fall asleep once they have died away', s['sl'] > sl0 and s['aw'] == 0, json.dumps(s))
    pk = pg.evaluate(PEAK_JS, 800)
    check('a sleeping voice wakes on the next key', pk['pk'] > 0.05 and pk['bad'] == 0, f"peak {pk['pk']}")

    if BROWSER == 'chromium':
        pg.click('#copydiag'); pg.wait_for_timeout(400)
        txt = pg.evaluate('navigator.clipboard.readText()')
        line = next((l for l in txt.split('\n') if l.startswith('cpu: ')), '')
        check('Copy report includes the CPU line', '% now' in line and 'highest' in line and 'let go' in line, line)
    check('no script errors', not errs, str(errs[:3]))
    c.close(); b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall P1 browser checks pass')
sys.exit(1 if failed else 0)
