# Stage 1 browser checks (Playwright + Chromium). Run from the repo root:
#   python3 qa-resonator/stage1_browser.py [repo_root]
# Since Stage I the preview has only the Tank (no shape chips): the same proofs run on it there. A new body
# comes from Size instead of a shape chip, the octave-trap check slides the strike and mic circles instead of
# using the old strike tool, and every stall run must show that a new body really was built.
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
# I: the spectrum's peaks (local maxima, interpolated), strongest first: 30 Hz–4 kHz, within 50 dB of the
# strongest. For the Tank, whose "pitch" is a cluster of modes: two spectra of the same body share their
# peak frequencies even when the amplitudes wobble; a body retuned to another mode shares almost none.
PEAKS_JS = """async()=>{ if(!window._af){const a=ctx.createAnalyser();a.fftSize=32768;a.smoothingTimeConstant=0;(master||node).connect(a);window._af=a;}
  const a=window._af, d=new Float32Array(a.frequencyBinCount), bin=ctx.sampleRate/a.fftSize;
  document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
  await new Promise(r=>setTimeout(r,900)); a.getFloatFrequencyData(d);
  let mx=-1e9; const k0=Math.ceil(30/bin), k1=Math.min(d.length-3,Math.floor(4000/bin)); for(let k=k0;k<=k1;k++) if(d[k]>mx) mx=d[k];
  const out=[]; for(let k=k0;k<=k1;k++){ if(d[k]>mx-50&&d[k]>=d[k-1]&&d[k]>=d[k+1]&&d[k]>=d[k-2]&&d[k]>=d[k+2]){
      const y0=d[k-1],y1=d[k],y2=d[k+1],off=0.5*(y0-y2)/(y0-2*y1+y2); out.push([+((k+off)*bin).toFixed(2), +(y1-mx).toFixed(1)]); } }
  return out.sort((p,q)=>q[1]-p[1]); }"""
def peaks_match(A, B, top=5, pool=10, hz=0.6):
    """how many of A's `top` strongest peaks are within `hz` of one of B's `pool` strongest. The same body
    measured twice agrees to about 0.1 Hz; the Tank's spectrum is dense, so a wide tolerance or the whole
    peak list matches by chance (a first version, 15 cents against every peak, called a +75-cent retune
    4 of 6 the same)."""
    return sum(1 for f, _ in A[:top] if any(abs(g - f) < hz for g, _ in B[:pool]))
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

# I: one tap of Size moves it by 1/32 of its range, which often leaves the Tank's mass count where it was
# (no new body, nothing to stall on). Tap until the count changes, as a finger would, and record it.
# Direction 0: whichever way has room.
SIZE_TAPS = ("(d=>{if(!d){const S=SHAPES[state.shape];d=state.n<S.max?1:-1;}const b=document.querySelector('.knob[data-k=\"size\"] .step[data-d=\"'+d+'\"]'),n0=state.n;"
             "for(let q=0;q<40&&state.n===n0;q++){b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));}"
             "(window._built=window._built||[]).push(n0+'→'+state.n);})")
PAD = "document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))"
TANK_KEYS = ['a new Tank (Size +) while a note rings', 'Stiffness + on the Tank, then a note', 'a new Tank again (Size −)']
def stall_scenarios_tank(pg):
    # both pages on the Tank (the live page gets there by its chip first), then the same taps on each
    if pg.evaluate("!!document.getElementById('shapes')"):
        pg.click('#shapes .chip:text-is("Tank")'); pg.wait_for_timeout(2500)
    out = {}
    pg.evaluate("window._built=[];val.decay=8;syncKnob('decay');send('decay')")
    out[TANK_KEYS[0]] = pg.evaluate(STALL_JS, PAD + "; setTimeout(()=>" + SIZE_TAPS + "(1),250);")
    pg.wait_for_timeout(1500)
    out[TANK_KEYS[1]] = pg.evaluate(STALL_JS, "document.querySelector('.knob[data-k=ratio] .step[data-d=\"1\"]').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); document.querySelector('.knob[data-k=ratio] .step[data-d=\"1\"]').dispatchEvent(new PointerEvent('pointerup',{bubbles:true})); setTimeout(()=>" + PAD + ",60);")
    pg.wait_for_timeout(800)
    out[TANK_KEYS[2]] = pg.evaluate(STALL_JS, SIZE_TAPS + "(-1);")
    out['built'] = pg.evaluate('window._built')
    return out
XY = "(i) => { const r = cv.getBoundingClientRect(); return [r.left + _px[i], r.top + _py[i]]; }"
# a free mass well clear of both circles and of the buttons (as in i1_browser.py)
TARGET = """(avoid) => { const g = state.geo; let best = -1, bs = -1e9;
  for (const i of state.free) { const x = _px[i], y = _py[i]; if (y > H - 60 || y < 40 || x < 30 || x > W - 30) continue;
    let near = 1e9; for (const j of avoid) near = Math.min(near, Math.hypot(x - _px[j], y - _py[j]));
    let crowd = 1e9; for (let k = 0; k < g.P.length; k++) if (k !== i) crowd = Math.min(crowd, Math.hypot(x - _px[k], y - _py[k]));
    const sc = Math.min(near, 160) + 3 * Math.min(crowd, 20) + 40 * (_pf[i] || 0); if (near > 70 && sc > bs) { bs = sc; best = i; } }
  return best; }"""
def mouse_drag(pg, x0, y0, x1, y1, n=12):
    pg.mouse.move(x0, y0); pg.mouse.down()
    for k in range(1, n + 1): pg.mouse.move(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n); pg.wait_for_timeout(16)
    pg.mouse.up()

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    # ---- stalls: live page vs preview ----
    c, pg, errs = open_page(b, 'apps/resonator-next.html'); TANK_ONLY = pg.evaluate("!document.getElementById('shapes')"); c.close()
    res = {}
    for label, path in [('live', 'apps/resonator.html'), ('preview', 'apps/resonator-next.html')]:
        c, pg, errs = open_page(b, path)
        if not TANK_ONLY: assert pg.evaluate("document.querySelector('#shapes .chip:nth-child(7)').textContent") == 'Tank'
        res[label] = (stall_scenarios_tank if TANK_ONLY else stall_scenarios)(pg); res[label]['errors'] = errs
        if label == 'preview': res[label]['tuner'] = pg.evaluate("({on:TUNER.on,up:TUNER.up,stats:TUNER.stats})")
        c.close()
    for k in (TANK_KEYS if TANK_ONLY else ['switch to Tank while a note rings', 'Stiffness + on Tank, then a note', 'switch back to String']):
        print(f'  audio clock frozen, {k}: live {res["live"][k]} ms · preview {res["preview"][k]} ms')
    worst_prev = max(res['preview'][k] for k in res['preview'] if isinstance(res['preview'][k], int))
    built = {l: res[l].get('built') for l in res} if TANK_ONLY else None
    built_ok = (not TANK_ONLY) or all(len(v or []) == 2 and all(x.split('→')[0] != x.split('→')[1] for x in v) for v in built.values())
    check('preview: tuning never freezes the audio clock', worst_prev < 60 and built_ok, f'longest freeze {worst_prev} ms (live page: up to {max(v for v in res["live"].values() if isinstance(v,int))} ms)'
          + (f'; new bodies built (masses per ring): {built}' if TANK_ONLY else ''))
    check('preview: tuner running in the background', res['preview']['tuner']['on'] and res['preview']['tuner']['up'], json.dumps(res['preview']['tuner']['stats']))
    check('no page errors', not res['live']['errors'] and not res['preview']['errors'], str(res['live']['errors'] + res['preview']['errors']))

    # ---- every shape makes sound on the preview, including String again after Tank ----
    c, pg, errs = open_page(b, 'apps/resonator-next.html')
    peaks = []
    if TANK_ONLY:
        counts = []
        for i, s in enumerate(['Tank', 'a new Tank (Size +)', 'a new Tank (Size −)']):
            if i: pg.evaluate(SIZE_TAPS + f"({1 if i == 1 else -1})"); pg.wait_for_timeout(300)
            counts.append(pg.evaluate('state.geo.P.length')); peaks.append((s + f' ({counts[-1]} masses)', pg.evaluate(PEAK_JS))); pg.wait_for_timeout(600)
        check('preview: the Tank makes sound, and again after each new body', all(v > 0.05 for _, v in peaks) and counts[1] != counts[0] and counts[2] != counts[1],
              ' · '.join(f'{s} {v}' for s, v in peaks))
    else:
      for i, s in enumerate(['String', 'Tine', 'Chime', 'Drum', 'Hoop', 'Web', 'Tank', 'Twins', 'String']):
        if i: pg.click(f'#shapes .chip:text-is("{s}")')
        peaks.append((s, pg.evaluate(PEAK_JS))); pg.wait_for_timeout(600)
      check('preview: every shape makes sound', all(v > 0.05 for _, v in peaks), ' · '.join(f'{s} {v}' for s, v in peaks))

    # ---- octave trap through the real UI ----
    if TANK_ONLY:
        # The trap was a body retuned to a different mode after the strike moved and a control changed. On the
        # Tank: slide the strike and the mic circles to new balls (the Stage I gesture), Stiffness + then -
        # (two retunes with the new pickups), slide both back. The same circles and the same knobs must give
        # the same body: the keys tuned to the same mode (the engine's reference), and the same spectral
        # peaks. Not the "lowest strong partial": a shell like the Tank has no clear fundamental, and which
        # low mode clears a fixed threshold wobbles from strike to strike (measured 58.0 vs 54.1 Hz for the
        # same body and circles, both peaks present in both spectra). Each measurement starts from silence
        # (Hush): the Tank rings for seconds and the auditions strike it elsewhere. The measure is checked
        # too: one Trim tap (+75 cents) must change the peaks.
        def quiet(): pg.evaluate("document.getElementById('hush').click()"); pg.wait_for_timeout(500)
        pg.evaluate('state.spin = false'); pg.wait_for_timeout(300)
        home = {'strike': pg.evaluate('state.hitIdx'), 'mic': pg.evaluate('state.micIdx')}
        quiet(); r0 = pg.evaluate('state.info.fRef'); P1 = pg.evaluate(PEAKS_JS); pg.wait_for_timeout(600)
        moved = []
        def slide(kind, j):
            idx = 'state.hitIdx' if kind == 'strike' else 'state.micIdx'
            i0 = pg.evaluate(idx); x0, y0 = pg.evaluate(XY, i0); x1, y1 = pg.evaluate(XY, j)
            mouse_drag(pg, x0, y0, x1, y1); pg.wait_for_timeout(500); moved.append(f"{kind} #{i0}→#{pg.evaluate(idx)}" + ('' if pg.evaluate(idx) == j else f' (wanted #{j})'))
        for kind in ['strike', 'mic', 'strike', 'mic']:
            slide(kind, pg.evaluate(TARGET, [pg.evaluate('state.hitIdx'), pg.evaluate('state.micIdx')]))
        quiet(); Pm = pg.evaluate(PEAKS_JS); pg.wait_for_timeout(600)
        pg.click('.tab[data-page=body]'); pg.click('.knob[data-k=ratio] .step[data-d="1"]'); pg.wait_for_timeout(1200)
        r1 = pg.evaluate('state.info.fRef')
        pg.click('.knob[data-k=ratio] .step[data-d="-1"]'); pg.wait_for_timeout(1200)
        r2 = pg.evaluate('state.info.fRef')
        slide('strike', home['strike']); slide('mic', home['mic'])
        quiet(); P2 = pg.evaluate(PEAKS_JS); pg.wait_for_timeout(600)
        pg.click('.knob[data-k=tune] .step[data-d="1"]'); pg.wait_for_timeout(300); trim = pg.evaluate('val.tune')
        quiet(); Pt = pg.evaluate(PEAKS_JS)
        pg.click('.knob[data-k=tune] .step[data-d="-1"]'); pg.wait_for_timeout(300)
        same_mode = r0 > 0 and abs(1200 * math.log2(r2 / r0)) < 0.5
        m12, m21, mt = peaks_match(P1, P2), peaks_match(P2, P1), peaks_match(P1, Pt)
        all_moved = all('wanted' not in m for m in moved)
        top = lambda P: ' '.join(f'{f:.1f}' for f, _ in P[:5])
        check('preview: octave trap gone on the Tank (circles slid, Stiffness + and −, circles back: the same body)',
              same_mode and m12 >= 4 and m21 >= 4 and all_moved and mt <= 1 and pg.evaluate('val.tune') == 0,
              f"{'; '.join(moved)}; tuned mode {r0:.2f} → {r1:.2f} (Stiffness +) → {r2:.2f} Hz; strongest peaks (Hz) {top(P1)} → back home {top(P2)}: "
              f"{m12}/5 and {m21}/5 shared within 0.6 Hz (circles moved: {peaks_match(P1, Pm)}/5; the measure, Trim {trim:+g} cents: {mt}/5)")
    else:
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
    if TANK_ONLY: pg.evaluate("window._built=[];" + SIZE_TAPS + "(0)")
    else: pg.click('#shapes .chip:text-is("Tank")')
    pg.wait_for_timeout(300)
    pk_after = pg.evaluate(PEAK_JS); nb = pg.evaluate('window._built||[]') if TANK_ONLY else ['Tank chip']
    check('preview: shadow failure falls back to engine tuning', (not st['on']) and st['fails'] == 1 and pk_after > 0.05 and nb and nb[-1].split('→')[0] != nb[-1].split('→')[-1],
          f'{st} · ' + ('a new Tank ' + str(nb) if TANK_ONLY else 'Tank') + f' after fallback {pk_after}')
    c.close()

    # ---- no Worker at all (old browsers / blocked): must still play ----
    c, pg, errs = open_page(b, 'apps/resonator-next.html', init='window.Worker=undefined;')
    pk1 = pg.evaluate(PEAK_JS)
    if TANK_ONLY: pg.evaluate("window._built=[];" + SIZE_TAPS + "(0)")
    else: pg.click('#shapes .chip:text-is("Tank")')
    pg.wait_for_timeout(300); pk2 = pg.evaluate(PEAK_JS)
    on = pg.evaluate('TUNER.on'); nb = pg.evaluate('window._built||[]') if TANK_ONLY else []
    check('preview without Worker support still plays', (not on) and pk1 > 0.05 and pk2 > 0.05 and not errs and (not TANK_ONLY or (nb and nb[-1].split('→')[0] != nb[-1].split('→')[-1])),
          (f'Tank {pk1} · a new Tank {nb} {pk2}' if TANK_ONLY else f'String {pk1} · Tank {pk2}') + f' · errors {errs}')
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
