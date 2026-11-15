# Stage I (Tank only, Sustain, touch the circles) — browser checks.
#   python3 qa-resonator/i1_browser.py [repo_root] [--browser=webkit]
# Chromium by default; --browser=webkit runs Safari's engine with iPhone 13 emulation.
# 1. What is gone, what stays, and Sustain.
# 2. The same sound as before: the same taps on the page before Stage I (from git) and on this one; every
#    message each page sent to the engine is recorded and replayed into one engine (i1_replay.mjs), and the
#    two outputs must be bit-identical. Needs the baseline commit; reported as a note when git lacks it.
# 3. The circles: press and slide (touch on Chromium through the DevTools protocol, the mouse on both),
#    tap then tap (real touch taps on both), a drag elsewhere turns the view, two circles on one mass.
# 4. Presets: save and load; old presets cannot switch a removed feature back on; other shapes refused.
import sys, os, json, subprocess, tempfile, threading, functools, http.server, math
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if not a.startswith('--')]
ROOT = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..'))
BROWSER = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--browser=')), 'chromium')
BASE_SHA = 'fe0393fca33d313f138246fa465ad5cbb659e643'   # the preview just before Stage I
PAGE = 'apps/resonator-next.html'
def serve(d):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=d); h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
srv = serve(ROOT); PORT = srv.server_address[1]
TMP = tempfile.mkdtemp()
failed = 0
def check(name, ok, detail='', critical=True):
    global failed
    s = 'PASS' if ok else ('FAIL' if critical else 'NOTE')
    print(f'{s} {name}' + (f' — {detail}' if detail else ''), flush=True); failed += 0 if ok or not critical else 1

RECORD = """(() => { const rec = window.__msgs = []; const orig = MessagePort.prototype.postMessage;
  MessagePort.prototype.postMessage = function (m, t) {
    try { const c = {}; for (const k in m) { const v = m[k]; c[k] = (v && ArrayBuffer.isView(v)) ? { __t: v.constructor.name, v: Array.from(v) } : v; } rec.push(c); } catch (e) {}
    return orig.apply(this, arguments); }; })();"""
LISTEN = """async (ms) => { const an = ctx.createAnalyser(); master.connect(an); const buf = new Float32Array(2048); let pk = 0;
  const t = performance.now(); while (performance.now() - t < ms) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf); for (const v of buf) pk = Math.max(pk, Math.abs(v)); }
  try { master.disconnect(an); } catch (e) {} return pk; }"""
XY = "(i) => { const r = cv.getBoundingClientRect(); return [r.left + _px[i], r.top + _py[i]]; }"
# a free mass that is well clear of both circles and of the buttons, facing the camera
TARGET = """(avoid) => { const r = cv.getBoundingClientRect(), g = state.geo; let best = -1, bs = -1e9;
  for (const i of state.free) { const x = _px[i], y = _py[i]; if (y > H - 60 || y < 40 || x < 30 || x > W - 30) continue;
    let near = 1e9; for (const j of avoid) near = Math.min(near, Math.hypot(x - _px[j], y - _py[j]));
    let crowd = 1e9; for (let k = 0; k < g.P.length; k++) if (k !== i) crowd = Math.min(crowd, Math.hypot(x - _px[k], y - _py[k]));
    const sc = Math.min(near, 160) + 3 * Math.min(crowd, 20) + 40 * (_pf[i] || 0); if (near > 70 && sc > bs) { bs = sc; best = i; } }
  return best; }"""

def tap(pg, sel):
    pg.evaluate("s => { const e = document.querySelector(s); if (e) e.scrollIntoView({block:'center'}); }", sel); pg.tap(sel)

def steps(pg, plan):
    """plan: [(tab, knob, +1/-1, count)] — taps on the knob's +/- buttons, as a finger would"""
    for tab, k, d, n in plan:
        tap(pg, f'.tab[data-page={tab}]')
        for _ in range(n):
            tap(pg, f'.knob[data-k="{k}"] .step[data-d="{d}"]'); pg.wait_for_timeout(40)

PLAN = [('body', 'decay', 1, 3), ('body', 'ratio', -1, 2), ('body', 'loss', 1, 1), ('body', 'sub', 1, 1), ('body', 'voices', 1, 1),
        ('body', 'nl', 1, 2), ('body', 'tune', 1, 1), ('body', 'size', 1, 3),
        ('strike', 'drive', 1, 1), ('strike', 'hard', 1, 2), ('strike', 'hit', 1, 2), ('strike', 'angle', 1, 2), ('strike', 'gain', -1, 1),
        ('mic', 'mic', 1, 3), ('mic', 'blend', 1, 2), ('mic', 'bite', 1, 1), ('mic', 'tone', -1, 3)]

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True, 'device_scale_factor': 2}
    def open_page(url, record=False):
        c = b.new_context(**dev)
        if record: c.add_init_script(RECORD)
        pg = c.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        pg.route('**/fonts.g*/**', lambda r: r.abort())
        pg.goto(url); pg.wait_for_timeout(400); tap(pg, '#start'); pg.wait_for_timeout(2500)
        return c, pg, errs

    # ---------- 2. the same sound as before ----------
    base = subprocess.run(['git', '-C', ROOT, 'show', f'{BASE_SHA}:{PAGE}'], capture_output=True)
    if base.returncode == 0:
        open(os.path.join(TMP, 'before.html'), 'wb').write(base.stdout)
        srv2 = serve(TMP)
        recs = {}
        for label, url in [('before', f'http://127.0.0.1:{srv2.server_address[1]}/before.html'), ('after', f'http://127.0.0.1:{PORT}/{PAGE}')]:
            c, pg, errs = open_page(url, record=True)
            if label == 'before':
                pg.click('#shapes .chip:text-is("Tank")'); pg.wait_for_timeout(2000)
            steps(pg, PLAN); pg.wait_for_timeout(2500)
            pg.evaluate("() => { play(0, 0.8); setTimeout(() => stop(0), 200); play(7, 0.6); }"); pg.wait_for_timeout(800)
            recs[label] = {'rate': pg.evaluate('ctx.sampleRate'), 'msgs': pg.evaluate('window.__msgs')}
            json.dump(recs[label], open(os.path.join(TMP, label + '.json'), 'w'))
            c.close()
        srv2.shutdown()
        out = subprocess.run(['node', os.path.join(ROOT, 'qa-resonator', 'i1_replay.mjs'), os.path.join(TMP, 'before.json'), os.path.join(TMP, 'after.json')],
                             capture_output=True, text=True, timeout=600)
        try:
            res = json.loads(out.stdout.strip().splitlines()[-1])
        except Exception:
            res = {'same': False, 'error': (out.stdout + out.stderr)[-400:]}
        # J1: the page no longer sends the removed controls at all (the engine has none of them left); a removed
        # control may only differ by being absent now. The sound must still be bit-identical.
        REMOVED = {'width','pkAp','pkSpc','pkRes','pkQ','amp','bass','treb','cab','splash','fbAmt','fbTime','coup','regime','rswitch','rphi','mem','memSpan',
                   'infer','spread','att','attC','fxCho','fxDly','fxFb','fxWow','fxTrem','fxSat','spImg','spDist','spRefl','spDop','spRot','spElev','bowSpd','bowVc','wind','inGain',
                   'rvMix','rvTime','rvTone','rvPre'}
        # T1 adds the padded mallet's controls, sent for the Tank as off (pad 0)
        odd = [d for d in res.get('paramDiffers') or [] if not (d.split(':')[0] in REMOVED and d.endswith('→ undefined')) and d not in ('pad: undefined → 0', 'padRef: undefined → 129')]
        check('the same taps on the page before Stage I and on this one: the engine hears the same, the sound is bit-identical',
              out.returncode == 0 and res.get('same') and not odd,
              json.dumps({k: res.get(k) for k in ['same', 'maxDiff', 'peak', 'notes', 'paramDiffers', 'error'] if k in res}))
        k0, k1 = res.get('kinds', [{}, {}])
        check('...and the only messages the new page no longer sends are for removed features (extra mics, second mic, pickup type, exciter mode, specialization)',
              {k for k in k0 if k not in k1} <= {'xmic', 'mic2', 'pk', 'mode', 'spec'}, f'before {k0} · after {k1}')
    else:
        check('baseline page from git (the preview before Stage I)', False, f'{BASE_SHA[:8]} not in this clone; replay proof not run', critical=False)

    # ---------- 1. what is gone, what stays, Sustain ----------
    c, pg, errs = open_page(f'http://127.0.0.1:{PORT}/{PAGE}', record=True)
    ui = pg.evaluate("""() => ({ tabs: [...document.querySelectorAll('.tab')].map(t => t.textContent),
      knobs: [...document.querySelectorAll('.knob[data-k]')].map(k => k.dataset.k),
      gone: ['shapes','modes','specs','pickups','micslots','bow','micin','recbtn','reclink','vrecbtn','selftest','bench','scramble','lessons','lback',
             'page-fx','page-amp','page-mod','page-learn','undo','redo','xmremove'].filter(id => document.getElementById(id)),
      tools: [...document.querySelectorAll('#tools .tool')].map(t => t.textContent), shape: state.shape, masses: state.geo.P.length,
      first: document.querySelector('#page-body .knob .lab span').textContent, W: innerWidth, sw: document.documentElement.scrollWidth })""")
    KEEP = ['decay', 'size', 'ratio', 'loss', 'sub', 'voices', 'nl', 'tune', 'drive', 'hard', 'hit', 'angle', 'gain', 'mic', 'blend', 'bite', 'tone', 'mag']
    check('three tabs: Body, Strike, Mic', ui['tabs'] == ['Body', 'Strike', 'Mic'], str(ui['tabs']))
    check('removed controls are gone from the page', not ui['gone'] and ui['tools'] == ['reset view'], f"still present: {ui['gone']} · tools {ui['tools']}")
    check('the kept controls, and only those', sorted(ui['knobs']) == sorted(KEEP), f"{len(ui['knobs'])} knobs: {ui['knobs']}")
    check('the Tank is the instrument; Sustain is the first control on Body', ui['shape'] == 'Tank' and ui['masses'] == 58 and ui['first'] == 'Sustain',
          f"{ui['shape']}, {ui['masses']} masses, first control {ui['first']!r}")
    check('nothing wider than the phone', ui['sw'] <= ui['W'], f"{ui['sw']} px in {ui['W']} px")
    d0 = pg.evaluate('val.decay'); pg.evaluate('window.__msgs.length = 0')
    tap(pg, '.knob[data-k="decay"] .step[data-d="1"]'); pg.wait_for_timeout(200)
    d1 = pg.evaluate('val.decay'); sent = pg.evaluate("window.__msgs.filter(m => m.t === 'p' && m.k === 'decay').map(m => m.v)")
    check('Sustain + lengthens it and the engine is told', d1 > d0 and sent and abs(sent[-1] - d1) < 1e-9, f'{d0} → {d1} s; engine told {sent}')

    # ---------- 3. the circles ----------
    pg.evaluate('state.spin = false'); pg.wait_for_timeout(300)   # a still picture for the finger
    cdp = c.new_cdp_session(pg) if BROWSER == 'chromium' else None
    def touch_drag(x0, y0, x1, y1, n=12):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
        for k in range(1, n + 1):
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * k / n, 'y': y0 + (y1 - y0) * k / n}]}); pg.wait_for_timeout(16)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    def mouse_drag(x0, y0, x1, y1, n=12):
        pg.mouse.move(x0, y0); pg.mouse.down()
        for k in range(1, n + 1): pg.mouse.move(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n); pg.wait_for_timeout(16)
        pg.mouse.up()
    def move_test(kind, how):
        idx = 'state.hitIdx' if kind == 'strike' else 'state.micIdx'
        i0 = pg.evaluate(idx); other = pg.evaluate('state.micIdx' if kind == 'strike' else 'state.hitIdx')
        j = pg.evaluate(TARGET, [i0, other]); x0, y0 = pg.evaluate(XY, i0); x1, y1 = pg.evaluate(XY, j)
        pg.evaluate('window.__msgs.length = 0'); M0 = pg.evaluate('state.M.slice()')
        (touch_drag if how == 'touch' else mouse_drag)(x0, y0, x1, y1); pg.wait_for_timeout(350)
        got = pg.evaluate(idx); msgs = pg.evaluate("window.__msgs.map(m => m.t + (m.i !== undefined ? ':' + m.i : ''))")
        told = [m for m in msgs if m.startswith(('hit:' if kind == 'strike' else 'mic:'))]
        bad = []
        if got != j: bad.append(f'ended on #{got}, finger on #{j}')
        if not told or told[-1] != ('hit:' if kind == 'strike' else 'mic:') + str(j): bad.append(f'engine told {told[-3:]}')
        if 'note' not in msgs: bad.append('no audition after letting go')
        if pg.evaluate('state.M.slice()') != M0: bad.append('the view turned too')
        if pg.evaluate('state.micIdx' if kind == 'strike' else 'state.hitIdx') != other: bad.append('the other circle moved')
        check(f'press the {kind} circle and slide it ({how}): it follows the finger along the tank', not bad, '; '.join(bad) if bad else f'#{i0} → #{j}, engine told, auditioned')
    if cdp:
        move_test('mic', 'touch'); move_test('strike', 'touch')
    move_test('mic', 'mouse'); move_test('strike', 'mouse')
    # tap, then tap
    i0 = pg.evaluate('state.hitIdx'); j = pg.evaluate(TARGET, [i0, pg.evaluate('state.micIdx')])
    x0, y0 = pg.evaluate(XY, i0); pg.touchscreen.tap(x0, y0); pg.wait_for_timeout(250)
    carry = pg.evaluate('state.carry'); note = pg.evaluate("document.getElementById('nudgeMsg').textContent")
    x1, y1 = pg.evaluate(XY, j); pg.touchscreen.tap(x1, y1); pg.wait_for_timeout(300)
    check('tap the strike circle, then tap a ball: it moves there', carry == 'strike' and 'strike' in note and pg.evaluate('state.hitIdx') == j and pg.evaluate('state.carry') is None,
          f'picked up: {carry} ({note!r}); now on #{pg.evaluate("state.hitIdx")}, wanted #{j}')
    i0 = pg.evaluate('state.micIdx'); x0, y0 = pg.evaluate(XY, i0)
    pg.touchscreen.tap(x0, y0); pg.wait_for_timeout(200); pg.touchscreen.tap(x0, y0); pg.wait_for_timeout(200)
    check('tapping a picked-up circle again puts it back down', pg.evaluate('state.carry') is None and pg.evaluate('state.micIdx') == i0)
    # carrying one circle, a tap on the other still puts the carried one there (revision 2: it used to pick
    # up the other one, so a ball within reach of the other circle could not be reached by tap-then-tap)
    m0 = pg.evaluate('state.micIdx'); s0 = pg.evaluate('state.hitIdx'); xm, ym = pg.evaluate(XY, m0); xs, ys = pg.evaluate(XY, s0)
    pg.touchscreen.tap(xm, ym); pg.wait_for_timeout(200); c1 = pg.evaluate('state.carry')
    pg.touchscreen.tap(xs, ys); pg.wait_for_timeout(300); after = pg.evaluate('[state.micIdx, state.hitIdx, state.carry]')
    check('carrying the mic, a tap on the strike circle puts the mic there (it does not pick up the strike)', c1 == 'mic' and after == [s0, s0, None],
          f'picked up {c1}; mic #{m0}→#{after[0]}, strike #{s0}→#{after[1]}, still carrying {after[2]}')
    # a drag on empty space turns the view
    e = pg.evaluate("""(() => { const r = cv.getBoundingClientRect(), g = state.geo; let best = null, bd = -1;
      for (let x = 60; x < W - 60; x += 6) for (let y = 60; y < H - 70; y += 6) { let m = 1e9;
        for (let i = 0; i < g.P.length; i++) m = Math.min(m, Math.hypot(_px[i] - x, _py[i] - y)); if (m > bd) { bd = m; best = [x, y]; } }
      return [r.left + best[0], r.top + best[1]]; })()""")
    hm = pg.evaluate('[state.hitIdx, state.micIdx]'); M0 = pg.evaluate('state.M.slice()')
    (touch_drag if cdp else mouse_drag)(e[0], e[1], e[0] + 60, e[1] + 20)
    pg.wait_for_timeout(200)
    check('a drag on empty space turns the view and moves neither circle', pg.evaluate('state.M.slice()') != M0 and pg.evaluate('[state.hitIdx, state.micIdx]') == hm)
    # two circles on one ball: press, slide one away; press the same ball again, the other one comes
    pg.evaluate("() => { const i = state.hitIdx; state.micIdx = i; }"); pg.wait_for_timeout(200)
    s0 = pg.evaluate('state.hitIdx'); x0, y0 = pg.evaluate(XY, s0)
    j = pg.evaluate(TARGET, [s0]); x1, y1 = pg.evaluate(XY, j)
    mouse_drag(x0, y0, x1, y1); pg.wait_for_timeout(300)
    first = 'strike' if pg.evaluate('state.hitIdx') == j else ('mic' if pg.evaluate('state.micIdx') == j else None)
    k2 = pg.evaluate(TARGET, [s0, j]); x2, y2 = pg.evaluate(XY, k2)
    mouse_drag(x0, y0, x2, y2); pg.wait_for_timeout(300)
    second = 'strike' if pg.evaluate('state.hitIdx') == k2 else ('mic' if pg.evaluate('state.micIdx') == k2 else None)
    check('two circles on one ball: the first slide takes one, the next takes the other', first and second and first != second, f'{first}, then {second}')

    # ---------- 4. presets ----------
    # A preset stores mass positions to 4 decimals, so the Tank's curved rings come back very slightly moved:
    # its reference mode shifts by about 0.02 cents (measured). The bar is 0.5 cents, far under the ~5 cents
    # a listener can hear.
    tap(pg, '.tab[data-page=body]')
    before = pg.evaluate("() => ({ val: Object.assign({}, val), hit: state.hitIdx, mic: state.micIdx, fRef: state.info.fRef })")
    tap(pg, '#psave'); pg.wait_for_timeout(200); saved = pg.evaluate("document.getElementById('plist').value")
    tap(pg, '.knob[data-k="decay"] .step[data-d="-1"]'); tap(pg, '.knob[data-k="size"] .step[data-d="1"]'); pg.wait_for_timeout(1500)
    pg.select_option('#plist', saved); tap(pg, '#pload'); pg.wait_for_timeout(1500)
    after = pg.evaluate("() => ({ val: Object.assign({}, val), hit: state.hitIdx, mic: state.micIdx, fRef: state.info.fRef, msg: document.getElementById('msg').textContent })")
    diffk = [k for k in KEEP if abs(before['val'][k] - after['val'][k]) > 1e-9]
    check('save, change, load: the Tank comes back as saved', not diffk and before['hit'] == after['hit'] and before['mic'] == after['mic'] and abs(1200 * math.log2(after['fRef'] / before['fRef'])) < 0.5 and after['msg'] == 'Loaded ' + saved,
          f"{saved}: knobs differing {diffk}; strike #{before['hit']}→#{after['hit']}, mic #{before['mic']}→#{after['mic']}; reference mode {before['fRef']:.3f}→{after['fRef']:.3f} Hz ({1200 * math.log2(after['fRef'] / before['fRef']):+.3f} cents: a preset stores positions to 4 decimals); message {after['msg']!r}")
    old = pg.evaluate("""() => { const s = JSON.parse(JSON.stringify(snapshot()));
      Object.assign(s.val, { rvMix: 0.5, att: 0.6, wind: 0.5, fbAmt: 0.7, bow: 0.16, spDist: 0.9, fxCho: 0.5, width: 0.8, amp: 0.7 });
      s.pk = 2; s.mode = 3; s.spec = 2; s.mods = [{ d: 'tone', sh: 0, ty: 1, dn: 0, src: 0 }]; s.xm = [{ i: 3, g: 0.7, p: -0.6 }];
      const str = JSON.parse(JSON.stringify(s)); str.shape = 'String';
      const all = store.get(); all['zz old tank'] = s; all['zz old string'] = str; store.set(all); refreshList();
      return [...document.querySelectorAll('#plist option')].map(o => o.value); }""")
    check('the list shows Tank presets only (others stay stored for the main Resonator)', 'zz old tank' in old and 'zz old string' not in old, str(old))
    pg.evaluate('window.__msgs.length = 0'); pg.select_option('#plist', 'zz old tank'); tap(pg, '#pload'); pg.wait_for_timeout(1500)
    m = pg.evaluate("""() => { const p = {}; for (const x of window.__msgs) if (x.t === 'p') p[x.k] = x.v;
      return { p, kinds: [...new Set(window.__msgs.map(x => x.t))], pk: state.pk, mode: state.mode, spec: state.spec,
               specSent: window.__msgs.filter(x => x.t === 'spec').map(x => x.v), modeSent: window.__msgs.filter(x => x.t === 'mode').map(x => x.v), pkSent: window.__msgs.filter(x => x.t === 'pk').map(x => x.v) }; }""")
    # J1: nothing for a removed feature is sent at all, and the page holds no value for one
    bad = [f'{k} sent' for k in ['rvMix', 'att', 'wind', 'fbAmt', 'spDist', 'fxCho', 'width', 'amp', 'bow', 'pkType'] if k in m['p']]
    bad += [f'{x} sent' for x in ['mod', 'xmic', 'mic2', 'pk', 'mode', 'spec'] if x in m['kinds']]
    held = pg.evaluate("() => ['rvMix','att','wind','fbAmt','spDist','fxCho','width','amp'].filter(k => k in val)")
    bad += [f'page holds {k}' for k in held]
    check('an old preset cannot switch a removed feature back on (reverb, OMEF, wind, feedback, bow, distance, modulators, extra mics, exciters)', not bad, '; '.join(bad) if bad else 'none of them is sent or held')
    code = pg.evaluate("JSON.stringify(Object.assign(JSON.parse(JSON.stringify(snapshot())), { shape: 'Drum' }))")
    tap(pg, '#ppaste'); pg.fill('#pcode', code); tap(pg, '#ppaste'); pg.wait_for_timeout(300)
    check('pasting code for another shape is refused, and says why', 'Drum' in pg.evaluate("document.getElementById('msg').textContent") and pg.evaluate('state.shape') == 'Tank',
          pg.evaluate("document.getElementById('msg').textContent"))

    # ---------- it still plays; the report ----------
    pg.evaluate("() => play(0, 0.8)"); pk = pg.evaluate(LISTEN, 900)
    check('it still plays', pk > 0.05, f'peak {pk:.3f}')
    pg.evaluate('renderDiag()'); rep = pg.evaluate('diagEl.textContent')
    check('Copy report carries the touch counters', 'body touches' in rep, [l for l in rep.splitlines() if 'body touches' in l][:1])
    check('no script errors', not errs, str(errs[:3]))
    c.close(); b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage I browser checks pass')
sys.exit(1 if failed else 0)
