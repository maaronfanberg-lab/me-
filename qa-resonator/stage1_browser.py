# Stage 1 browser checks (Playwright + Chromium). Run from the repo root:
#   python3 qa-resonator/stage1_browser.py [repo_root]
# Measures audio-thread stalls with the audio clock: while the rendering thread is blocked,
# AudioContext.currentTime stops advancing, so the longest frozen stretch is the stall.
import sys, os, json, math, threading, functools, http.server
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..'))
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
failed = 0
def check(name, ok, detail=''):
    global failed
    print(('PASS ' if ok else 'FAIL ') + name + (' — ' + detail if detail else '')); failed += 0 if ok else 1

# longest stretch (ms of wall time) during which the audio clock did not move, while `action` runs
STALL_JS = """async(action)=>{ const t=[]; let last=ctx.currentTime, lastWall=performance.now(), worst=0;
  const tick=()=>{ const now=performance.now(), c=ctx.currentTime; if(c!==last){ last=c; lastWall=now; } else worst=Math.max(worst, now-lastWall); };
  const iv=setInterval(tick,4); await new Promise(r=>setTimeout(r,150));
  eval(action);
  await new Promise(r=>setTimeout(r,1800)); clearInterval(iv); tick(); return Math.round(worst); }"""
PEAK_JS = """async()=>{ if(!window._an){window._an=ctx.createAnalyser();window._an.fftSize=2048;(master||node).connect(window._an);}
  const an=window._an,buf=new Float32Array(2048);let pk=0;
  document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
  for(let i=0;i<120;i++){await new Promise(r=>setTimeout(r,25));an.getFloatTimeDomainData(buf);for(const v of buf)pk=Math.max(pk,Math.abs(v));}
  return +pk.toFixed(3); }"""   # 3 s: a heavy body (Tank) is tuned before its first note sounds
PITCH_JS = """async()=>{ if(!window._af){const a=ctx.createAnalyser();a.fftSize=32768;a.smoothingTimeConstant=0;(master||node).connect(a);window._af=a;}
  const a=window._af, d=new Float32Array(a.frequencyBinCount), bin=ctx.sampleRate/a.fftSize;
  document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
  await new Promise(r=>setTimeout(r,900)); a.getFloatFrequencyData(d);
  let mx=-1e9; for(let k=30;k<d.length;k++) if(d[k]>mx) mx=d[k];
  for(let k=Math.ceil(40/bin);k<d.length-2;k++){ if(d[k]>mx-25&&d[k]>=d[k-1]&&d[k]>=d[k+1]&&d[k]>=d[k-2]&&d[k]>=d[k+2]){
      const y0=d[k-1],y1=d[k],y2=d[k+1],off=0.5*(y0-y2)/(y0-2*y1+y2); return (k+off)*bin; } }
  return 0; }"""
NAMES = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
def note_name(f):
    if not f: return '?'
    m = round(69 + 12 * math.log2(f / 440)); return NAMES[m % 12] + str(m // 12 - 1)

def open_page(b, path, init=None, perms=None):
    c = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    if perms: c.grant_permissions(perms, origin=f'http://127.0.0.1:{PORT}')
    if init: c.add_init_script(init)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{path}'); pg.wait_for_timeout(300)
    pg.tap('#start'); pg.wait_for_timeout(1800)
    return c, pg, errs

def stall_scenarios(pg):
    out = {}
    pg.evaluate("val.decay=8;syncKnob('decay');send('decay')")
    out['switch to Tank while a note rings'] = pg.evaluate(STALL_JS, "document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); setTimeout(()=>document.querySelector('#shapes .chip:nth-child(7)').click(),250);")
    pg.wait_for_timeout(1500)
    out['Stiffness + on Tank, then a note'] = pg.evaluate(STALL_JS, "document.querySelector('.knob[data-k=ratio] .step[data-d=\"1\"]').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); document.querySelector('.knob[data-k=ratio] .step[data-d=\"1\"]').dispatchEvent(new PointerEvent('pointerup',{bubbles:true})); setTimeout(()=>document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})),60);")
    pg.wait_for_timeout(800)
    out['switch back to String'] = pg.evaluate(STALL_JS, "document.querySelector('#shapes .chip:nth-child(1)').click();")
    return out

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    # ---- stalls: live page vs preview ----
    res = {}
    for label, path in [('live', 'apps/resonator.html'), ('preview', 'apps/resonator-next.html')]:
        c, pg, errs = open_page(b, path)
        assert pg.evaluate("document.querySelector('#shapes .chip:nth-child(7)').textContent") == 'Tank'
        res[label] = stall_scenarios(pg); res[label]['errors'] = errs
        if label == 'preview': res[label]['tuner'] = pg.evaluate("({on:TUNER.on,up:TUNER.up,stats:TUNER.stats})")
        c.close()
    for k in ['switch to Tank while a note rings', 'Stiffness + on Tank, then a note', 'switch back to String']:
        print(f'  audio clock frozen, {k}: live {res["live"][k]} ms · preview {res["preview"][k]} ms')
    worst_prev = max(res['preview'][k] for k in res['preview'] if isinstance(res['preview'][k], int))
    check('preview: tuning never freezes the audio clock', worst_prev < 60, f'longest freeze {worst_prev} ms (live page: up to {max(v for v in res["live"].values() if isinstance(v,int))} ms)')
    check('preview: tuner running in the background', res['preview']['tuner']['on'] and res['preview']['tuner']['up'], json.dumps(res['preview']['tuner']['stats']))
    check('no page errors', not res['live']['errors'] and not res['preview']['errors'], str(res['live']['errors'] + res['preview']['errors']))

    # ---- every shape makes sound on the preview, including String again after Tank ----
    c, pg, errs = open_page(b, 'apps/resonator-next.html')
    peaks = []
    for i, s in enumerate(['String', 'Tine', 'Chime', 'Drum', 'Hoop', 'Web', 'Tank', 'Twins', 'String']):
        if i: pg.click(f'#shapes .chip:text-is("{s}")')
        peaks.append((s, pg.evaluate(PEAK_JS))); pg.wait_for_timeout(600)
    check('preview: every shape makes sound', all(v > 0.05 for _, v in peaks), ' · '.join(f'{s} {v}' for s, v in peaks))

    # ---- octave trap through the real UI ----
    pg.click('#shapes .chip:text-is("String")'); pg.wait_for_timeout(800)
    f1 = pg.evaluate(PITCH_JS); pg.wait_for_timeout(600)
    pg.click('.tool[data-tool=strike]'); pg.wait_for_timeout(150)
    x, y = pg.evaluate("(()=>{const r=cv.getBoundingClientRect();const i=state.free[1];return [r.left+_px[i],r.top+_py[i]];})()")
    pg.mouse.click(x, y); pg.wait_for_timeout(1200)
    pg.click('.tab[data-page=body]'); pg.click('.knob[data-k=ratio] .step[data-d="1"]'); pg.wait_for_timeout(300)
    f2 = pg.evaluate(PITCH_JS)
    check('preview: octave trap gone (real taps)', note_name(f1) == 'E3' and note_name(f2) == 'E3', f'{note_name(f1)} → {note_name(f2)} ({f1:.1f} → {f2:.1f} Hz)')

    # ---- error path: a broken message makes the shadow fail; the engine must take over tuning ----
    pg.evaluate("TUNER.w.postMessage({t:'struct'})"); pg.wait_for_timeout(500)
    st = pg.evaluate("({on:TUNER.on,fails:TUNER.stats.fails,why:TUNER.stats.why})")
    pg.click('#shapes .chip:text-is("Tank")'); pg.wait_for_timeout(300)
    pk_after = pg.evaluate(PEAK_JS)
    check('preview: shadow failure falls back to engine tuning', (not st['on']) and st['fails'] == 1 and pk_after > 0.05, f'{st} · Tank after fallback {pk_after}')
    c.close()

    # ---- no Worker at all (old browsers / blocked): must still play ----
    c, pg, errs = open_page(b, 'apps/resonator-next.html', init='window.Worker=undefined;')
    pk1 = pg.evaluate(PEAK_JS); pg.click('#shapes .chip:text-is("Tank")'); pg.wait_for_timeout(300); pk2 = pg.evaluate(PEAK_JS)
    on = pg.evaluate('TUNER.on')
    check('preview without Worker support still plays', (not on) and pk1 > 0.05 and pk2 > 0.05 and not errs, f'String {pk1} · Tank {pk2} · errors {errs}')
    c.close()

    # ---- Copy report ----
    c, pg, errs = open_page(b, 'apps/resonator-next.html', perms=['clipboard-read', 'clipboard-write'])
    pg.click('#copydiag'); pg.wait_for_timeout(400)
    txt = pg.evaluate('navigator.clipboard.readText()'); label = pg.inner_text('#copydiag')
    check('Copy report copies a usable report', 'RESONATOR report' in txt and 'tuning thread: background' in txt and label.startswith('Copied'), txt.split('\n')[3] if txt.count('\n') > 3 else txt[:120])
    c.close()
    b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage 1 browser checks pass')
sys.exit(1 if failed else 0)
