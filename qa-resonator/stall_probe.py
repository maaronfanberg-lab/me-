# Diagnostic (not a pass/fail check): where does the audio-clock freeze on a Size change go?
#   python3 qa-resonator/stall_probe.py [repo_root] [out_dir] [--browser=webkit|chromium]
# WebKit on macOS CI froze the audio clock for about 0.2 s when Size built a new Tank, on the Tank-only
# preview and (less consistently) on the preview before Stage I, while the page's main thread stayed free.
# This runs both pages with the engine instrumented in a test copy only: every message the engine handles
# and every render call is timed inside the audio thread (Date.now, 1 ms steps; events of 2 ms or more are
# kept with the audio clock's time). Each page is tried with the tank silent (asleep) and while it rings.
# If the freeze is inside a message handler or a render call, it shows up here; if it shows up in neither,
# the time is going somewhere outside the engine's code (the browser's audio path, garbage collection).
# Also logged: every wait of 30 ms or more between render calls, with how many messages the engine handled
# in it (a burst of many short messages would show as a long wait full of messages; the browser's own
# audio path as a long wait with none).
# First WebKit macOS run (2026-10-12): a 247 ms freeze with no message or render call of 2 ms or more.
import sys, os, json, subprocess, tempfile, threading, functools, http.server, platform
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if not a.startswith('--')]
ROOT = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(ROOT, 'webkit-out'))
BROWSER = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--browser=')), 'webkit')
BASE_SHA = 'fe0393fca33d313f138246fa465ad5cbb659e643'   # the preview just before Stage I
os.makedirs(OUT, exist_ok=True)

def instrument(html):
    """time every engine message and render call, inside the engine (test copy only)"""
    def rep(s, old, new):
        assert s.count(old) == 1, f'instrument: expected one {old!r}, found {s.count(old)}'
        return s.replace(old, new)
    ct = "(typeof currentTime!=='undefined'?currentTime:-1)"
    html = rep(html, "  msg(d){\n", "  msg(d){ if(d&&d.t==='__dump'){ this.port.postMessage({t:'__ev',ev:this.__ev||[]}); this.__ev=[]; return; }\n"
               "    this.__nm=(this.__nm||0)+1; const __t0=Date.now(); try{ return this.__msg(d); } finally { const __dt=Date.now()-__t0;\n"
               f"      if(__dt>=2) (this.__ev||(this.__ev=[])).push(['msg', d.t+(d.k?':'+d.k:''), __dt, {ct}]); }} }}\n"
               "  __msg(d){\n")
    html = rep(html, "  process(inputs, outputs){\n", "  process(inputs, outputs){ const __t0=Date.now();\n"
               # a long wait since the last render call ended, and how many messages the engine handled in it
               f"    if(this.__end&&__t0-this.__end>=30) (this.__ev||(this.__ev=[])).push(['gap', String(this.__nm||0), __t0-this.__end, {ct}]); this.__nm=0;\n"
               "    try{ return this.__process(inputs, outputs); } finally {\n"
               f"      const __e=Date.now(), __dt=__e-__t0; this.__end=__e; if(__dt>=2) (this.__ev||(this.__ev=[])).push(['render', '', __dt, {ct}]); }} }}\n"
               "  __process(inputs, outputs){\n")
    return html

STALL_JS = """async (d) => { let last = ctx.currentTime, lastWall = performance.now(), worst = 0, at = 0, prevTick = performance.now(), gap = 0;
  const tick = () => { const now = performance.now(), c = ctx.currentTime; gap = Math.max(gap, now - prevTick); prevTick = now;
    if (c !== last) { last = c; lastWall = now; } else if (now - lastWall > worst) { worst = now - lastWall; at = c; } };
  const iv = setInterval(tick, 4); await new Promise(r => setTimeout(r, 150)); gap = 0;
  const b = document.querySelector('.knob[data-k="size"] .step[data-d="' + d + '"]'), n0 = state.n, t0 = ctx.currentTime;
  for (let q = 0; q < 40 && state.n === n0; q++) { b.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); b.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); }
  const built = state.n !== n0 ? n0 + '→' + state.n : '';
  await new Promise(r => setTimeout(r, 2500)); clearInterval(iv); tick();
  return { freeze_ms: Math.round(worst), freeze_at: +at.toFixed(3), tap_at: +t0.toFixed(3), main_gap_ms: Math.round(gap), built }; }"""
DUMP_JS = """async () => { const got = new Promise(r => { const h = e => { if (e.data && e.data.t === '__ev') { node.port.removeEventListener('message', h); r(e.data.ev); } };
    node.port.addEventListener('message', h); });
  (TUNER && TUNER.raw ? TUNER.raw : node.port.postMessage.bind(node.port))({ t: '__dump' });
  return await Promise.race([got, new Promise(r => setTimeout(() => r(null), 3000))]); }"""
NOTE_JS = "() => { const p = document.querySelector('#pads .pad'); p.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); p.dispatchEvent(new PointerEvent('pointerup', {bubbles: true})); }"

def serve(d):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=d); h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s

TMP = tempfile.mkdtemp()
pages = {'tank-only (now)': open(os.path.join(ROOT, 'apps/resonator-next.html'), encoding='utf-8').read()}
base = subprocess.run(['git', '-C', ROOT, 'show', f'{BASE_SHA}:apps/resonator-next.html'], capture_output=True)
if base.returncode == 0: pages['before Stage I'] = base.stdout.decode('utf-8')
else: print(f'NOTE {BASE_SHA[:8]} not in this clone: only the current page is probed')
files = {}
for k, html in pages.items():
    f = ('now' if 'now' in k else 'before') + '.html'; open(os.path.join(TMP, f), 'w', encoding='utf-8').write(instrument(html)); files[k] = f
srv = serve(TMP); PORT = srv.server_address[1]

R = {'browser': BROWSER, 'platform': platform.platform(), 'runs': []}
with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True}
    R['browser_version'] = b.version
    for rnd in range(3):   # three rounds, the pages in turn, so neither always goes first (the freeze comes and goes)
        for label, f in (list(files.items()) if rnd % 2 == 0 else list(files.items())[::-1]):
            c = b.new_context(**dev); pg = c.new_page(); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e))); pg.route('**/fonts.g*/**', lambda r: r.abort())
            pg.goto(f'http://127.0.0.1:{PORT}/{f}'); pg.wait_for_timeout(400); pg.tap('#start'); pg.wait_for_timeout(2500)
            if pg.evaluate("!!document.getElementById('shapes')"):
                pg.click('#shapes .chip:text-is("Tank")'); pg.wait_for_timeout(3000)
            pg.evaluate(DUMP_JS)   # clear the start-up events
            for k, (mode, d) in enumerate([('silent', 1), ('silent', -1), ('ringing', 1), ('ringing', -1)]):
                if mode == 'ringing': pg.evaluate(NOTE_JS); pg.wait_for_timeout(300)
                else: pg.evaluate("document.getElementById('hush').click()"); pg.wait_for_timeout(1500)
                r = pg.evaluate(STALL_JS, str(d)); ev = pg.evaluate(DUMP_JS) or []
                # the engine's events within 0.5 s of the tap, by kind
                near = [e for e in ev if e[3] < 0 or (r['tap_at'] - 0.1 <= e[3] <= r['tap_at'] + 0.5)]
                msgs = sorted([e for e in near if e[0] == 'msg'], key=lambda e: -e[2])
                rend = [e for e in near if e[0] == 'render']
                gaps = sorted([e for e in near if e[0] == 'gap'], key=lambda e: -e[2])
                row = {'page': label, 'round': rnd, 'mode': mode, **r, 'engine_msg_ms_total': sum(e[2] for e in msgs),
                       'slowest_msgs': [[e[1], e[2]] for e in msgs[:4]], 'render_calls_2ms_plus': len(rend),
                       'render_ms_total': sum(e[2] for e in rend), 'slowest_render_ms': max([e[2] for e in rend], default=0),
                       'longest_waits_between_renders': [[e[2], 'messages in it: ' + e[1]] for e in gaps[:3]], 'errors': errs[:2]}
                R['runs'].append(row)
                print(f"{label:>16} r{rnd} {mode:8} {row['built']:5} freeze {r['freeze_ms']:4} ms (main gap {r['main_gap_ms']:3}) · engine messages {row['engine_msg_ms_total']:4} ms "
                      f"{row['slowest_msgs'][:2]} · slow renders {row['render_calls_2ms_plus']} ({row['render_ms_total']} ms, slowest {row['slowest_render_ms']}) "
                      f"· waits between renders ≥30 ms {row['longest_waits_between_renders']}", flush=True)
            c.close()
    b.close()
srv.shutdown()
json.dump(R, open(os.path.join(OUT, 'stall_probe.json'), 'w'), indent=1)
by = {}
for r in R['runs']: by.setdefault((r['page'], r['mode']), []).append(r['freeze_ms'])
print('\nfreeze (ms) by page and state: ' + ' · '.join(f'{k[0]} {k[1]} {v}' for k, v in by.items()))
