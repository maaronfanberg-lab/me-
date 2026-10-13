# Stage U1 — scrolling over the controls must not move them. Browser checks with a finger.
#   python3 qa-resonator/u1_browser.py [repo_root] [--browser=webkit]
# Chromium (a 390 px touch phone): touches go in through the DevTools protocol, so the browser scrolls the panel
# itself, exactly as it would under a finger.
#  1. Every control on every tab: a vertical swipe (both ways) starting on its bar, on its - and on its + changes no
#     value anywhere, and the panel scrolls. A mostly-vertical diagonal swipe on a bar too. No skip list.
#  2. What must still work: a sideways drag on a bar follows the finger; a tap on a bar sets the value where it
#     landed; a tap on + / - is exactly one step; a held + repeats; a double tap on a label resets it; two quick
#     swipes over a label do not; the mouse still drags.
#  3. The tower's chips and Size keep working; no script errors.
# WebKit: Playwright has no touch-drag there, so it runs the taps (2) and reports the swipes as Chromium-only.
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

VALS = "() => JSON.stringify(val)"
BOX = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }"""

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True, 'device_scale_factor': 2}
    c = b.new_context(**dev); pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400); pg.tap('#start'); pg.wait_for_timeout(2500)
    cdp = c.new_cdp_session(pg) if BROWSER == 'chromium' else None

    def touch_path(pts, dt=16, hold_end=0, end_wait=120):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': pts[0][0], 'y': pts[0][1]}]})
        for x, y in pts[1:]:
            pg.wait_for_timeout(dt); cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y}]})
        if hold_end: pg.wait_for_timeout(hold_end)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); pg.wait_for_timeout(end_wait)
    def swipe(x, y, dx, dy, n=12, dt=16, end_wait=120):
        touch_path([(x + dx * k / n, y + dy * k / n) for k in range(n + 1)], dt=dt, end_wait=end_wait)
    def tab(name):
        pg.tap(f'.tab[data-page="{name}"]'); pg.wait_for_timeout(150)
    def scroll_to(el_sel):   # put a control in the middle of the panel without touching it
        pg.evaluate("s => document.querySelector(s).scrollIntoView({block:'center'})", el_sel); pg.wait_for_timeout(80)
    panel_top = lambda: pg.evaluate("document.getElementById('panel').scrollTop")
    panel_max = lambda: pg.evaluate("(() => { const p = document.getElementById('panel'); return p.scrollHeight - p.clientHeight; })()")
    def panel_rect(): return pg.evaluate(BOX, '#panel')

    # ---------- 1. swipes over every control ----------
    if cdp:
        changed, still, tried, scrolled_n = [], [], 0, [0]
        for t in ['body', 'strike', 'mic']:
            tab(t)
            if t == 'body': pg.evaluate("setShape('Tower')"); pg.wait_for_timeout(2500); tab('body')   # the tower's page has the most rows
            if t == 'strike': pg.evaluate("setShape('Tank')"); pg.wait_for_timeout(2500); tab('strike')  # Mallet knob visible
            knobs = pg.evaluate(f"[...document.querySelectorAll('#page-{t} .knob[data-k]')].filter(k => !k.hidden && k.offsetParent).map(k => k.dataset.k)")
            for k in knobs:
                for part, sel in [('bar', f'#page-{t} .knob[data-k="{k}"] .bar'), ('−', f'#page-{t} .knob[data-k="{k}"] .step[data-d="-1"]'), ('+', f'#page-{t} .knob[data-k="{k}"] .step[data-d="1"]')]:
                    for direction in (-1, 1):
                        scroll_to(sel); x, y, w, h = pg.evaluate(BOX, sel)
                        cx, cy = x + w * (0.37 if part == 'bar' else 0.5), y + h / 2
                        pr = panel_rect(); room = pr[1] + pr[3] - cy - 10 if direction > 0 else cy - pr[1] - 10
                        dist = max(40, min(150, room))
                        before, t0 = pg.evaluate(VALS), panel_top()
                        swipe(cx, cy, 0, direction * dist); pg.wait_for_timeout(250)
                        after, t1 = pg.evaluate(VALS), panel_top(); tried += 1
                        if after != before:
                            a, bb = json.loads(after), json.loads(before)
                            changed.append(f"{t}/{k}/{part}/{'down' if direction > 0 else 'up'}: " + ', '.join(f'{q} {bb[q]}→{a[q]}' for q in a if a[q] != bb[q]))
                        # a finger moving up scrolls the panel down: only judged where there was room to go
                        room_left = (panel_max() - t0) if direction < 0 else t0
                        if room_left < 30: tried_scroll = False
                        else: tried_scroll = True; scrolled_n[0] += 1
                        if tried_scroll and abs(t1 - t0) < 15: still.append(f'{t}/{k}/{part}/{"down" if direction > 0 else "up"} ({t0}→{t1})')
        check('1a. a vertical swipe starting on any slider, − or + (every control, every tab, both ways) changes nothing', not changed, f'{tried} swipes; ' + ('; '.join(changed[:8]) if changed else 'no value moved'))
        check('1b. ...and the panel scrolls under the finger (wherever it had room to)', not still and scrolled_n[0] >= tried * 0.5, f'{scrolled_n[0] - len(still)}/{scrolled_n[0]} scrolled ({tried - scrolled_n[0]} swipes started with the panel already at its end that way)' + (f'; did not: {", ".join(still[:6])}' if still else ''))
        tab('body'); scroll_to('#page-body .knob[data-k="ratio"] .bar'); x, y, w, h = pg.evaluate(BOX, '#page-body .knob[data-k="ratio"] .bar')
        before = pg.evaluate(VALS); swipe(x + w * 0.4, y + h / 2, 30, -90); pg.wait_for_timeout(200)
        check('1c. a mostly-vertical diagonal swipe on a bar changes nothing', pg.evaluate(VALS) == before)
        before = pg.evaluate(VALS)
        for _ in range(3): swipe(x + w * 0.2, y + h / 2, 0, -60, n=4)   # quick flicks, like a hurried thumb
        check('1d. quick short flicks starting on a bar change nothing', pg.evaluate(VALS) == before)
    else:
        print('NOTE 1. swipes: Chromium only (Playwright has no touch-drag in WebKit); a real iPhone is the final check')

    # ---------- 2. what must still work ----------
    tab('body'); pg.evaluate("setShape('Tank')"); pg.wait_for_timeout(2500); tab('body')
    K = pg.evaluate("(() => { const k = KNOBS.ratio; return [k.min, k.max, k.step, k.val]; })()")
    sel = '#page-body .knob[data-k="ratio"] .bar'
    scroll_to(sel); x, y, w, h = pg.evaluate(BOX, sel)
    if cdp:
        touch_path([(x + w * 0.2 + w * 0.6 * k / 14, y + h / 2 + (k % 3) - 1) for k in range(15)])
        v = pg.evaluate('val.ratio'); want = K[0] + 0.8 * (K[1] - K[0])
        check('2a. a sideways drag on a bar follows the finger (20% → 80%)', abs(v - want) <= 0.04 * (K[1] - K[0]), f'Stiffness {v} (finger at {want:.2f})')
    pg.touchscreen.tap(x + w * 0.25, y + h / 2); pg.wait_for_timeout(200)
    v = pg.evaluate('val.ratio'); want = K[0] + 0.25 * (K[1] - K[0])
    check('2b. a tap on a bar sets the value where it landed', abs(v - want) <= 0.03 * (K[1] - K[0]), f'Stiffness {v} (tapped at {want:.2f})')
    v0 = pg.evaluate('val.ratio'); scroll_to('#page-body .knob[data-k="ratio"] .step[data-d="1"]')
    pg.tap('#page-body .knob[data-k="ratio"] .step[data-d="1"]'); pg.wait_for_timeout(600); v1 = pg.evaluate('val.ratio')
    pg.tap('#page-body .knob[data-k="ratio"] .step[data-d="-1"]'); pg.wait_for_timeout(600); v2 = pg.evaluate('val.ratio')
    inc = max(K[2], round((K[1] - K[0]) / 32 / K[2]) * K[2])
    check('2c. a tap on + is exactly one step, a tap on − exactly one back', abs(v1 - v0 - inc) < 1e-6 and abs(v2 - v0) < 1e-6, f'{v0} → {v1} → {v2} (step {inc})')
    if cdp:
        bx, by, bw, bh = pg.evaluate(BOX, '#page-body .knob[data-k="ratio"] .step[data-d="-1"]')
        v0 = pg.evaluate('val.ratio'); touch_path([(bx + bw / 2, by + bh / 2)], hold_end=1500); v1 = pg.evaluate('val.ratio')
        check('2d. holding − still repeats', (v0 - v1) / inc >= 5, f'{v0} → {v1} ({(v0 - v1) / inc:.0f} steps in 1.5 s)')
        lab = '#page-body .knob[data-k="ratio"] .lab'; lx, ly, lw, lh = pg.evaluate(BOX, lab)
        v0 = pg.evaluate('val.ratio')
        swipe(lx + 40, ly + lh / 2, 0, -40, n=3, dt=10, end_wait=30); swipe(lx + 40, ly + lh / 2, 0, -40, n=3, dt=10, end_wait=150)   # second flick within ~100 ms
        check('2e. two quick swipes over a label do not reset it', pg.evaluate('val.ratio') == v0, f'Stiffness {v0} → {pg.evaluate("val.ratio")}')
    scroll_to('#page-body .knob[data-k="ratio"] .lab'); lx, ly, lw, lh = pg.evaluate(BOX, '#page-body .knob[data-k="ratio"] .lab')
    pg.touchscreen.tap(lx + 40, ly + lh / 2); pg.wait_for_timeout(120); pg.touchscreen.tap(lx + 40, ly + lh / 2); pg.wait_for_timeout(250)
    check('2f. a double tap on a label still resets it', pg.evaluate('val.ratio') == K[3], f'Stiffness {pg.evaluate("val.ratio")} (default {K[3]})')
    scroll_to(sel); x, y, w, h = pg.evaluate(BOX, sel)
    pg.mouse.move(x + w * 0.1, y + h / 2); pg.mouse.down(); pg.mouse.move(x + w * 0.6, y + h / 2, steps=8); pg.mouse.up(); pg.wait_for_timeout(150)
    v = pg.evaluate('val.ratio'); want = K[0] + 0.6 * (K[1] - K[0])
    check('2g. the mouse still drags a bar', abs(v - want) <= 0.04 * (K[1] - K[0]), f'Stiffness {v} (pointer at {want:.2f})')

    # ---------- 3. ----------
    tab('body'); scroll_to('[data-shape="Tower"]'); pg.tap('[data-shape="Tower"]'); pg.wait_for_timeout(2500)
    n0 = pg.evaluate('state.geo.P.length'); scroll_to('#page-body .knob[data-k="size"] .step[data-d="-1"]')
    for _ in range(40):
        if pg.evaluate('state.geo.P.length') != n0: break
        pg.tap('#page-body .knob[data-k="size"] .step[data-d="-1"]'); pg.wait_for_timeout(60)
    check('3a. the Water tower chip and Size − work by taps', pg.evaluate('state.shape') == 'Tower' and pg.evaluate('state.geo.P.length') < n0, f"{pg.evaluate('state.shape')}, {n0} → {pg.evaluate('state.geo.P.length')} masses")
    w2 = pg.evaluate('() => [innerWidth, document.documentElement.scrollWidth]')
    check('3b. nothing wider than the phone; no script errors', w2[1] <= w2[0] and not errs, f'{w2[1]} px in {w2[0]} px; errors {errs[:3]}')
    c.close(); b.close()
print(f'\n{failed} check(s) FAILED' if failed else '\nall U1 browser checks pass')
sys.exit(1 if failed else 0)
