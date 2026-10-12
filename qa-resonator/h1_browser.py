# Stage H (factory presets, Learn tab, presets that come back as saved) — browser checks.
#   python3 qa-resonator/h1_browser.py [repo_root] [--browser=webkit]
# Chromium by default; --browser=webkit runs Safari's engine with iPhone 13 emulation. Every control is
# driven by taps. Messages to the engine are recorded at the page's own port (after the background
# tuner's router), so the checks see what the engine is told, in order.
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
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f' — {detail}' if detail else ''), flush=True); failed += 0 if ok else 1

TAP = "sel => { const e = document.querySelector(sel); if (!e) return false; e.scrollIntoView({block:'center'}); return true; }"
RECORD = """() => { window.__msgs = []; const po = node.port.postMessage;
  node.port.postMessage = function (m, t) { try { const c = {}; for (const k in m) { const v = m[k]; c[k] = (v && v.buffer && v.length !== undefined) ? '[' + v.length + ']' : v; } window.__msgs.push(c); } catch (e) {}
    return po.call(node.port, m, t); }; return true; }"""
LISTEN = """async (ms) => { const an = ctx.createAnalyser(); master.connect(an); const buf = new Float32Array(2048); let pk = 0;
  const t = performance.now(); while (performance.now() - t < ms) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf); for (const v of buf) pk = Math.max(pk, Math.abs(v)); }
  try { master.disconnect(an); } catch (e) {} return pk; }"""
KEY = """() => { const p = padsEl.children[SCALES[state.scale].length]; p.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); setTimeout(() => p.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })), 150); return p.textContent; }"""

def tap(pg, sel):
    pg.evaluate(TAP, sel); pg.tap(sel)

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
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400)
    tap(pg, '#start'); pg.wait_for_timeout(1800)
    pg.evaluate(RECORD)

    # ---------- layout: seven tabs on a phone ----------
    lay = pg.evaluate("""() => { const t = [...document.querySelectorAll('.tab')].map(e => { const r = e.getBoundingClientRect(); return [e.textContent, r.left, r.right, e.scrollWidth <= e.clientWidth + 1]; });
      return { t, W: innerWidth, sw: document.documentElement.scrollWidth }; }""")
    check('seven tabs, Learn last, all on screen at phone width, nothing clipped', len(lay['t']) == 7 and lay['t'][-1][0] == 'Learn' and all(x[1] >= 0 and x[2] <= lay['W'] + 0.5 and x[3] for x in lay['t']) and lay['sw'] <= lay['W'],
          f"{lay['W']} px: " + ', '.join(f"{x[0]} {x[2] - x[1]:.0f}" for x in lay['t']))
    pg.set_viewport_size({'width': 375, 'height': 812}); pg.wait_for_timeout(200)
    lay2 = pg.evaluate("() => [...document.querySelectorAll('.tab')].every(e => { const r = e.getBoundingClientRect(); return r.right <= innerWidth + 0.5 && e.scrollWidth <= e.clientWidth + 1; }) && document.documentElement.scrollWidth <= innerWidth")
    check('...and at 375 px (iPhone SE / mini)', lay2)
    pg.set_viewport_size(dev['viewport'] if 'viewport' in dev else {'width': 390, 'height': 844}); pg.wait_for_timeout(200)

    # ---------- an instrument of my own, set by taps, to come back to ----------
    tap(pg, '.tab[data-page=body]')
    pg.evaluate("[...document.querySelectorAll('#shapes .chip')].find(c => c.textContent === 'Hoop').scrollIntoView()"); pg.locator('#shapes .chip', has_text='Hoop').tap(); pg.wait_for_timeout(600)
    pg.locator('#specs .chip', has_text='Bell').tap()
    tap(pg, '.tab[data-page=mic]'); pg.locator('#axes .chip', has_text='Mic axis X').tap()
    tap(pg, '.tab[data-page=strike]'); tap(pg, '#bow'); tap(pg, '[data-scale="1"]')
    pg.evaluate("() => { val.decay = 7.3; syncKnob('decay'); send('decay'); }"); pg.wait_for_timeout(900)
    mine = pg.evaluate("() => ({ shape: state.shape, n: state.n, decay: val.decay, bow: document.getElementById('bow').getAttribute('aria-pressed'), vbow: val.bow, axis: state.axis, spec: state.spec, scale: state.scale, fRef: state.info && state.info.fRef, P: state.geo.P.length, mic: state.micIdx, hit: state.hitIdx })")

    # ---------- the Learn tab ----------
    tap(pg, '.tab[data-page=learn]')
    info = pg.evaluate("() => ({ n: document.querySelectorAll('.lesson').length, ab: document.querySelectorAll('.lesson [data-a=A]').length, back: document.getElementById('lback').disabled, why: [...document.querySelectorAll('.lwhy')].some(w => w.offsetParent !== null) })")
    check('Learn: 10 lessons, 9 with A and B; the explanations are closed; nothing to give back yet', info['n'] == 10 and info['ab'] == 9 and info['back'] and not info['why'], json.dumps(info))
    LESS = pg.evaluate("() => LESSONS.map(L => ({ t: L.t, how: !!L.how, base: L.base, A: L.A, B: L.B, hold: L.hold || 0.15 }))")
    STATE = """(L) => { const S = SHAPES[state.shape], free = state.free, at = v => free[Math.min(free.length - 1, Math.round(v * (free.length - 1)))];
      return { shape: state.shape, n: state.n, mode: state.mode, val: Object.assign({}, val), mods0: Object.assign({}, state.mods[0]), mic: state.micIdx, hit: state.hitIdx,
        atMic: at(val.mic), atHit: at(val.hit), bow: document.getElementById('bow').getAttribute('aria-pressed'), vbow: val.bow,
        why: document.querySelectorAll('.lesson')[L].querySelector('.lwhy').offsetParent !== null, back: document.getElementById('lback').disabled }; }"""
    REF = "(sh) => { const S = SHAPES[sh.shape], g = S.make(sh.n); return { h: g.hit, m: g.mic }; }"
    for i, L in enumerate(LESS):
        if L['how']:
            continue
        for side in ['A', 'B']:
            pg.evaluate('window.__msgs.length = 0')
            tap(pg, f'.lesson[data-l="{i}"] [data-a={side}]')
            pg.wait_for_timeout(int(450 + 1000 * L['hold']))
            st = pg.evaluate(STATE, i); msgs = pg.evaluate('window.__msgs')
            ch = L[side][1]; base = L['base']; bad = []
            shape = ch.get('shape', base['shape'])
            if st['shape'] != shape: bad.append(f"shape {st['shape']}")
            if 'n' in base and 'shape' not in ch and st['n'] != base['n']: bad.append(f"n {st['n']}")
            for k, v in {**base.get('val', {}), **{k: v for k, v in ch.items() if k not in ('shape', 'mode', 'env')}}.items():
                if abs(st['val'][k] - v) > 1e-9: bad.append(f'{k}={st["val"][k]}')
            if 'mode' in ch and st['mode'] != ch['mode']: bad.append(f"mode {st['mode']}")
            if 'env' in ch and (st['mods0']['d'] != ('tone' if ch['env'] else '') or st['mods0']['ty'] != (1 if ch['env'] else 0)): bad.append(f"mod 1 {st['mods0']}")
            if st['mic'] != st['atMic'] or st['hit'] != st['atHit']: bad.append(f"mic/strike {st['mic']}/{st['hit']} vs knobs {st['atMic']}/{st['atHit']}")
            if st['bow'] != 'false' or st['vbow']: bad.append('bow on')
            notes = [m for m in msgs if m.get('t') == 'note']; offs = [m for m in msgs if m.get('t') == 'off']
            if len(notes) != 1 or abs(notes[0]['f'] - 329.6276) > 0.01 or notes[0]['v'] != 0.8: bad.append(f'notes {notes}')
            if len(offs) != 1: bad.append(f'{len(offs)} key releases')
            structs = [m for m in msgs if m.get('t') == 'struct']
            if side == 'A' or 'shape' in ch:
                want = pg.evaluate(REF, {'shape': st['shape'], 'n': st['n']})
                if not structs or structs[0]['mic'] != want['m'] or structs[0]['hit'] != want['h']: bad.append(f"body built with mic/strike {[(s['mic'], s['hit']) for s in structs]}, want the shape's own {want['m']}/{want['h']}")
            elif structs: bad.append('B rebuilt the body')
            if side == 'A' and st['why']: bad.append('explanation open after A only')
            if side == 'B' and not st['why']: bad.append('explanation still closed after A and B')
            if st['back']: bad.append('give-back button not enabled')
            check(f"lesson {i + 1} {L['t']}, {side} · {L[side][0]}: sets exactly that, plays E4 at 0.8 for {L['hold']} s", not bad, '; '.join(bad) if bad else f"{st['shape']} {st['n']} masses, strike #{st['hit']}, mic #{st['mic']}")
        pg.evaluate('window.__msgs.length = 0'); tap(pg, f'.lesson[data-l="{i}"] [data-a=play]'); pg.wait_for_timeout(int(350 + 1000 * L['hold']))
        n2 = pg.evaluate("window.__msgs.filter(m => m.t === 'note' || m.t === 'off').map(m => m.t).join(',')")
        if i in (0, 8): check(f"lesson {i + 1}: Play again plays the same key once more", n2 == 'off,note,off' or n2 == 'note,off', n2)
    sc = pg.evaluate("() => [state.scale, document.querySelector('[data-scale][aria-pressed=true]').dataset.scale]")
    check('during the lessons the scale chips show the lesson\'s scale', sc == [0, '0'], str(sc))
    # the octave fix, in the lessons: the strike and mic near the end of a 15-mass string still tune the note
    tap(pg, '.lesson[data-l="4"] [data-a=A]'); pg.wait_for_timeout(900)
    fr5 = pg.evaluate("[state.info.fRef, state.n, state.hitIdx, state.micIdx]")
    tap(pg, '.lesson[data-l="3"] [data-a=A]'); pg.wait_for_timeout(900)
    fr4 = pg.evaluate("[state.info.fRef, state.n, state.hitIdx, state.micIdx]")
    check("lessons 4 and 5 tune the same partial (a strike and mic near the end don't move the note an octave)", fr5[1] == fr4[1] == 15 and abs(fr5[0] - fr4[0]) < 1e-6 * fr4[0],
          f"lesson 5 (strike #{fr5[2]}, mic #{fr5[3]}): reference mode {fr5[0]:.2f} Hz; lesson 4 (strike #{fr4[2]}, mic #{fr4[3]}): {fr4[0]:.2f} Hz")

    # ---------- build your own ----------
    tap(pg, '.lesson[data-l="9"] [data-a=go]'); pg.wait_for_timeout(700)
    hw = pg.evaluate("() => ({ shape: state.shape, n: state.n, P: state.geo.P.length, tool: document.querySelector('.tool[data-tool=add]').getAttribute('aria-pressed'), msg: document.getElementById('msg').textContent })")
    check('Build your own: a 6-mass string with the add tool on, and a hint', hw['shape'] == 'String' and hw['n'] == 6 and hw['P'] == 8 and hw['tool'] == 'true' and 'tap empty space' in hw['msg'], json.dumps(hw))
    pg.evaluate("document.querySelector('.tool[data-tool=orbit]').click()")

    # ---------- give it back ----------
    pg.evaluate('window.__msgs.length = 0'); tap(pg, '#lback'); pg.wait_for_timeout(1200)
    back = pg.evaluate("() => ({ shape: state.shape, n: state.n, decay: val.decay, bow: document.getElementById('bow').getAttribute('aria-pressed'), vbow: val.bow, axis: state.axis, spec: state.spec, scale: state.scale, scaleChip: document.querySelector('[data-scale][aria-pressed=true]').dataset.scale, fRef: state.info && state.info.fRef, P: state.geo.P.length, mic: state.micIdx, hit: state.hitIdx, disabled: document.getElementById('lback').disabled, msg: document.getElementById('msg').textContent, axisChip: [...document.querySelectorAll('#axes .chip')].findIndex(c => c.getAttribute('aria-pressed') === 'true'), body: document.getElementById('bodytext').textContent === SHAPES[state.shape].note })")
    sent = pg.evaluate("window.__msgs.filter(m => m.t === 'spec' || (m.t === 'p' && m.k === 'bow')).map(m => m.t + ':' + (m.v))")
    same = all(back[k] == mine[k] for k in ['shape', 'n', 'decay', 'bow', 'vbow', 'axis', 'spec', 'scale', 'P', 'mic', 'hit']) and back['scaleChip'] == '1' and abs((back['fRef'] or 0) - (mine['fRef'] or 0)) < 1e-6
    check('Put my instrument back: shape, size, knobs, bow, Mic axis X, spectrum, scale, pickups and tuning all return', same and back['disabled'] and back['axisChip'] == 0 and back['body'] and 'spec:1' in sent and 'p:0.16' in sent,
          f"mine {json.dumps(mine)} → back {json.dumps({k: back[k] for k in mine})}; engine told {sent}; message {back['msg']!r}")

    # ---------- factory presets ----------
    tap(pg, '.tab[data-page=body]')
    opts = pg.evaluate("() => ({ first: document.querySelector('#plist option').textContent, groups: [...document.querySelectorAll('#plist optgroup')].map(g => [g.label, [...g.children].map(o => o.textContent)]) })")
    FACT = pg.evaluate("() => FACTORY.map(f => ({ name: f.name, shape: f.shape, mode: f.mode || 0, pk: f.pk || 0, bow: !!f.bow, val: f.val, note: f.note }))")
    check('Presets list: a Factory group with the 10 presets, then the ones saved here', opts['first'] == '— pick a preset —' and opts['groups'][0][0] == 'Factory' and opts['groups'][0][1] == [f['name'] for f in FACT] and opts['groups'][1][0].startswith('Saved on this phone'), json.dumps(opts['groups']))
    for f in FACT:
        pg.select_option('#plist', 'factory:' + f['name']); tap(pg, '#pload'); pg.wait_for_timeout(500)
        st = pg.evaluate("() => ({ shape: state.shape, mode: state.mode, pk: state.pk, val: Object.assign({}, val), bow: document.getElementById('bow').getAttribute('aria-pressed'), msg: document.getElementById('msg').textContent })")
        pg.wait_for_timeout(1500)
        msg2 = pg.evaluate("document.getElementById('msg').textContent")
        bad = []
        if st['shape'] != f['shape'] or st['mode'] != f['mode'] or st['pk'] != f['pk']: bad.append(f"shape/mode/pickup {st['shape']}/{st['mode']}/{st['pk']}")
        for k, v in f['val'].items():
            if abs(st['val'][k] - v) > 1e-9: bad.append(f"{k}={st['val'][k]}")
        if st['bow'] != ('true' if f['bow'] else 'false'): bad.append(f"bow {st['bow']}")
        want = f"Loaded {f['name']}. {f['note']}"
        if st['msg'] != want or msg2 != want: bad.append(f'message {st["msg"]!r} then {msg2!r}')
        sounds = f['bow'] or f['val'].get('wind', 0) > 0
        if not sounds: pg.evaluate(KEY)
        pk = pg.evaluate(LISTEN, 900)
        if pk < 0.01: bad.append(f'peak {pk:.4f}')
        check(f"factory preset {f['name']}: loads, says what it is (still readable 2 s later), plays", not bad, '; '.join(bad) if bad else f'peak {pk:.3f}' + (' with no key' if sounds else ''))
        if f['name'] == 'Steel tank':   # a heavy body: the readout's own warning comes back once the message has been read
            pg.wait_for_timeout(4200)
            later = pg.evaluate("() => ({ msg: document.getElementById('msg').textContent, load: state.geo.S.length * state.info.os, springs: state.geo.S.length, os: state.info.os })")
            want = 'This one is heavy' if later['load'] > 190 else ''
            check("...and after a few seconds the message line goes back to the readout's own note", later['msg'].startswith(want) if want else later['msg'] == '',
                  f"{later['springs']} springs × {later['os']}× = {later['load']} (heavy above 190); line now {later['msg']!r}")
    tap(pg, '.tab[data-page=strike]'); tap(pg, '#hush'); pg.wait_for_timeout(300); tap(pg, '.tab[data-page=body]')
    pg.select_option('#plist', 'factory:Harp'); tap(pg, '#pdel'); pg.wait_for_timeout(200)
    d = pg.evaluate("() => ({ still: !!document.querySelector('#plist option[value=\"factory:Harp\"]'), msg: document.getElementById('msg').textContent })")
    check('Delete leaves a factory preset alone and says so', d['still'] and d['msg'].startswith('Factory presets stay'), d['msg'])

    # ---------- a preset comes back as it was saved, including which partial is tuned ----------
    tap(pg, '.tab[data-page=learn]'); tap(pg, '.lesson[data-l="4"] [data-a=A]'); pg.wait_for_timeout(900)
    pre = pg.evaluate("() => ({ fRef: state.info.fRef, mic: state.micIdx, hit: state.hitIdx, ref: state.ref })")
    tap(pg, '.tab[data-page=body]'); tap(pg, '#psave'); pg.wait_for_timeout(200)
    saved = pg.evaluate("document.getElementById('plist').value")
    pg.select_option('#plist', 'factory:Gong'); tap(pg, '#pload'); pg.wait_for_timeout(900)
    pg.evaluate('window.__msgs.length = 0'); pg.select_option('#plist', saved); tap(pg, '#pload'); pg.wait_for_timeout(1200)
    post = pg.evaluate("() => ({ fRef: state.info.fRef, mic: state.micIdx, hit: state.hitIdx, ref: state.ref, msg: document.getElementById('msg').textContent })")
    seq = pg.evaluate("window.__msgs.filter(m => m.t === 'struct' || m.t === 'mic' || m.t === 'hit').map(m => m.t + ':' + (m.t === 'struct' ? m.mic + '/' + m.hit : m.i))")
    check('a saved preset reloads with the same partial tuned: built with the strike and mic it was tuned with, then moved',
          abs(post['fRef'] - pre['fRef']) < 1e-6 * pre['fRef'] and post['mic'] == pre['mic'] and post['hit'] == pre['hit'] and seq[0] == f"struct:{pre['ref']['m']}/{pre['ref']['h']}" and f"mic:{pre['mic']}" in seq and f"hit:{pre['hit']}" in seq and post['msg'] == 'Loaded ' + saved,
          f"{saved}: reference mode {pre['fRef']:.2f} → {post['fRef']:.2f} Hz; engine told {seq[:5]}")
    # without the fix (a preset from before Stage H has no reference): built with the saved strike and mic, as before
    old = pg.evaluate("""() => { const s = JSON.parse(JSON.stringify(snapshot())); delete s.ref; window.__msgs.length = 0; const ok = restore(s);
      const st = window.__msgs.find(m => m.t === 'struct'); return { ok, mic: st && st.mic, hit: st && st.hit, want: [s.micIdx, s.hitIdx] }; }""")
    pg.wait_for_timeout(1200)
    f_old = pg.evaluate("state.info.fRef")
    check('a preset saved before this stage still loads, built as before; its tuning shows the octave problem the reference fixes',
          old['ok'] and [old['mic'], old['hit']] == old['want'] and abs(f_old - pre['fRef']) > 0.2 * pre['fRef'],
          f"built with mic/strike {old['mic']}/{old['hit']}; reference mode {f_old:.2f} Hz vs {pre['fRef']:.2f} Hz with the reference")
    # spectrum and axis from a preset reach the engine and the chips
    sp = pg.evaluate("""() => { const s = JSON.parse(JSON.stringify(snapshot())); s.spec = 3; s.axis = 0; window.__msgs.length = 0; restore(s);
      return { spec: window.__msgs.filter(m => m.t === 'spec').map(m => m.v), axis: state.axis, chip: [...document.querySelectorAll('#axes .chip')].findIndex(c => c.getAttribute('aria-pressed') === 'true'),
               mic: window.__msgs.filter(m => m.t === 'mic').map(m => m.a) }; }""")
    check('loading a preset sets its spectrum in the engine and keeps Mic axis X', sp['spec'] == [3] and sp['axis'] == 0 and sp['chip'] == 0 and sp['mic'] == [0], json.dumps(sp))
    check('no script errors', not errs, str(errs[:3]))
    c.close(); b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage H browser checks pass')
sys.exit(1 if failed else 0)
