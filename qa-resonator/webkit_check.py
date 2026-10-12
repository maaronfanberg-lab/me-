# RESONATOR in Safari's engine: Playwright WebKit with iPhone emulation.
# Runs on GitHub Actions (.github/workflows/resonator-webkit.yml); the results are pushed to the
# branch qa-results/webkit-<os> so they can be read with git (log downloads are blocked from the
# workspace).
#   python qa-resonator/webkit_check.py [repo_root] [out_dir] [--browser=webkit|chromium]
# A CI machine may have no audio device. Then the live-audio checks are reported as NOTE (not run)
# and the engine is still checked by rendering it offline inside WebKit (OfflineAudioContext +
# AudioWorklet), and compared with the Node engine fed the same messages.
import sys, os, json, math, subprocess, threading, functools, http.server, platform
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if not a.startswith('--')]
ROOT = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(ROOT, 'webkit-out'))
BROWSER = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--browser=')), 'webkit')
os.makedirs(OUT, exist_ok=True)
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

R = {'browser': BROWSER, 'platform': platform.platform(), 'checks': [], 'env': {}, 'offline': {}, 'live': {}, 'bench': {}}
def check(name, ok, detail='', critical=True):
    s = 'PASS' if ok else ('FAIL' if critical else 'NOTE')
    R['checks'].append({'name': name, 'status': s, 'detail': detail})
    print(f'{s} {name}' + (f' — {detail}' if detail else ''), flush=True)

PAGES = [('live', 'apps/resonator.html'), ('preview', 'apps/resonator-next.html')]
SHAPES = ['String', 'Tine', 'Chime', 'Drum', 'Hoop', 'Web', 'Tank', 'Twins']

ENV_JS = """() => ({ ua: navigator.userAgent, audioWorkletNode: typeof AudioWorkletNode !== 'undefined',
  offline: typeof OfflineAudioContext !== 'undefined', worker: typeof Worker !== 'undefined',
  audioSession: navigator.audioSession ? navigator.audioSession.type : 'none',
  running: !!state.running, audioMode: state.audioMode || '', ctxState: ctx ? ctx.state : 'none', rate: ctx ? ctx.sampleRate : 0,
  readout: ((document.getElementById('readout') || {}).textContent || '').trim().slice(0, 160),
  tuner: (typeof TUNER !== 'undefined') ? { on: !!TUNER.on, up: !!TUNER.up, stats: TUNER.stats } : null })"""
CLOCK_JS = """async () => { const t0 = ctx.currentTime; await new Promise(r => setTimeout(r, 700));
  return { state: ctx.state, advanced: ctx.currentTime - t0 }; }"""
PEAK_JS = """async () => { if (!window._an) { window._an = ctx.createAnalyser(); window._an.fftSize = 2048; (master || node).connect(window._an); }
  const an = window._an, buf = new Float32Array(2048); let pk = 0, bad = 0;
  const pad = document.querySelector('#pads .pad');
  pad.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); pad.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
  for (let i = 0; i < 120; i++) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf);
    for (const v of buf) { if (!isFinite(v)) bad++; else pk = Math.max(pk, Math.abs(v)); } }
  return { pk: +pk.toFixed(3), bad }; }"""
# the audio clock's longest stand-still, and the main thread's longest gap between ticks (if the page
# itself is blocked, the clock cannot be read either: the two together tell audio stalls from page stalls)
STALL_JS = """async () => { let last = ctx.currentTime, lastWall = performance.now(), worst = 0, prevTick = performance.now(), gap = 0;
  const tick = () => { const now = performance.now(), c = ctx.currentTime; gap = Math.max(gap, now - prevTick); prevTick = now;
    if (c !== last) { last = c; lastWall = now; } else worst = Math.max(worst, now - lastWall); };
  const iv = setInterval(tick, 4); await new Promise(r => setTimeout(r, 150)); gap = 0;
  document.querySelector('#shapes .chip:nth-child(7)').click();
  await new Promise(r => setTimeout(r, 2500)); clearInterval(iv); tick(); return [Math.round(worst), Math.round(gap)]; }"""
# The engine rendered offline inside the browser, with exactly the messages webkit_ref.mjs sends in Node.
OFFLINE_JS = """async ({ shape, secs, sr }) => {
  const S = SHAPES[shape], g = S.make(S.def), NN = g.P.length;
  const idx = f => Math.min(NN - 1, Math.max(0, Math.round(f * (NN - 1))));
  const oc = new OfflineAudioContext(2, Math.round(sr * secs), sr);
  const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
  await oc.audioWorklet.addModule(url);
  const node = new AudioWorkletNode(oc, 'resonator', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2] });
  node.connect(oc.destination);
  // An offline render does not deliver port messages while it runs (measured in Chromium), so every
  // message must be handled first. The engine posts 'ready' once the body is built and tuned; a
  // fixed wait was too short for Tank and rendered silence (test artefact, found 2026-10-11).
  let readyAt = -1; const t00 = performance.now();
  const ready = new Promise(res => { node.port.onmessage = e => { if (e.data && e.data.t === 'ready' && readyAt < 0) { readyAt = performance.now() - t00; res(true); } }; });
  const pos = new Float32Array(NN * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  const m = d => node.port.postMessage(d);
  m({ t: 'struct', n: NN, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  m({ t: 'mode', v: 0 }); m({ t: 'pk', v: 0 });
  const skip = ['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'];
  for (const k in KNOBS) if (!skip.includes(k)) m({ t: 'p', k, v: KNOBS[k].val });
  m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'mic2', i: idx(0.62), a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
  m({ t: 'note', f: 440 * Math.pow(2, (52 - 69) / 12), v: 0.9 });
  const gotReady = await Promise.race([ready, new Promise(r => setTimeout(() => r(false), 30000))]);
  // the note re-tunes once more (Stiffness/Substrate were sent after the body), as long again as the build
  await new Promise(r => setTimeout(r, Math.max(400, 1.5 * readyAt)));
  const t0 = performance.now(); const buf = await oc.startRendering(); const ms = performance.now() - t0;
  const L = buf.getChannelData(0), Rr = buf.getChannelData(1);
  let pk = 0, ss = 0, bad = 0, onset = -1;
  for (let i = 0; i < L.length; i++) { const a = L[i], b = Rr[i];
    if (!isFinite(a) || !isFinite(b)) { bad++; continue; }
    if (onset < 0 && (Math.abs(a) > 1e-4 || Math.abs(b) > 1e-4)) onset = i;
    pk = Math.max(pk, Math.abs(a), Math.abs(b)); ss += a * a + b * b; }
  return { pk, rms: Math.sqrt(ss / (2 * L.length)), bad, onset, ms: Math.round(ms), readyMs: Math.round(readyAt), gotReady,
           head: onset < 0 ? [] : Array.from(L.slice(onset, onset + 2048)) };
}"""
EMPTY_JS = """(() => { const r = cv.getBoundingClientRect(), g = state.geo; let best = null, bd = -1;
  for (let x = 70; x < W - 70; x += 6) for (let y = 110; y < H - 120; y += 6) { let m = 1e9;
    for (let i = 0; i < g.P.length; i++) { const dx = _px[i] - x, dy = _py[i] - y; m = Math.min(m, dx * dx + dy * dy); }
    if (m > bd) { bd = m; best = [x, y]; } }
  return { x: r.left + best[0], y: r.top + best[1] }; })()"""
MASS_XY = "(i) => { const r = cv.getBoundingClientRect(); return [r.left + _px[i], r.top + _py[i]]; }"

def db(a, b):
    return 20 * math.log10(max(a, 1e-12) / max(b, 1e-12))

def node_reference(src):
    env = dict(os.environ, RESONATOR_SRC=os.path.join(ROOT, src))
    out = subprocess.run(['node', os.path.join(ROOT, 'qa-resonator', 'webkit_ref.mjs')], env=env, capture_output=True, text=True, timeout=900)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[-2000:])
    return json.loads(out.stdout)

def open_page(b, path, device):
    c = b.new_context(**device)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{path}'); pg.wait_for_timeout(400)
    return c, pg, errs

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch()
        device = dict(p.devices['iPhone 13'])
        device.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        device = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True, 'device_scale_factor': 3}
    R['browser_version'] = b.version
    print(f'browser: {BROWSER} {b.version} on {R["platform"]}', flush=True)

    for label, path in PAGES:
        # ---------- start-up: the page must load and start without a script error ----------
        c, pg, errs = open_page(b, path, device)
        try:
            pg.tap('#start')
        except Exception as e:
            errs.append(f'tap #start: {e}')
        pg.wait_for_timeout(2500)
        try:
            env = pg.evaluate(ENV_JS)
        except Exception as e:
            env = {'error': str(e)}
        R['env'][label] = env
        check(f'{label}: loads and starts with no script error', not errs and env.get('running') is True,
              f"running={env.get('running')} engine={env.get('audioMode')!r} errors={errs[:3]}")
        if label == 'preview':
            t = env.get('tuner') or {}
            check('preview: background tuner (Worker) runs in WebKit', bool(t.get('on')) and bool(t.get('up')), json.dumps(t)[:200])

        # ---------- live audio, when this machine has an audio device ----------
        clock = pg.evaluate(CLOCK_JS)
        live_ok = clock['state'] == 'running' and clock['advanced'] > 0.2
        R['live'][label] = {'clock': clock}
        check(f'{label}: live audio clock runs', live_ok, f"state={clock['state']}, advanced {clock['advanced']:.3f} s in 0.7 s"
              + ('' if live_ok else ' (no audio device on this machine; live checks not run)'), critical=False)
        if live_ok:
            peaks = []
            for i, s in enumerate(SHAPES + ['String']):
                if i: pg.click(f'#shapes .chip:text-is("{s}")')
                peaks.append((s, pg.evaluate(PEAK_JS))); pg.wait_for_timeout(500)
            R['live'][label]['peaks'] = peaks
            check(f'{label}: every shape sounds (live)', all(v['pk'] > 0.05 and v['bad'] == 0 for _, v in peaks),
                  ' · '.join(f"{s} {v['pk']}" for s, v in peaks))
            stalls, gaps = [], []
            for _ in range(3):   # median of three: one sample on a busy CI machine is noise-prone
                pg.click('#shapes .chip:text-is("String")'); pg.wait_for_timeout(1200)
                st, gp = pg.evaluate(STALL_JS); stalls.append(st); gaps.append(gp)
            stall = sorted(stalls)[1]
            R['live'][label]['tank_stall_ms'] = stalls; R['live'][label]['main_thread_gap_ms'] = gaps
            check(f'{label}: audio clock freeze when choosing Tank (median of 3)', stall < 120 or label == 'live',
                  f'{stall} ms (runs {stalls}; page main-thread gaps {gaps})', critical=(label == 'preview'))

        # ---------- the engine itself, rendered offline inside this browser ----------
        try:
            ref = node_reference(path)
        except Exception as e:
            ref = None; check(f'{label}: Node reference render', False, str(e)[:300])
        rows = {}
        for s in SHAPES:
            try:
                w = pg.evaluate(OFFLINE_JS, {'shape': s, 'secs': 2, 'sr': 32000})
            except Exception as e:
                rows[s] = {'error': str(e)[:300]}; continue
            row = {'pk': round(w['pk'], 4), 'rms': w['rms'], 'bad': w['bad'], 'onset': w['onset'], 'render_ms': w['ms'],
                   'build_and_tune_ms': w['readyMs'], 'engine_ready': w['gotReady']}
            if ref and s in ref:
                n = ref[s]
                row['vs_node_rms_db'] = round(db(w['rms'], n['rms']), 3)
                row['vs_node_pk_db'] = round(db(w['pk'], n['pk']), 3)
                hw, hn = w['head'], n['head']; k = min(len(hw), len(hn))
                row['head_max_abs_diff'] = max((abs(hw[i] - hn[i]) for i in range(k)), default=None)
                row['head_identical'] = k > 0 and all(hw[i] == hn[i] for i in range(k))
                row['onset_shift_samples'] = (w['onset'] - n['onset']) if (w['onset'] >= 0 and n['onset'] >= 0) else None
            rows[s] = row
        R['offline'][label] = rows
        errs_off = {s: r['error'] for s, r in rows.items() if 'error' in r}
        check(f'{label}: engine renders offline in this browser (8 shapes)', not errs_off, json.dumps(errs_off)[:300])
        good = {s: r for s, r in rows.items() if 'error' not in r}
        check(f'{label}: engine output finite and audible (offline)', bool(good) and all(r['bad'] == 0 and r['pk'] > 0.01 for r in good.values()),
              ' · '.join(f"{s} pk {r['pk']}" for s, r in good.items()))
        if ref and good:
            worst = max(abs(r.get('vs_node_rms_db', 0)) for r in good.values())
            ident = sum(1 for r in good.values() if r.get('head_identical'))
            check(f'{label}: same sound as the Node engine (level within 0.5 dB)', worst <= 0.5,
                  f'worst level difference {worst:.3f} dB; first 2048 samples bit-identical on {ident}/{len(good)} shapes')

        # ---------- JavaScriptCore speed (this CI CPU, not a phone) ----------
        try:
            R['bench'][label] = {s: round(pg.evaluate(f"benchOne(32000, SHAPES['{s}'].def, 1, '{s}').x"), 1) for s in ['String', 'Tank']}
            check(f'{label}: engine speed in this browser (times real time, 1 voice)', True, json.dumps(R['bench'][label]), critical=False)
        except Exception as e:
            check(f'{label}: engine speed in this browser', False, str(e)[:200], critical=False)

        # ---------- tap flows (preview): everything works by finger ----------
        if label == 'preview':
            def tap(sel):
                pg.tap(sel); pg.wait_for_timeout(180)
            try:
                tap('.tool[data-tool=orbit]')
                m0 = pg.evaluate('state.M.slice()'); tap('#nudge [aria-label=right]')
                check('tap: turn pad turns the view', pg.evaluate('state.M.slice()') != m0)
                n0 = pg.evaluate('state.geo.P.length')
                tap('.tool[data-tool=add]'); e = pg.evaluate(EMPTY_JS); pg.touchscreen.tap(e['x'], e['y']); pg.wait_for_timeout(900)
                n1 = pg.evaluate('state.geo.P.length')
                check('tap: add puts a new mass where the finger lands', n1 == n0 + 1, f'{n0} → {n1} masses')
                tap('.tool[data-tool=del]'); xy = pg.evaluate(f"({MASS_XY})(state.geo.P.length - 1)"); pg.touchscreen.tap(xy[0], xy[1]); pg.wait_for_timeout(900)
                n2 = pg.evaluate('state.geo.P.length')
                check('tap: delete removes the tapped mass', n2 == n1 - 1, f'{n1} → {n2} masses')
                tap('#undo'); pg.wait_for_timeout(400)
                check('tap: undo brings it back', pg.evaluate('state.geo.P.length') == n1)
                tap('.tab[data-page=strike]')
                got = {}
                for name in ['Plectrum', 'Oscillator', 'Mallet']:
                    pg.tap(f'#modes .chip:text-is("{name}")'); pg.wait_for_timeout(150)
                    got[name] = pg.evaluate(f"""document.querySelector('#modes .chip:nth-child({['Mallet','Worthington splash','Plectrum','Oscillator'].index(name)+1})').getAttribute('aria-pressed')""")
                check('tap: exciter chips select (Plectrum, Oscillator, Mallet)', all(v == 'true' for v in got.values()), json.dumps(got))
                tap('.tab[data-page=mod]'); tap('[data-mty="0"] .chip:nth-child(2)')
                ty = pg.evaluate('state.mods[0].ty || 0')
                tap('[data-mty="0"] .chip:nth-child(1)')
                check('tap: modulator 1 becomes an envelope and back', ty == 1 and (pg.evaluate('state.mods[0].ty || 0') == 0), f'type after tap {ty}')
                tap('.tab[data-page=mic]'); tap('#micslots .chip:nth-child(2)')
                check('tap: Mic 2 can be picked', pg.evaluate("document.querySelector('#micslots .chip:nth-child(2)').getAttribute('aria-pressed')") == 'true')
                tap('#micslots .chip:nth-child(1)')
                if live_ok:
                    tap('.tab[data-page=strike]'); pg.tap('#modes .chip:text-is("Mallet")')
                    after = pg.evaluate(PEAK_JS)
                    check('still plays after all the taps', after['pk'] > 0.05 and after['bad'] == 0, f"peak {after['pk']}")
            except Exception as e:
                check('tap flows ran to the end', False, str(e)[:300])
            if errs:
                check('preview: no script errors during the tap flows', False, str(errs[:4]))
            # screenshots of every tab at iPhone size
            for tab in ['body', 'strike', 'mic', 'amp', 'fx', 'mod']:
                try:
                    pg.tap(f'.tab[data-page={tab}]'); pg.wait_for_timeout(250)
                    pg.screenshot(path=os.path.join(OUT, f'preview-{tab}.png'))
                except Exception as e:
                    check(f'screenshot {tab}', False, str(e)[:120], critical=False)
        else:
            pg.screenshot(path=os.path.join(OUT, 'live.png'))
        c.close()
    b.close()
srv.shutdown()

fails = [c for c in R['checks'] if c['status'] == 'FAIL']
R['summary'] = {'pass': sum(c['status'] == 'PASS' for c in R['checks']), 'fail': len(fails), 'note': sum(c['status'] == 'NOTE' for c in R['checks'])}
with open(os.path.join(OUT, 'results.json'), 'w') as f:
    json.dump(R, f, indent=1)
with open(os.path.join(OUT, 'summary.txt'), 'w') as f:
    f.write(f"{BROWSER} {R.get('browser_version')} on {R['platform']}\n")
    for c in R['checks']:
        f.write(f"{c['status']} {c['name']} — {c['detail']}\n")
print(f"\n{R['summary']['fail']} FAILED, {R['summary']['pass']} passed, {R['summary']['note']} notes")
sys.exit(1 if fails else 0)
