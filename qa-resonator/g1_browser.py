# Stage G (video with sound) — browser checks. Chromium by default; --browser=webkit for Safari's engine.
#   python3 qa-resonator/g1_browser.py [repo_root] [--browser=webkit]
# Records a few seconds while playing, then checks the file itself: in the page (the browser decodes its
# own recording: picture size, sound level) and, when ffprobe is installed, with ffprobe/ffmpeg
# (streams, codecs, duration, sound level, a frame that is not black).
import sys, os, json, base64, shutil, subprocess, threading, functools, http.server, tempfile
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if not a.startswith('--')]
ROOT = os.path.abspath(argv[0] if argv else os.path.join(os.path.dirname(__file__), '..'))
BROWSER = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--browser=')), 'chromium')
PAGE = 'apps/resonator-next.html'
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
failed = 0
def check(name, ok, detail='', critical=True):
    global failed
    s = 'PASS' if ok else ('FAIL' if critical else 'NOTE')
    print(f'{s} {name}' + (f' — {detail}' if detail else ''), flush=True); failed += 0 if ok or not critical else 1

PLAY = """async (secs) => { const pads = [...document.querySelectorAll('#pads .pad')]; const t = performance.now(); let i = 0;
  while (performance.now() - t < secs * 1000) { const p = pads[(i++ * 5) % pads.length];
    p.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); p.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
    await new Promise(r => setTimeout(r, 300)); } }"""
DECODE = """async () => { const b = VREC.blob; const out = { size: b.size, type: b.type };
  try { const u = URL.createObjectURL(b), v = document.createElement('video'); v.muted = true; v.src = u;
    await new Promise((res, rej) => { v.onloadedmetadata = res; v.onerror = () => rej(new Error('video error')); setTimeout(() => rej(new Error('timeout')), 8000); });
    out.w = v.videoWidth; out.h = v.videoHeight; URL.revokeObjectURL(u); } catch (e) { out.videoErr = String(e.message || e); }
  try { const ab = await b.arrayBuffer(); const buf = await ctx.decodeAudioData(ab.slice(0)); let pk = 0;
    for (let c = 0; c < buf.numberOfChannels; c++) for (const s of buf.getChannelData(c)) pk = Math.max(pk, Math.abs(s));
    out.audioPk = pk; out.audioSecs = buf.duration; out.channels = buf.numberOfChannels; } catch (e) { out.audioErr = String(e.message || e); }
  out.b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(String(fr.result).split(',')[1]); fr.readAsDataURL(b); });
  return out; }"""

with sync_playwright() as p:
    if BROWSER == 'webkit':
        b = p.webkit.launch(); dev = dict(p.devices['iPhone 13']); dev.pop('default_browser_type', None)
    else:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        dev = {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True}
    c = b.new_context(accept_downloads=True, **dev); pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400)
    pg.tap('#start'); pg.wait_for_timeout(1800)
    pg.tap('.tab[data-page=strike]'); pg.wait_for_timeout(200)
    why = pg.evaluate('vrecWhyNot()')
    check('Record video and Save video are on the Strike tab', pg.is_visible('#vrecbtn') and not pg.is_visible('#vreclink'))
    if why:
        check(f'{BROWSER} can record video here', False, why, critical=(BROWSER == 'chromium'))
    else:
        pg.tap('#vrecbtn'); pg.wait_for_timeout(300)
        lab = pg.inner_text('#vrecbtn')
        check('Record video starts and shows the time', lab.startswith('Stop video'), lab)
        pg.evaluate(PLAY, 4.0)
        frame_ok = pg.evaluate("(() => { const d = g2.getImageData(Math.round((W-58)*devicePixelRatio), Math.round(18*devicePixelRatio), 1, 1).data; return d[0] > 180 && d[1] < 140; })()")
        check('a red recording dot is drawn on the 3D view (it lands in the video)', frame_ok)
        pg.tap('#vrecbtn'); pg.wait_for_timeout(2600)
        d = pg.evaluate(DECODE)
        link = pg.inner_text('#vreclink') if pg.is_visible('#vreclink') else ''
        check('stopping gives a Save video button with the size', link.startswith('Save video ·') and d['size'] > 20000, f"{link} · {d['type']} · {d['size']} bytes")
        check('the browser plays its own recording: the picture has the 3D view\'s size', d.get('w', 0) > 100 and d.get('h', 0) > 100, json.dumps({k: d.get(k) for k in ['w', 'h', 'videoErr']}))
        check('the recording carries the sound (decoded level)', d.get('audioPk', 0) > 0.05 and not d.get('audioErr'), json.dumps({k: d.get(k) for k in ['audioPk', 'audioSecs', 'channels', 'audioErr']}))
        # the file itself, with ffprobe / ffmpeg when available
        if shutil.which('ffprobe') and shutil.which('ffmpeg'):
            tmp = tempfile.mkdtemp(); ext = 'mp4' if 'mp4' in d['type'] else 'webm'; f = os.path.join(tmp, 'rec.' + ext)
            open(f, 'wb').write(base64.b64decode(d['b64']))
            pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', f], capture_output=True, text=True).stdout or '{}')
            st = pr.get('streams', []); v = [x for x in st if x.get('codec_type') == 'video']; a = [x for x in st if x.get('codec_type') == 'audio']
            # MediaRecorder's WebM often has no duration in its header; count it from the decoded audio instead
            wav = os.path.join(tmp, 'a.wav'); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f, '-vn', '-ac', '1', '-ar', '16000', '-f', 'wav', wav])
            import wave, array
            secs, pk = 0, 0
            if os.path.exists(wav):
                with wave.open(wav) as w: n = w.getnframes(); data = array.array('h', w.readframes(n)); secs = n / 16000; pk = max(abs(x) for x in data) / 32768 if data else 0
            check('ffprobe: one video stream and one audio stream', len(v) == 1 and len(a) == 1, f"video {[x.get('codec_name') for x in v]} {v[0].get('width') if v else ''}x{v[0].get('height') if v else ''} · audio {[x.get('codec_name') for x in a]}")
            check('ffmpeg: about 4 s long, and the sound is in it', 3.0 <= secs <= 6.5 and pk > 0.05, f'{secs:.2f} s of audio, peak {pk:.3f}')
            png = os.path.join(tmp, 'f.png'); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', f, '-frames:v', '1', png])
            # full resolution: the balls and caption are small, a downscale averages them away (measured: 0.06%
            # bright at 64 px wide vs 0.9% at full size for the same frame)
            bright, mean, sd = 0, 0, 0
            if os.path.exists(png):
                g = subprocess.run(['ffmpeg', '-v', 'error', '-i', png, '-vf', 'format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
                if g:
                    import statistics
                    bright = sum(1 for x in g if x > 120) / len(g); mean = sum(g) / len(g); sd = statistics.pstdev(g)
            check('a frame 2 s in shows the body (bright detail, structure, not black)', bright > 0.002 and sd > 5 and mean > 3,
                  f'{100 * bright:.2f}% bright pixels · mean {mean:.1f} · spread {sd:.1f}')
        else:
            check('ffprobe available for the file checks', False, 'not installed here; in-browser checks above still ran', critical=False)
        # saving: the share sheet where there is one, otherwise a download
        if BROWSER == 'chromium':
            with pg.expect_download(timeout=8000) as dl:
                pg.tap('#vreclink')
            name = dl.value.suggested_filename
            check('Save video hands over a named file', name.startswith('resonator-') and (name.endswith('.webm') or name.endswith('.mp4')), name)
        # it still plays afterwards, and the time limit stops a recording by itself
        pg.evaluate('VREC.max = 2'); pg.tap('#vrecbtn'); pg.wait_for_timeout(3200)
        check('a recording stops by itself at the time limit', not pg.evaluate('VREC.on') and pg.inner_text('#vrecbtn') == 'Record video')
        pk = pg.evaluate("""async () => { const an = ctx.createAnalyser(); (master || node).connect(an); const buf = new Float32Array(2048); let pk = 0;
          const pad = document.querySelector('#pads .pad'); pad.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); pad.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
          for (let i = 0; i < 30; i++) { await new Promise(r => setTimeout(r, 25)); an.getFloatTimeDomainData(buf); for (const v of buf) pk = Math.max(pk, Math.abs(v)); } return pk; }""")
        check('the instrument still plays after recording', pk > 0.05, f'peak {pk:.3f}')
    check('no script errors', not errs, str(errs[:3]))
    c.close()
    # a browser without MediaRecorder: the page says so instead of failing
    c = b.new_context(**dev); c.add_init_script('delete window.MediaRecorder; window.MediaRecorder = undefined;'); pg = c.new_page(); errs2 = []
    pg.on('pageerror', lambda e: errs2.append(str(e))); pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto(f'http://127.0.0.1:{PORT}/{PAGE}'); pg.wait_for_timeout(400); pg.tap('#start'); pg.wait_for_timeout(1500)
    pg.tap('.tab[data-page=strike]'); pg.tap('#vrecbtn'); pg.wait_for_timeout(300)
    note = pg.inner_text('#vrecnote')
    check('without MediaRecorder the page explains instead of failing', 'cannot record video' in note and not errs2, note)
    c.close(); b.close()
srv.shutdown()
print(f'\n{failed} check(s) FAILED' if failed else '\nall Stage G browser checks pass')
sys.exit(1 if failed else 0)
