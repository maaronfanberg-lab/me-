import http.server, threading, functools, sys
from playwright.sync_api import sync_playwright
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory='/home/claude/me-'); H.log_message=lambda *a:None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8766), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    for f in ['resonator-orig-tmp.html', 'resonator.html']:
        pg = b.new_page(viewport={'width':390,'height':844}); errs=[]
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.route('**/fonts.g*/**', lambda r: r.abort())
        pg.goto(f'http://127.0.0.1:8766/apps/{f}'); pg.wait_for_timeout(400)
        pg.click('#start'); pg.wait_for_timeout(2500)
        pg.click('text=Self-test'); pg.wait_for_timeout(25000)
        txt = pg.evaluate("document.getElementById('diag').textContent")
        print('=====', f, 'pageerrors:', errs); print(txt[-1800:])
        pg.close()
    b.close()
srv.shutdown()
