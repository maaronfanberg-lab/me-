import http.server, threading, functools
from playwright.sync_api import sync_playwright
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory='/home/claude/me-'); H.log_message=lambda *a:None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8767), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    for f in ['resonator-orig-tmp.html', 'resonator.html']:
        pg = b.new_page(); pg.route('**/fonts.g*/**', lambda r: r.abort())
        pg.goto(f'http://127.0.0.1:8767/apps/{f}'); pg.wait_for_timeout(300)
        pg.click('#start'); pg.wait_for_timeout(2000)
        pg.evaluate("play(0,0.9)"); pg.wait_for_timeout(600)
        pk = pg.evaluate("state.peak")
        xs = [pg.evaluate("benchOne(48000,14,1,'String').x") for _ in range(5)]
        xs.sort(); print(f, 'live peak after a note:', round(pk,3), ' realtime factor (median of 5):', round(xs[2],1))
        pg.close()
    b.close()
srv.shutdown()
