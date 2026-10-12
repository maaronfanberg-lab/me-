# Stage G, refinement (preview): while recording, paint the stage's gradient into the canvas itself.
# On screen the gradient is a CSS background behind a transparent canvas, so the video showed black
# there; WebKit has also had trouble with transparent pixels in canvas capture (bug 181663 thread,
# 2022-05-16). An opaque background avoids both. Edits apps/resonator-next.html; aborts on mismatch.
import sys
P = sys.argv[1]; s = open(P, encoding='utf-8').read()
def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count: sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)
rep("state._lastDraw=ts;g2.clearRect(0,0,W,H);", "state._lastDraw=ts;g2.clearRect(0,0,W,H);if(VREC.on)vrecBg();")
rep("// drawn on top of the 3D view while recording:",
    "// G: the same gradient as the stage's CSS background (#stage), painted into the canvas while recording\n"
    "function vrecBg(){ const gr=g2.createRadialGradient(W*0.5,H*0.34,0,W*0.5,H*0.34,Math.hypot(W,H)*0.65);\n"
    " gr.addColorStop(0,'#16233F'); gr.addColorStop(0.55,'#0A1120'); gr.addColorStop(1,'#05080F'); g2.fillStyle=gr; g2.fillRect(0,0,W,H); }\n"
    "// drawn on top of the 3D view while recording:")
open(P, 'w', encoding='utf-8').write(s); print('patched OK')
