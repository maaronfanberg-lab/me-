# F4 browser test: tap path for orbit and move, on a phone-sized touch viewport.
import http.server, threading, functools, sys, json
from playwright.sync_api import sync_playwright
ROOT = sys.argv[1]
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
res, errs = {}, []
with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto('http://127.0.0.1:8765/apps/resonator.html'); pg.wait_for_timeout(500)
    pg.tap('#start'); pg.wait_for_timeout(2500)
    E = pg.evaluate
    res['running'] = E('state.running')
    res['nudge visible on orbit'] = E("!document.getElementById('nudge').hidden")
    M0 = E('state.M.slice()'); pg.tap('#nudge [aria-label=right]'); pg.wait_for_timeout(100)
    res['orbit right turns view'] = E('state.M.slice()') != M0
    res['spin stopped'] = E('state.spin') is False
    M1 = E('state.M.slice()'); pg.tap('#nudge [aria-label=up]'); pg.wait_for_timeout(100)
    res['orbit up turns view'] = E('state.M.slice()') != M1
    pg.tap('.tool[data-tool=move]'); pg.wait_for_timeout(150)
    res['label says move'] = E("document.getElementById('nudgeLab').textContent") == 'move'
    pg.tap('#nudge [aria-label=up]'); pg.wait_for_timeout(100)
    res['no-selection hint'] = E("document.getElementById('nudgeMsg').textContent")
    # tap a free mass on the canvas where it is drawn
    i, x, y = E("(()=>{const r=cv.getBoundingClientRect();const i=state.free[Math.floor(state.free.length/2)];return [i,r.left+_px[i],r.top+_py[i]];})()")
    pg.touchscreen.tap(x, y); pg.wait_for_timeout(150)
    sel = E('state.sel'); res['tap selects a mass'] = sel >= 0
    P0 = E(f'state.geo.P[{sel}].slice()')
    for d in ['right', 'right', 'up']: pg.tap(f'#nudge [aria-label={d}]'); pg.wait_for_timeout(80)
    P1 = E(f'state.geo.P[{sel}].slice()')
    res['mass moved'] = P1 != P0
    res['moved by'] = round(sum((a - b) ** 2 for a, b in zip(P0, P1)) ** 0.5, 4)
    res['undo enabled'] = E("!document.getElementById('undo').disabled")
    res['undo steps used'] = 0
    for _ in range(3):
        pg.tap('#undo'); pg.wait_for_timeout(120); res['undo steps used'] += 1
    P2 = E(f'state.geo.P[{sel}].slice()')
    res['undo restores'] = [round(v, 6) for v in P2] == [round(v, 6) for v in P0]
    # hold-to-repeat: press for 1.2 s, expect many steps
    pg.tap(f'#nudge [aria-label=left]'); pg.wait_for_timeout(50)
    Pa = E(f'state.geo.P[{sel}].slice()')
    box = pg.locator('#nudge [aria-label=left]').bounding_box()
    pg.mouse.move(box['x'] + 20, box['y'] + 20); pg.mouse.down(); pg.wait_for_timeout(1200); pg.mouse.up()
    Pb = E(f'state.geo.P[{sel}].slice()')
    res['hold repeats (distance)'] = round(sum((a - b) ** 2 for a, b in zip(Pa, Pb)) ** 0.5, 4)
    pg.tap('.tool[data-tool=strike]'); pg.wait_for_timeout(100)
    res['hidden on strike'] = E("document.getElementById('nudge').hidden")
    pg.tap('.tool[data-tool=orbit]'); pg.wait_for_timeout(100)
    # overlap check against the level readout and tool row
    res['overlaps'] = E("""(()=>{const n=document.getElementById('nudge').getBoundingClientRect();
      const hit=id=>{const r=document.getElementById(id).getBoundingClientRect();return !(r.right<n.left||r.left>n.right||r.bottom<n.top||r.top>n.bottom);};
      const tools=[...document.querySelectorAll('#tools .tool')].some(t=>{const r=t.getBoundingClientRect();return !(r.right<n.left||r.left>n.right||r.bottom<n.top||r.top>n.bottom);});
      return {level:hit('level'),brand:hit('brand'),tools};})()""")
    res['stage height'] = E("document.getElementById('stage').getBoundingClientRect().height")
    pg.screenshot(path=sys.argv[2])
    b.close()
srv.shutdown()
print(json.dumps(res, indent=1)); print('ERRORS:', errs)
