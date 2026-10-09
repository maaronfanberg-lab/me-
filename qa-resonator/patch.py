# Verified edits for RESONATOR fixes F1-F4. Every replacement must match exactly
# the expected number of times or the script aborts without writing anything.
import sys, re
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1, where=None):
    global s
    hay = s if where is None else where()
    n = hay.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:70]!r}')
    s = s.replace(old, new)

a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a)
W = s[a:b]
assert W.count('Math.random()') == 8, 'ABORT: worklet random count changed'

# ---------- F1: seeded PRNG, per instance, reset on every new structure ----------
W2 = W.replace('Math.random()', 'this.rnd()')
W2 = W2.replace(
    "    this.port.onmessage = e => this.msg(e.data);\n  }\n  msg(d){\n",
    "    // F1: seeded PRNG so the same input always gives the same output\n"
    "    this.seed0=0x2545F491; this.rs=this.seed0;\n"
    "    // F2/F3: level calibration and ceiling limiter (gain is exactly 1 below the ceiling)\n"
    "    this.lvl=1; this.limG=1; this.limC=0.8414; this.limRel=1-Math.exp(-1/(0.08*sampleRate));\n"
    "    this.port.onmessage = e => this.msg(e.data);\n  }\n"
    "  rnd(){ let t=(this.rs=(this.rs+0x6D2B79F5)|0); t=Math.imul(t^(t>>>15),1|t);\n"
    "    t=(t+Math.imul(t^(t>>>7),61|t))^t; return ((t^(t>>>14))>>>0)/4294967296; }\n"
    "  msg(d){\n", 1)
W2 = W2.replace("      case 'struct': this.build(d); break;\n",
    "      case 'struct': this.rs=this.seed0; this.build(d); break;\n"
    "      case 'seed': this.seed0=(d.v|0)||0x2545F491; this.rs=this.seed0; break;\n"
    "      case 'lvl': this.lvl=(d.v>0&&d.v<32)?d.v:1; break;\n", 1)
# ---------- F2 + F3: output stage ----------
old_out = "      L[k]=Math.max(-1.2,Math.min(1.2,ll)); if(R) R[k]=Math.max(-1.2,Math.min(1.2,rr));\n"
assert W2.count(old_out) == 1, 'ABORT: output line'
W2 = W2.replace(old_out,
    "      if(this.lvl!==1){ ll*=this.lvl; rr*=this.lvl; }          // F3: per-shape level calibration\n"
    "      if(!isFinite(ll)) ll=0; if(!isFinite(rr)) rr=0;\n"
    "      { const pk=Math.max(ll<0?-ll:ll, rr<0?-rr:rr); let g=this.limG;   // F2: ceiling limiter, -1 dBTP\n"
    "        if(g<1){ g+=(1-g)*this.limRel; if(g>0.99999) g=1; }\n"
    "        if(pk*g>this.limC) g=this.limC/pk;\n"
    "        this.limG=g; if(g<1){ ll*=g; rr*=g; } }\n"
    "      L[k]=ll; if(R) R[k]=rr;\n")
for tag in ['this.rnd()', "case 'lvl'", "case 'seed'", 'this.limC/pk']:
    assert tag in W2, 'ABORT: missing ' + tag
assert 'Math.random' not in W2, 'ABORT: random left in worklet'
s = s[:a] + W2 + s[b:]

# ---------- F3: main thread sends the shape's calibration ----------
rep("const RATE=v=>0.01*Math.pow(200000,v);",
    "// F3: per-shape output calibration to -21 LUFS at default settings (measured, see qa-resonator)\n"
    "const SHAPE_LVL={String:1.4928,Tine:0.8082,Chime:0.866,Drum:0.9784,Hoop:1.5171,Web:0.7379,Tank:8.8716,Twins:1.8793};\n"
    "const RATE=v=>0.01*Math.pow(200000,v);")
rep("function send(k){if(node)node.port.postMessage({t:'p',k,v:val[k]});}",
    "function send(k){if(node)node.port.postMessage({t:'p',k,v:val[k]});}\n"
    "function sendLvl(){if(node)node.port.postMessage({t:'lvl',v:SHAPE_LVL[state.shape]||1});}")
rep("   node.port.postMessage({t:'spec',v:state.spec||0});}",
    "   node.port.postMessage({t:'spec',v:state.spec||0});sendLvl();}")
rep("  node.port.postMessage({t:'mode',v:state.mode||0});\n  state.disp=new Float32Array(g.P.length*3);state.spd=new Float32Array(g.P.length);\n  drawInfo();\n}",
    "  node.port.postMessage({t:'mode',v:state.mode||0});\n  sendLvl();\n  state.disp=new Float32Array(g.P.length*3);state.spd=new Float32Array(g.P.length);\n  drawInfo();\n}")

# ---------- F4: tap path for orbit and move ----------
rep("#undo,#redo{font-size:14px;padding:6px 10px}",
    "#undo,#redo{font-size:14px;padding:6px 10px}\n"
    "#nudge{position:absolute;right:10px;top:52px;display:grid;grid-template-columns:repeat(3,40px);grid-template-rows:repeat(3,40px);gap:3px}\n"
    "#nudge[hidden]{display:none}\n"
    "#nudge .nb{appearance:none;border:1px solid rgba(74,88,122,.6);background:rgba(10,17,32,.8);color:var(--live);\n"
    "  font-family:var(--mono);font-size:16px;border-radius:3px;padding:0;cursor:pointer;touch-action:none;backdrop-filter:blur(8px)}\n"
    "#nudge .nb:active{border-color:var(--compress)}\n"
    "#nudge .nl{grid-column:2;grid-row:2;align-self:center;text-align:center;font-size:9px;color:var(--dim);pointer-events:none}\n"
    "#nudgeMsg{position:absolute;right:10px;top:182px;font-size:10px;color:var(--tension);pointer-events:none;text-shadow:0 1px 3px #000}")
rep('    <div id="tools">',
    '    <div id="nudge" hidden aria-label="Nudge">'
    '<button class="nb" data-nx="0" data-ny="-1" style="grid-column:2;grid-row:1" aria-label="up">&#9650;</button>'
    '<button class="nb" data-nx="-1" data-ny="0" style="grid-column:1;grid-row:2" aria-label="left">&#9664;</button>'
    '<span class="nl" id="nudgeLab">turn</span>'
    '<button class="nb" data-nx="1" data-ny="0" style="grid-column:3;grid-row:2" aria-label="right">&#9654;</button>'
    '<button class="nb" data-nx="0" data-ny="1" style="grid-column:2;grid-row:3" aria-label="down">&#9660;</button>'
    '</div><div id="nudgeMsg"></div>\n'
    '    <div id="tools">')
rep("  state.spin = state.tool==='orbit';\n};",
    "  state.spin = state.tool==='orbit';\n  syncNudge();\n};\n"
    "// F4: tap path for the two drag-only tools. Hold to repeat, like the knob steppers.\n"
    "const nudgeEl=document.getElementById('nudge'),nudgeMsg=document.getElementById('nudgeMsg');\n"
    "function syncNudge(){const on=state.tool==='orbit'||state.tool==='move';nudgeEl.hidden=!on;\n"
    " document.getElementById('nudgeLab').textContent=state.tool==='move'?'move':'turn';nudgeMsg.textContent='';}\n"
    "let nudgeMoved=false;\n"
    "function nudge(nx,ny){\n"
    " if(state.tool==='orbit'){state.spin=false;if(nx)camRotate(1,nx*0.12);if(ny)camRotate(0,ny*0.12);return true;}\n"
    " if(state.tool!=='move')return false;\n"
    " const g=state.geo,i=state.sel;\n"
    " if(!g||i<0||i>=g.P.length){nudgeMsg.textContent='tap a mass first';return false;}\n"
    " if(!nudgeMoved){geoPush();nudgeMoved=true;}\n"
    " const {R,U}=camBasis(),st=0.012,p=g.P[i];\n"
    " for(let a=0;a<3;a++)p[a]=Math.max(-0.6,Math.min(0.6,p[a]+(R[a]*nx+U[a]*ny)*st));\n"
    " if(node)node.port.postMessage({t:'mv',i,x:p[0],y:p[1],z:p[2]});\n"
    " return true;\n"
    "}\n"
    "for(const nb of nudgeEl.querySelectorAll('.nb')){\n"
    " const nx=+nb.dataset.nx,ny=+nb.dataset.ny;let timer=null,held=0;\n"
    " const stop=()=>{if(timer){clearInterval(timer);timer=null;}held=0;if(nudgeMoved){nudgeMoved=false;drawInfo();}};\n"
    " const start=()=>{if(!nudge(nx,ny))return;held=0;timer=setInterval(()=>{held++;const n=held>14?3:held>6?2:1;for(let q=0;q<n;q++)nudge(nx,ny);},90);};\n"
    " nb.addEventListener('pointerdown',e=>{e.preventDefault();if(!timer)start();});\n"
    " nb.addEventListener('pointerup',stop);nb.addEventListener('pointerleave',stop);nb.addEventListener('pointercancel',stop);\n"
    " nb.addEventListener('touchstart',e=>{e.preventDefault();if(!timer)start();},{passive:false});\n"
    " nb.addEventListener('touchend',stop,{passive:true});nb.addEventListener('touchcancel',stop,{passive:true});\n"
    " nb.addEventListener('click',e=>e.preventDefault());\n"
    " nb.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();nudge(nx,ny);if(nudgeMoved){nudgeMoved=false;drawInfo();}}});\n"
    "}\n"
    "syncNudge();")
open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
