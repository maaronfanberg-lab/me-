import http.server, threading, functools, json
from playwright.sync_api import sync_playwright
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory='/home/claude/me-'); H.log_message=lambda *a:None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8772), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
JS = """async(label)=>{ if(!window._an){window._an=ctx.createAnalyser();window._an.fftSize=2048;(master||node).connect(window._an);}
  const an=window._an,buf=new Float32Array(2048);let pk=0;play(0,0.9);
  for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,25));an.getFloatTimeDomainData(buf);for(const v of buf)pk=Math.max(pk,Math.abs(v));}
  return {label,pk:+pk.toFixed(4),shape:state.shape,n:state.n,u:(window.RESONATOR_DIAG||[]).length};}"""
with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    pg = b.new_page(); msgs=[]
    pg.on('console', lambda m: msgs.append(m.text))
    pg.route('**/fonts.g*/**', lambda r: r.abort())
    pg.goto('http://127.0.0.1:8772/apps/resonator.html'); pg.wait_for_timeout(300)
    pg.click('#start'); pg.wait_for_timeout(2000)
    print(pg.evaluate(JS, 'String first'))
    pg.click('#shapes .chip:text-is("Tank")'); pg.wait_for_timeout(600)
    print(pg.evaluate(JS, 'Tank'))
    for s in ['String','Chime']:
        pg.click(f'#shapes .chip:text-is("{s}")'); pg.wait_for_timeout(600)
        print(pg.evaluate(JS, s+' after Tank'))
    print('console:', [m for m in msgs if 'net::' not in m][-8:])
    b.close()
srv.shutdown()
