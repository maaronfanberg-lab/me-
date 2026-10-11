# Stage 4 browser checks: extra mics through the Mic tab and the mic tool, per-mic level/pan, remove,
# renumbering after delete, undo, pinning a mic's ball, presets, and that a net-zero edit sends the
# engine exactly the original body (ratchet: no body-level flag may change the sound by itself).
# Run from the repo root:
#   python3 qa-resonator/stage4_browser.py [repo_root]
import sys, os, json, threading, functools, http.server
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

LR = """async()=>{ if(!window._sp){ window._sp=ctx.createChannelSplitter(2); (master||node).connect(window._sp); window._L=ctx.createAnalyser(); window._R=ctx.createAnalyser(); _L.fftSize=_R.fftSize=2048; _sp.connect(_L,0); _sp.connect(_R,1); }
  const a=new Float32Array(2048), b=new Float32Array(2048); let pl=0, pr=0, d=0;
  document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
  for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,25)); _L.getFloatTimeDomainData(a); _R.getFloatTimeDomainData(b); for(let k=0;k<2048;k++){ pl=Math.max(pl,Math.abs(a[k])); pr=Math.max(pr,Math.abs(b[k])); d=Math.max(d,Math.abs(a[k]-b[k])); } }
  return {L:+pl.toFixed(3), R:+pr.toFixed(3), diff:+d.toFixed(3)}; }"""
# every struct / xmic message the page sends, as JSON (typed arrays as plain arrays)
HOOK = """window._msgs=[]; { const r=node.port.postMessage.bind(node.port);
  node.port.postMessage=(m,tr)=>{ if(m&&(m.t==='struct'||m.t==='xmic')) window._msgs.push(JSON.stringify(m,(k,v)=>ArrayBuffer.isView(v)?Array.from(v):v)); return r(m,tr); }; }"""

def tap_mass(pg, i):
    xy = pg.evaluate(f"(()=>{{const r=cv.getBoundingClientRect();return [r.left+_px[{i}],r.top+_py[{i}]];}})()")
    pg.mouse.click(xy[0], xy[1])
def msgs(pg): return [json.loads(m) for m in pg.evaluate("window._msgs")]
def last_xmic(ms, k):
    xs = [m for m in ms if m['t'] == 'xmic' and m['k'] == k]
    return xs[-1] if xs else None

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    c = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(300)
    pg.tap('#start'); pg.wait_for_timeout(1800)
    pg.evaluate(HOOK)
    pg.evaluate("rebuild()"); pg.wait_for_timeout(300)
    s_factory = [m for m in msgs(pg) if m['t'] == 'struct'][-1]   # the untouched body, before any edit
    pg.tap('.tab[data-page=mic]'); pg.wait_for_timeout(150)
    slots = pg.evaluate("[...document.querySelectorAll('#micslots .chip')].map(c=>c.textContent)")
    check('Mic tab offers Mic 1–4', slots == ['Mic 1', 'Mic 2 (off)', 'Mic 3 (off)', 'Mic 4 (off)'], str(slots))
    mono = pg.evaluate(LR); pg.wait_for_timeout(800)

    # place Mic 2 with the mic tool, pan it hard left with taps
    pg.tap('#micslots .chip:nth-child(2)'); pg.wait_for_timeout(100)
    hint = pg.inner_text('#xmhint')
    pg.tap('.tool[data-tool=mic]'); pg.wait_for_timeout(100)
    j = pg.evaluate("state.free[state.free.length-2]")
    tap_mass(pg, j); pg.wait_for_timeout(200)
    placed = pg.evaluate("state.xm[0].i"); main_mic = pg.evaluate("state.micIdx")
    for _ in range(25): pg.tap('.knob[data-k=xPan] .step[data-d="-1"]')
    pan_lab = pg.inner_text('.knob[data-k=xPan] .lab b')
    left = pg.evaluate(LR); pg.wait_for_timeout(800)
    check('Mic 2 placed with the mic tool (main mic unchanged)', placed == j and main_mic != j and 'tap a ball' in hint.lower(), f"Mic 2 on #{placed}, main mic #{main_mic}")
    check('Mic 2 panned hard left makes the left channel differ', pan_lab.startswith('L') and mono['diff'] < 0.01 and left['diff'] > 0.02, f"pan {pan_lab}: L {left['L']} R {left['R']} (mono before: diff {mono['diff']})")
    # its level to zero → contribution gone
    pg.tap('.knob[data-k=xLevel] .lab'); pg.wait_for_timeout(100)
    for _ in range(40): pg.tap('.knob[data-k=xLevel] .step[data-d="-1"]')
    lev = pg.inner_text('.knob[data-k=xLevel] .lab b'); zero = pg.evaluate(LR); pg.wait_for_timeout(800)
    check('Mic 2 level at 0% removes its contribution', lev == '0%' and zero['diff'] < 0.01, f"level {lev}: diff {zero['diff']}")
    for _ in range(22): pg.tap('.knob[data-k=xLevel] .step[data-d="1"]')

    # Mic 3: separate level/pan; switching back shows Mic 2's own settings
    pg.tap('#micslots .chip:nth-child(3)'); pg.wait_for_timeout(100)
    m3 = pg.inner_text('.knob[data-k=xPan] .lab b')
    pg.tap('#micslots .chip:nth-child(2)'); pg.wait_for_timeout(100)
    m2 = pg.inner_text('.knob[data-k=xPan] .lab b')
    check('each extra mic keeps its own level and pan', m3 != m2 and m2.startswith('L'), f"Mic 3 pan {m3}, Mic 2 pan {m2}")

    # delete a mass below Mic 2's index: Mic 2 follows the renumbering; undo puts it back
    pg.tap('.tool[data-tool=del]'); pg.wait_for_timeout(100)
    k = pg.evaluate("state.free[0]")
    before_i = pg.evaluate("state.xm[0].i"); tap_mass(pg, k); pg.wait_for_timeout(700)
    after_i = pg.evaluate("state.xm[0].i")
    check('Mic 2 follows the renumbering after a delete', after_i == before_i - 1, f"#{before_i} → #{after_i}")
    pg.tap('#undo'); pg.wait_for_timeout(700)
    undo_i = pg.evaluate("state.xm[0].i"); sent = last_xmic(msgs(pg), 0)
    check('undo puts Mic 2 back on its ball (and tells the engine)', undo_i == before_i and sent and sent['i'] == before_i, f"after undo: page #{undo_i}, engine told #{sent and sent['i']}")

    # pin Mic 2's ball: Mic 2 goes off in the page and the engine; undo brings it back
    pg.tap('.tool[data-tool=pin]'); pg.wait_for_timeout(100)
    tap_mass(pg, before_i); pg.wait_for_timeout(700)
    pin_i = pg.evaluate("state.xm[0].i"); chip = pg.evaluate("document.querySelector('#micslots .chip:nth-child(2)').textContent"); sent = last_xmic(msgs(pg), 0)
    check('pinning Mic 2\'s ball switches Mic 2 off (page and engine agree)', pin_i == -1 and chip == 'Mic 2 (off)' and sent and sent['i'] == -1, f"page #{pin_i}, chip {chip!r}, engine told #{sent and sent['i']}")
    pg.tap('#undo'); pg.wait_for_timeout(700)
    back_i = pg.evaluate("state.xm[0].i"); sent = last_xmic(msgs(pg), 0)
    check('undo of the pin brings Mic 2 back', back_i == before_i and sent and sent['i'] == before_i, f"page #{back_i}, engine told #{sent and sent['i']}")

    # ratchet: edits that change nothing physical (delete+undo, pin+undo above, pin+unpin here) must send
    # the engine exactly the untouched body — no flag may change the sound by itself
    busy = pg.evaluate("[state.micIdx,state.hitIdx,...state.xm.map(x=>x.i)]")
    q = pg.evaluate(f"state.free.find(i=>!{json.dumps(busy)}.includes(i))")
    tap_mass(pg, q); pg.wait_for_timeout(500); tap_mass(pg, q); pg.wait_for_timeout(500)
    s2 = [m for m in msgs(pg) if m['t'] == 'struct'][-1]
    pinned_then = [m for m in msgs(pg) if m['t'] == 'struct'][-2]
    diff = sorted(k for k in set(s2) | set(s_factory) if s2.get(k) != s_factory.get(k))
    check('net-zero edits send the engine exactly the untouched body', s2 == s_factory and pinned_then != s_factory,
          f"keys {sorted(s_factory.keys())}" + (f"; differs in {diff}" if diff else '; identical'))
    pg.tap('.tool[data-tool=orbit]')

    # presets keep the extra mics
    rt = pg.evaluate("""(()=>{ const s=JSON.parse(JSON.stringify(snapshot())); const want=JSON.stringify(state.xm); buildShape(true); const cleared=state.xm.every(x=>x.i<0); restore(s); return {cleared, back: JSON.stringify(state.xm)===want}; })()""")
    check('shape change clears extra mics; a preset brings them back', rt['cleared'] and rt['back'], str(rt))

    # remove
    pg.tap('#micslots .chip:nth-child(2)'); pg.tap('#xmremove'); pg.wait_for_timeout(200)
    rem = pg.evaluate("state.xm[0].i"); lab2 = pg.evaluate("document.querySelector('#micslots .chip:nth-child(2)').textContent")
    check('Remove this mic switches it off', rem == -1 and lab2 == 'Mic 2 (off)', f"#{rem}, chip {lab2!r}")
    check('no page errors', not errs, str(errs[:3]))
    b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage 4 browser checks pass')
sys.exit(1 if failed else 0)
