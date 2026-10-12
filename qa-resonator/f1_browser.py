# Stage F (plate reverb) — browser checks. Chromium by default; --browser=webkit for Safari's engine.
#   python3 qa-resonator/f1_browser.py [repo_root] [--browser=webkit]
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

# level of the output during [t0, t1] seconds after a key, measured live
TAIL_JS = """async ([t0, t1]) => { if (!window._an) { window._an = ctx.createAnalyser(); window._an.fftSize = 2048; (master || node).connect(window._an); }
  const an = window._an, buf = new Float32Array(2048); let pk = 0, bad = 0;
  const pad = document.querySelector('#pads .pad'); const s = performance.now();
  pad.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); pad.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
  while (performance.now() - s < t1 * 1000) { await new Promise(r => setTimeout(r, 20)); an.getFloatTimeDomainData(buf);
    if (performance.now() - s >= t0 * 1000) for (const v of buf) { if (!isFinite(v)) bad++; else pk = Math.max(pk, Math.abs(v)); } }
  return { pk, bad }; }"""
SET = "([k, v]) => { val[k] = v; syncKnob(k); send(k); }"

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True}
    c = b.new_context(**dev); pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.add_init_script("""window.__p=[]; const _pm=MessagePort.prototype.postMessage;
      MessagePort.prototype.postMessage=function(d,...r){ try{ if(d&&d.t==='p'&&String(d.k).startsWith('rv')) window.__p.push(d.k+'='+d.v); }catch(e){} return _pm.call(this,d,...r); };""")
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400)
    pg.tap('#start'); pg.wait_for_timeout(2000)

    pg.tap('.tab[data-page=fx]'); pg.wait_for_timeout(200)
    vis = pg.evaluate("""(() => { const s = [...document.querySelectorAll('#page-fx .secttl')].map(e => e.textContent);
      const ks = ['rvMix','rvTime','rvTone','rvPre'].map(k => { const w = document.querySelector('.knob[data-k='+k+']'); const r = w ? w.getBoundingClientRect() : null;
        return { k, label: w ? w.querySelector('.lab span').textContent : null, val: w ? w.querySelector('.lab b').textContent : null, steps: w ? w.querySelectorAll('.step').length : 0, w: r ? r.width : 0 }; });
      return { sections: s, knobs: ks, pageW: document.documentElement.scrollWidth }; })()""")
    check('FX tab has a Plate reverb section with four knobs, each with - and + buttons',
          'Plate reverb' in vis['sections'] and all(k['label'] and k['steps'] == 2 for k in vis['knobs']) and vis['pageW'] <= 390,
          json.dumps(vis)[:260])
    check('Reverb starts off', vis['knobs'][0]['val'] == 'off', vis['knobs'][0]['val'])

    # a short decay so the dry note is gone by 1 s; compare the level 1.0-1.6 s after a key, off vs on
    pg.evaluate(SET, ['decay', 0.25]); pg.wait_for_timeout(200)
    off = pg.evaluate(TAIL_JS, [1.0, 1.6]); pg.wait_for_timeout(400)
    for _ in range(16): pg.tap('.knob[data-k=rvMix] .step[data-d="1"]')
    pg.wait_for_timeout(300)
    mix = pg.evaluate('val.rvMix'); label = pg.inner_text('.knob[data-k=rvMix] .lab b')
    sent = pg.evaluate('window.__p.filter(s=>s.startsWith("rvMix="))')
    on = pg.evaluate(TAIL_JS, [1.0, 1.6])
    check('tapping + on Reverb turns it up and tells the engine', mix > 0.3 and sent and label.endswith('%'), f'{label}, engine told {sent[-1] if sent else None}')
    check('with Reverb on, the sound rings on after the body has stopped', on['pk'] > 20 * max(off['pk'], 1e-5) and on['bad'] == 0,
          f"level 1.0-1.6 s after a key: off {off['pk']:.5f} · on {on['pk']:.4f}")

    # a shape change keeps the setting and the reverb (the knob list is re-sent with the new body)
    pg.tap('.tab[data-page=body]'); pg.click('#shapes .chip:text-is("Chime")'); pg.wait_for_timeout(1200)
    pg.evaluate(SET, ['decay', 0.25]); pg.wait_for_timeout(200)
    on2 = pg.evaluate(TAIL_JS, [1.0, 1.6])
    check('after changing shape, Reverb is still on and still rings', pg.evaluate('val.rvMix') == mix and on2['pk'] > 20 * max(off['pk'], 1e-5), f"tail {on2['pk']:.4f}")

    # Hush stops the tail
    pg.evaluate("""(() => { const pad = document.querySelector('#pads .pad'); pad.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); pad.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); })()""")
    pg.wait_for_timeout(250); pg.tap('.tab[data-page=strike]'); pg.tap('#hush'); pg.wait_for_timeout(400)
    h = pg.evaluate("""async () => { const an = window._an, buf = new Float32Array(2048); let pk = 0;
      for (let i = 0; i < 20; i++) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf); for (const v of buf) pk = Math.max(pk, Math.abs(v)); } return pk; }""")
    check('Hush silences the reverb tail', h < 3.2e-5, f'peak after Hush {h:.2e}')

    # presets: a preset with reverb restores it; a preset from before reverb (no rv keys) comes back dry
    snap = pg.evaluate("JSON.stringify(snapshot())")
    pg.evaluate(SET, ['rvMix', 0]); pg.wait_for_timeout(100)
    pg.evaluate(f"restore(JSON.parse({json.dumps(snap)}))"); pg.wait_for_timeout(600)
    check('a preset saved with reverb brings it back', abs(pg.evaluate('val.rvMix') - mix) < 1e-9)
    old = pg.evaluate("(() => { const o = JSON.parse(%s); for (const k of ['rvMix','rvTime','rvTone','rvPre']) delete o.val[k]; return JSON.stringify(o); })()" % json.dumps(snap))
    pg.evaluate(f"restore(JSON.parse({json.dumps(old)}))"); pg.wait_for_timeout(600)
    check('a preset from before reverb loads with Reverb off', pg.evaluate('val.rvMix') == 0 and pg.inner_text('.knob[data-k=rvMix] .lab b') == 'off')

    # double-tap the name returns a knob to its default
    pg.evaluate(SET, ['rvTime', 6]); pg.tap('.tab[data-page=fx]')
    pg.tap('.knob[data-k=rvTime] .lab'); pg.wait_for_timeout(120); pg.tap('.knob[data-k=rvTime] .lab'); pg.wait_for_timeout(200)
    check('double-tap on Reverb time returns it to 2.5 s', pg.evaluate('val.rvTime') == 2.5, pg.inner_text('.knob[data-k=rvTime] .lab b'))
    check('no script errors', not errs, str(errs[:3]))
    c.close(); b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage F browser checks pass')
sys.exit(1 if failed else 0)
