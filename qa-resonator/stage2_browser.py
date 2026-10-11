# Stage 2 browser checks: free building (add / delete), undo across shape changes, presets,
# second-mic guard. Run from the repo root: python3 qa-resonator/stage2_browser.py [repo_root]
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

PEAK_JS = """async()=>{ if(!window._an){window._an=ctx.createAnalyser();window._an.fftSize=2048;(master||node).connect(window._an);}
  const an=window._an,buf=new Float32Array(2048);let pk=0,bad=0;
  document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
  for(let i=0;i<60;i++){await new Promise(r=>setTimeout(r,25));an.getFloatTimeDomainData(buf);for(const v of buf){ if(!isFinite(v)) bad++; else pk=Math.max(pk,Math.abs(v)); }}
  return {pk:+pk.toFixed(3), bad}; }"""
# the canvas point farthest from every drawn mass (avoiding the readout, the nudge pad and the tool row)
EMPTY_JS = """(()=>{ const r=cv.getBoundingClientRect(), g=state.geo; let best=null, bd=-1;
  for(let x=70;x<W-70;x+=6) for(let y=110;y<H-120;y+=6){ let m=1e9; for(let i=0;i<g.P.length;i++){ const dx=_px[i]-x, dy=_py[i]-y; m=Math.min(m,dx*dx+dy*dy); }
    if(m>bd){ bd=m; best=[x,y]; } } return {x:r.left+best[0], y:r.top+best[1], lx:best[0], ly:best[1], dist:Math.sqrt(bd)}; })()"""
COUNTS = "({m:state.geo.P.length, s:state.geo.S.length, hit:state.hitIdx, mic:state.micIdx, free:state.free.slice(), shape:state.shape, n:state.n, structs:TUNER.stats.structs, msg:document.getElementById('nudgeMsg').textContent})"

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    c = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(300)
    pg.tap('#start'); pg.wait_for_timeout(1800)
    base = pg.evaluate(COUNTS)

    # --- add: tap empty space ---
    pg.tap('.tool[data-tool=add]'); pg.wait_for_timeout(150)
    e = pg.evaluate(EMPTY_JS)
    pg.mouse.click(e['x'], e['y']); pg.wait_for_timeout(700)
    a1 = pg.evaluate(COUNTS)
    newpos = pg.evaluate("(()=>{const i=state.geo.P.length-1;return [_px[i],_py[i]];})()")
    off = ((newpos[0] - e['lx']) ** 2 + (newpos[1] - e['ly']) ** 2) ** 0.5
    linked = pg.evaluate("(()=>{const i=state.geo.P.length-1;return state.geo.S.some(s=>s[0]===i||s[1]===i);})()")
    snd = pg.evaluate(PEAK_JS)
    check('add: tap empty space adds a wired mass under the finger',
          a1['m'] == base['m'] + 1 and a1['s'] == base['s'] + 1 and linked and off < 12 and a1['structs'] > base['structs'],
          f"masses {base['m']}→{a1['m']}, springs {base['s']}→{a1['s']}, lands {off:.1f} px from the tap, retuned in background ({a1['structs']} bodies)")
    check('add: still plays after adding', snd['pk'] > 0.05 and snd['bad'] == 0, f"peak {snd['pk']}")
    # tap right on an existing mass: refused
    xy = pg.evaluate("(()=>{const r=cv.getBoundingClientRect();const i=state.free[0];return [r.left+_px[i],r.top+_py[i]];})()")
    pg.mouse.click(xy[0], xy[1]); pg.wait_for_timeout(300)
    a2 = pg.evaluate(COUNTS)
    check('add: a tap on an existing mass adds nothing and says why', a2['m'] == a1['m'] and a2['msg'] == 'tap empty space', f"message: {a2['msg']!r}")
    # --- undo removes it ---
    pg.tap('#undo'); pg.wait_for_timeout(600)
    u1 = pg.evaluate(COUNTS)
    check('undo removes the added mass', u1['m'] == base['m'] and u1['s'] == base['s'], f"masses {u1['m']}")

    # --- delete the strike mass: strike moves to the nearest remaining free mass ---
    pg.tap('.tool[data-tool=del]'); pg.wait_for_timeout(150)
    hit = u1['hit']
    xy = pg.evaluate(f"(()=>{{const r=cv.getBoundingClientRect();return [r.left+_px[{hit}],r.top+_py[{hit}]];}})()")
    pg.mouse.click(xy[0], xy[1]); pg.wait_for_timeout(700)
    d1 = pg.evaluate(COUNTS)
    snd = pg.evaluate(PEAK_JS)
    ok_ptrs = d1['hit'] in d1['free'] and d1['mic'] in d1['free']
    check('delete: removes the mass and its springs; strike and mic stay on real masses',
          d1['m'] == u1['m'] - 1 and d1['s'] < u1['s'] and ok_ptrs, f"masses {u1['m']}→{d1['m']}, springs {u1['s']}→{d1['s']}, strike #{d1['hit']}, mic #{d1['mic']}")
    check('delete: still plays after deleting', snd['pk'] > 0.05 and snd['bad'] == 0, f"peak {snd['pk']}")

    # --- second mic: delete its mass with Stereo up; output must stay finite and stereo ---
    pg.evaluate("val.width=1;syncKnob('width');send('width')")
    j = pg.evaluate("state.micIdx2")
    xy = pg.evaluate(f"(()=>{{const r=cv.getBoundingClientRect();return [r.left+_px[{j}],r.top+_py[{j}]];}})()")
    pg.mouse.click(xy[0], xy[1]); pg.wait_for_timeout(700)
    st = pg.evaluate("""async()=>{ const sp=ctx.createChannelSplitter(2); (master||node).connect(sp); const L=ctx.createAnalyser(), R=ctx.createAnalyser(); L.fftSize=R.fftSize=2048; sp.connect(L,0); sp.connect(R,1);
      const a=new Float32Array(2048), b2=new Float32Array(2048); let diff=0, pk=0, pr=0, bad=0;
      document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
      for(let i=0;i<40;i++){ await new Promise(r=>setTimeout(r,25)); L.getFloatTimeDomainData(a); R.getFloatTimeDomainData(b2);
        for(let k=0;k<2048;k++){ if(!isFinite(a[k])||!isFinite(b2[k])) bad++; else { diff=Math.max(diff,Math.abs(a[k]-b2[k])); pk=Math.max(pk,Math.abs(a[k])); pr=Math.max(pr,Math.abs(b2[k])); } } }
      const piece=pieceOf(state.geo,state.hitIdx);
      return {pk:+pk.toFixed(3), right:+pr.toFixed(3), diff:+diff.toFixed(3), bad, mic2:state.micIdx2, free:state.free.includes(state.micIdx2), onPiece:piece.has(state.micIdx2)&&piece.has(state.micIdx)}; }""")
    check('second mic re-placed on the struck piece after its mass is deleted (Stereo up)', st['bad'] == 0 and st['pk'] > 0.05 and st['right'] > 0.05 and st['free'] and st['onPiece'],
          f"left {st['pk']}, right {st['right']} (the second mic alone), second mic #{st['mic2']}, both mics on the struck piece: {st['onPiece']}")
    pg.evaluate("val.width=0;syncKnob('width');send('width')")

    # --- limit ---
    lim = pg.evaluate("""(()=>{ const g=state.geo; const n0=g.P.length; while(g.P.length<MAX_MASSES){ const p=g.P[g.P.length-1]; g.P.push([p[0]*0.9,p[1]*0.9+0.01,p[2]]); g.F=Uint8Array.from([...g.F,0]); g.S.push([g.P.length-2,g.P.length-1]); }
      const r=cv.getBoundingClientRect(); addMassAt(r.left+5, r.top+5); const m=document.getElementById('nudgeMsg').textContent; const n1=g.P.length; return {n0, n1, m}; })()""")
    check('limit: adding past the limit is refused with a message', lim['n1'] == 100 and 'Limit' in lim['m'], f"{lim}")
    pg.tap('#undo'); pg.wait_for_timeout(300)   # (the limit test edited geometry directly; undo restores the last real edit)

    # --- undo across a Size change: a hand-built shape can't vanish ---
    pg.tap('.tool[data-tool=add]'); e = pg.evaluate(EMPTY_JS); pg.mouse.click(e['x'], e['y']); pg.wait_for_timeout(700)
    built = pg.evaluate(COUNTS)
    pg.tap('.tab[data-page=body]'); pg.tap('.knob[data-k=size] .step[data-d="1"]'); pg.wait_for_timeout(700)
    after_size = pg.evaluate(COUNTS)
    pg.tap('#undo'); pg.wait_for_timeout(700)
    back = pg.evaluate(COUNTS)
    check('undo restores a hand-built body after a Size change', after_size['m'] != built['m'] and back['m'] == built['m'] and back['s'] == built['s'] and back['n'] == built['n'],
          f"built {built['m']} masses → Size changed to {after_size['m']} → undo back to {back['m']}")
    # and across a shape change
    pg.click('#shapes .chip:text-is("Drum")'); pg.wait_for_timeout(700)
    pg.tap('#undo'); pg.wait_for_timeout(700)
    back2 = pg.evaluate(COUNTS)
    pressed = pg.evaluate("[...document.querySelectorAll('#shapes .chip')].filter(c=>c.getAttribute('aria-pressed')==='true').map(c=>c.textContent)")
    check('undo restores it after a shape change too, with the right shape shown', back2['m'] == built['m'] and back2['shape'] == built['shape'] and pressed == [built['shape']],
          f"{back2['shape']} with {back2['m']} masses; highlighted: {pressed}")

    # --- presets keep a hand-built body ---
    rt = pg.evaluate("""(()=>{ const s=JSON.parse(JSON.stringify(snapshot())); const m=state.geo.P.length, sp=state.geo.S.length;
      buildShape(true); const mid=state.geo.P.length; restore(s); return {m, sp, mid, back:state.geo.P.length, backS:state.geo.S.length}; })()""")
    pg.wait_for_timeout(700)
    snd = pg.evaluate(PEAK_JS)
    check('presets save and restore a hand-built body', rt['back'] == rt['m'] and rt['backS'] == rt['sp'] and snd['pk'] > 0.05, f"{rt}, plays {snd['pk']}")

    check('no page errors', not errs, str(errs[:3]))
    import tempfile; pg.screenshot(path=os.path.join(tempfile.gettempdir(), 'resonator-stage2.png'))
    b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage 2 browser checks pass')
sys.exit(1 if failed else 0)
