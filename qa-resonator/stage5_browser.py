# Stage 5 browser checks: modulator types by taps (LFO / Envelope / Follower), the right controls for each,
# the messages the engine gets, the live meters (envelope through attack, sustain and release; follower on
# Mic 1 and on the phone microphone via Chromium's fake device), an audible envelope, presets, and that an
# LFO's message is exactly as before. Run from the repo root:
#   python3 qa-resonator/stage5_browser.py [repo_root]
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

HOOK = """window._mods=[]; { const r=node.port.postMessage.bind(node.port);
  node.port.postMessage=(m,tr)=>{ if(m&&m.t==='mod') window._mods.push(JSON.parse(JSON.stringify(m))); return r(m,tr); }; }"""
PAD_DOWN = "document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));"
PAD_UP = "document.querySelector('#pads .pad').dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));"
# meter width (0..1) of modulator i, sampled every 30 ms for `ms`
METER = """async([i, ms])=>{ const b=document.querySelector('[data-mm="'+i+'"] i'), out=[];
  for(let t=0;t<ms;t+=30){ await new Promise(r=>setTimeout(r,30)); out.push(parseFloat(b.style.width||'0')/100); } return out; }"""
# peak of the output over `ms`, starting `skip` ms after running `pre` (so a note's first milliseconds can be left out)
LEVEL = """async([pre, ms, skip])=>{ if(!window._an){window._an=ctx.createAnalyser();window._an.fftSize=2048;(master||node).connect(window._an);}
  const an=window._an,buf=new Float32Array(2048); let pk=0; if(pre) eval(pre); if(skip) await new Promise(r=>setTimeout(r,skip));
  const n=Math.round(ms/25); for(let i=0;i<n;i++){ await new Promise(r=>setTimeout(r,25)); an.getFloatTimeDomainData(buf); for(const v of buf) pk=Math.max(pk,Math.abs(v)); }
  return +pk.toFixed(4); }"""
def shown(pg, sel): return pg.evaluate(f"(()=>{{const e=document.querySelector('{sel}');return !!e&&e.offsetParent!==null;}})()")
def taps(pg, k, d, n):
    for _ in range(n): pg.tap(f'.knob[data-k={k}] .step[data-d="{d}"]')
def last_mod(pg, i):
    ms = [m for m in pg.evaluate("window._mods") if m['i'] == i]
    return ms[-1] if ms else None

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    c = b.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    c.grant_permissions(['microphone'], origin=f'http://127.0.0.1:{PORT}')
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(300)
    pg.tap('#start'); pg.wait_for_timeout(1800)
    pg.evaluate(HOOK)
    pg.tap('.tab[data-page=mod]'); pg.wait_for_timeout(150)

    # --- default: LFO, with only the LFO's controls ---
    types = pg.evaluate("[...document.querySelectorAll('[data-mty=\"0\"] .chip')].map(c=>c.textContent+(c.getAttribute('aria-pressed')==='true'?'*':''))")
    lfo_ui = shown(pg, '.knob[data-k=m1r]') and not shown(pg, '.knob[data-k=m1at]') and not shown(pg, '.knob[data-k=m1fa]') and not shown(pg, '[data-mm="0"]')
    check('each modulator offers LFO / Envelope / Follower; LFO by default with only its controls', types == ['LFO*', 'Envelope', 'Follower'] and lfo_ui, str(types))
    width = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")

    # an LFO's message is exactly as before (no new fields)
    pg.select_option('.mrow[data-m="1"] select >> nth=0', 'tone'); taps(pg, 'm2a', 1, 5); pg.wait_for_timeout(100)
    lm = last_mod(pg, 1)
    check("an LFO's message to the engine is exactly as before", lm and sorted(lm.keys()) == ['a', 'd', 'i', 'r', 'sh', 't'] and lm['d'] == 'tone', str(lm))
    taps(pg, 'm2a', -1, 8)

    # --- Envelope by taps ---
    pg.tap('[data-mty="0"] .chip:nth-child(2)'); pg.wait_for_timeout(100)
    vis = pg.evaluate("""(()=>{ const v=s=>{const e=document.querySelector(s);return !!e&&e.offsetParent!==null;};
      return {adsr:['at','dc','su','rl'].every(x=>v('.knob[data-k=m1'+x+']')), rate:v('.knob[data-k=m1r]'), wave:document.querySelectorAll('.mrow[data-m="0"] select')[1].offsetParent!==null,
              fol:v('.knob[data-k=m1fa]'), dir:v('[data-mdir="0"]'), meter:v('[data-mm="0"]'), hint:document.querySelector('[data-mhint="0"]').textContent}; })()""")
    check('Envelope shows Attack/Decay/Sustain/Release, Push up/down and a meter; hides Rate and wave', vis['adsr'] and not vis['rate'] and not vis['wave'] and not vis['fol'] and vis['dir'] and vis['meter'] and 'Pick what it moves' in vis['hint'], str(vis))
    pg.select_option('.mrow[data-m="0"] select >> nth=0', 'tone')
    taps(pg, 'm1a', 1, 16); taps(pg, 'm1su', 1, 10); pg.wait_for_timeout(100)
    lab = {k: pg.inner_text(f'.knob[data-k={k}] .lab b') for k in ('m1at', 'm1dc', 'm1su', 'm1rl', 'm1a')}
    em = last_mod(pg, 0)
    ok = em and em.get('ty') == 1 and em['d'] == 'tone' and abs(em['S'] - 0.30) < 1e-9 and abs(em['a'] - 0.48) < 1e-9 and abs(em['A'] - 0.005) < 0.0002 and abs(em['D'] - 0.302) < 0.002 and em['inv'] == 0
    check('the engine gets the envelope the knobs show', bool(ok), f"labels {lab}; message ty {em and em.get('ty')}, A {em and round(em['A'], 4)} s, D {em and round(em['D'], 3)} s, S {em and em['S']}, R {em and round(em['R'], 3)} s, depth {em and em['a']}")

    # meter: attack to the top, settle at sustain while held, fall away after release
    pg.evaluate(f"(()=>{{ {PAD_DOWN} }})()")
    held = pg.evaluate(METER, [0, 1500])
    pg.evaluate(f"(()=>{{ {PAD_UP} }})()")
    after = pg.evaluate(METER, [0, 1200])
    # the meter updates about every 32 ms, so with a 5 ms attack and a 302 ms decay it shows ≥ 0.80 of the peak
    check('envelope meter: rises to the top, rests at Sustain while held, falls after release', max(held) > 0.75 and abs(held[-1] - 0.30) < 0.05 and after[-1] < 0.03,
          f"peak {max(held):.2f}, held {held[-1]:.2f} (sustain 0.30), 1.2 s after release {after[-1]:.2f}")

    # audible: Push down on Level with Sustain 100% holds the sound down while the key is held
    pg.select_option('.mrow[data-m="0"] select >> nth=0', 'gain'); taps(pg, 'm1a', 1, 20); taps(pg, 'm1su', 1, 30)
    pg.tap('[data-mdir="0"] .chip:nth-child(2)'); pg.wait_for_timeout(1500)
    ducked = pg.evaluate(LEVEL, [PAD_DOWN, 750, 150]); pg.evaluate(f"(()=>{{ {PAD_UP} }})()"); pg.wait_for_timeout(2500)
    pg.tap('[data-mty="0"] .chip:nth-child(1)'); pg.wait_for_timeout(300)     # back to LFO at depth: Rate is slow, so measure with Depth 0
    taps(pg, 'm1a', -1, 40); pg.wait_for_timeout(1500)
    plain = pg.evaluate(LEVEL, [PAD_DOWN, 750, 150]); pg.evaluate(f"(()=>{{ {PAD_UP} }})()"); pg.wait_for_timeout(1500)
    check('an envelope is heard: Push down on Level holds the note down while the key is held', plain > 0.05 and ducked < 0.25 * plain, f"peak 0.15–0.9 s into the held note: {ducked} with the envelope, {plain} without")

    # --- Follower ---
    pg.tap('[data-mty="0"] .chip:nth-child(3)'); pg.wait_for_timeout(100)
    vis = pg.evaluate("""(()=>{ const v=s=>{const e=document.querySelector(s);return !!e&&e.offsetParent!==null;};
      return {fol:['fa','fr','se'].every(x=>v('.knob[data-k=m1'+x+']')), adsr:v('.knob[data-k=m1at]'), src:[...document.querySelectorAll('[data-msrc="0"] .chip')].map(c=>c.textContent+(c.getAttribute('aria-pressed')==='true'?'*':'')),
              labs:['fa','fr','se'].map(x=>document.querySelector('.knob[data-k=m1'+x+'] .lab b').textContent)}; })()""")
    check('Follower shows its source, Follow attack/release and Sensitivity (defaults 22 ms / 50 ms / +13 dB)', vis['fol'] and not vis['adsr'] and vis['src'] == ['Mic 1*', 'Mic 2', 'Mic 3', 'Mic 4', 'Phone mic'] and vis['labs'] == ['22 ms', '50 ms', '+13.0 dB'], str(vis))
    taps(pg, 'm1a', 1, 10); pg.wait_for_timeout(200)
    pg.evaluate(f"(()=>{{ {PAD_DOWN} }})()")
    fm = pg.evaluate(METER, [0, 600]); pg.evaluate(f"(()=>{{ {PAD_UP} }})()")
    late = pg.evaluate(METER, [0, 4500])
    check('follower meter follows Mic 1: up with the hit, down as it fades', max(fm) > 0.4 and late[-1] < 0.5 * max(fm), f"peak {max(fm):.2f}, 5 s later {late[-1]:.2f}")
    pg.tap('[data-msrc="0"] .chip:nth-child(3)'); pg.wait_for_timeout(100)
    h3 = pg.inner_text('[data-mhint="0"]')
    pg.tap('[data-msrc="0"] .chip:nth-child(5)'); pg.wait_for_timeout(100)
    h5 = pg.inner_text('[data-mhint="0"]')
    check('follower hints: an off mic and Mic in being off are explained', 'Mic 3 is off' in h3 and 'Turn on Mic in' in h5, f"{h3!r} · {h5!r}")
    # phone microphone (Chromium's fake device), with Mic input at 0 so the voice only steers
    pg.tap('.tab[data-page=strike]'); pg.wait_for_timeout(100)
    pg.tap('.knob[data-k=inGain] .lab'); pg.wait_for_timeout(120)
    for _ in range(40): pg.tap('.knob[data-k=inGain] .step[data-d="-1"]')
    pg.tap('#micin'); pg.wait_for_timeout(1500)
    pg.tap('.tab[data-page=mod]'); pg.wait_for_timeout(100)
    pm = pg.evaluate(METER, [0, 3000]); h5on = pg.inner_text('[data-mhint="0"]')
    pg.tap('.tab[data-page=strike]'); pg.tap('#micin'); pg.wait_for_timeout(300); pg.tap('.tab[data-page=mod]')
    check('follower on the phone microphone moves with the sound it hears', max(pm) > 0.1 and min(pm) < 0.5 * max(pm) and 'Phone mic' in h5on, f"meter range {min(pm):.2f}–{max(pm):.2f} over 3 s; hint {h5on!r}")

    # presets keep type, direction, source and the knobs
    rt = pg.evaluate("""(()=>{ const s=JSON.parse(JSON.stringify(snapshot())); const want=JSON.stringify(state.mods.map(m=>[m.ty||0,m.dn||0,m.src||0,m.d]));
      const se=val.m1se; state.mods.forEach(m=>{m.ty=0;m.dn=0;m.src=0;}); for(let i=0;i<3;i++) modUI(i); restore(s);
      return {back: JSON.stringify(state.mods.map(m=>[m.ty||0,m.dn||0,m.src||0,m.d]))===want, se: val.m1se===se,
              chip: document.querySelector('[data-mty="0"] .chip:nth-child(3)').getAttribute('aria-pressed'), fol: document.querySelector('.knob[data-k=m1fa]').offsetParent!==null}; })()""")
    check('a preset brings back each modulator\'s type, direction, source and knobs', rt['back'] and rt['se'] and rt['chip'] == 'true' and rt['fol'], str(rt))
    check('Mod tab fits a 390 px phone', width[0] <= width[1], f"page width {width[0]} for a {width[1]} px screen")
    check('no page errors', not errs, str(errs[:3]))
    b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage 5 browser checks pass')
sys.exit(1 if failed else 0)
