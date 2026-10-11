# Stage 4 (preview): up to three extra mics (Mics 2–4), each a clean point pickup with its own level and
# pan. Edits apps/resonator-next.html in place; aborts on any mismatch.
#
# Tried and withdrawn: a pickup-coil aperture that followed the springs on hand-edited bodies. Measured,
# switching it on at the first edit changed the main pickup's sound by itself (up to +14 dB and a 56%
# brightness shift in pickup modes 1–2) even when the edit changed nothing physical. The coil stays the
# live page's coil (masses counted by number) — see docs/research/resonator-stage4-mics-2026-10-11.md.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1, where='page'):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT ({where}): expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)

def eng(old, new):
    global s
    assert '`' not in new and '${' not in new, 'ABORT: template characters in engine edit'
    a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a); seg = s[a:b]
    if seg.count(old) != 1:
        sys.exit(f'ABORT (engine): expected 1 match, found {seg.count(old)}: {old[:90]!r}')
    s = s[:a] + seg.replace(old, new) + s[b:]

# ---------------- engine ----------------
eng("    this.windA=1-Math.exp(-2*Math.PI*400/sampleRate);",
    "    this.windA=1-Math.exp(-2*Math.PI*400/sampleRate);\n"
    "    // S4: up to three extra point mics (clean room mics), each with its own level and pan\n"
    "    this.xmN=0; this.xmI=new Int32Array([-1,-1,-1]); this.xmG=new Float64Array([0.7,0.7,0.7]); this.xmP=new Float64Array(3);\n"
    "    this.xmVec=[[0,1,0],[0,1,0],[0,1,0]]; this.xmLp=new Float64Array(24); this.xmLpB=new Float64Array(24); this.xmDx=new Float64Array(3); this.xmDy=new Float64Array(3);\n"
    "    this.xmT=new Int32Array(24); this.xmS=new Int32Array(24); this.xmK=new Float64Array(24); this.xmX=new Float64Array(24); this.xmY=new Float64Array(24); this.xmZ=new Float64Array(24);\n"
    "    this.xmGL=new Float64Array(3); this.xmGR=new Float64Array(3);")
eng("      case 'asyncCal': this.asyncCal=!!d.v; break;",
    "      case 'asyncCal': this.asyncCal=!!d.v; break;\n"
    "      case 'xmic': { const q=d.k|0; if(q<0||q>2) break;   // S4: place / move / remove an extra mic\n"
    "        this.xmI[q]=(d.i>=0&&d.i<this.N&&!(this.fixed&&this.fixed[d.i]))?d.i:-1;\n"
    "        if(d.g!=null) this.xmG[q]=d.g; if(d.p!=null) this.xmP[q]=d.p;\n"
    "        this.xmN=(this.xmI[0]>=0)+(this.xmI[1]>=0)+(this.xmI[2]>=0); this.vectors(); break; }")
eng("    if(this.micJ>=N||(this.micJ>=0&&this.fixed[this.micJ])) this.micJ=-1;   // S2: second mic re-placed if its mass is gone or pinned\n",
    "    if(this.micJ>=N||(this.micJ>=0&&this.fixed[this.micJ])) this.micJ=-1;   // S2: second mic re-placed if its mass is gone or pinned\n"
    "    for(let q=0;q<3;q++) if(this.xmI[q]>=N||(this.xmI[q]>=0&&this.fixed[this.xmI[q]])) this.xmI[q]=-1;   // S4\n"
    "    this.xmN=(this.xmI[0]>=0)+(this.xmI[1]>=0)+(this.xmI[2]>=0); this.xmLp.fill(0); this.xmLpB.fill(0); this.xmDx.fill(0); this.xmDy.fill(0);\n")
eng("    this.micVec2=mk(this.micJ>=0?this.micJ:this.micI,this.micA,AXM);",
    "    this.micVec2=mk(this.micJ>=0?this.micJ:this.micI,this.micA,AXM);\n"
    "    for(let q=0;q<3;q++) if(this.xmI[q]>=0) this.xmVec[q]=mk(this.xmI[q],this.micA,AXM);   // S4")
eng("    if(pd) this.pitch();\n    for(let k=0;k<n;k++){\n      this.applyMods(true);",
    "    if(pd) this.pitch();\n"
    "    // S4: one tap per (extra mic, voice), built once per block (pitches and scale only change between blocks)\n"
    "    let nXT=0; const XT=this.xmT, XS=this.xmS, XK=this.xmK, XX=this.xmX, XY=this.xmY, XZ=this.xmZ, XL=this.xmLp, XB=this.xmLpB;\n"
    "    if(this.xmN){ const V=this.voices;\n"
    "      for(let q=0;q<3;q++){ if(this.xmI[q]<0) continue; const xi=this.xmI[q]*3, xv=this.xmVec[q];\n"
    "        const th=(Math.max(-1,Math.min(1,this.xmP[q]))+1)*Math.PI/4;   // constant-power pan, centre = unity\n"
    "        this.xmGL[q]=Math.cos(th)*1.4142135623730951; this.xmGR[q]=Math.sin(th)*1.4142135623730951;\n"
    "        for(let vv=0;vv<V;vv++){ XT[nXT]=vv*this.stride+xi; XS[nXT]=q*8+vv; XK[nXT]=V>1?1/(2*Math.PI*this.vf0[vv]*this.aChar):vk;\n"
    "          XX[nXT]=xv[0]; XY[nXT]=xv[1]; XZ[nXT]=xv[2]; nXT++; } } }\n"
    "    for(let k=0;k<n;k++){\n      this.applyMods(true);")
eng("      for(let s=0;s<os;s++){ this.advance(1);\n        if(this.voices>1){",
    "      for(let s=0;s<os;s++){ this.advance(1);\n"
    "        if(nXT){ const vel=this.vel;   // S4: extra mics hear every voice\n"
    "          for(let t=0;t<nXT;t++){ const vb=XT[t], s8=XS[t], rx=(vel[vb]*XX[t]+vel[vb+1]*XY[t]+vel[vb+2]*XZ[t])*XK[t];\n"
    "            XL[s8]+=g*(rx-XL[s8]); XB[s8]+=g*(XL[s8]-XB[s8]); } }\n"
    "        if(this.voices>1){")
eng("        ll=o*a+o2*b; rr=o2*a+o*b;\n      }\n      if(this.fxLive()||this.spLive()){",
    "        ll=o*a+o2*b; rr=o2*a+o*b;\n      }\n"
    "      if(this.xmN){   // S4: extra mics, each a clean point pickup with its own level and pan\n"
    "        const V=this.voices, nrm=V>1?1/Math.sqrt(V):1;\n"
    "        for(let q=0;q<3;q++){ if(this.xmI[q]<0) continue; const xi=this.xmI[q]*3, xv=this.xmVec[q]; let sv=0, sd=0;\n"
    "          for(let vv=0;vv<V;vv++){ const vb=vv*this.stride+xi; sv+=this.xmLpB[q*8+vv];\n"
    "            sd+=((this.pos[vb]-this.rest[vb])*xv[0]+(this.pos[vb+1]-this.rest[vb+1])*xv[1]+(this.pos[vb+2]-this.rest[vb+2])*xv[2])*dispK; }\n"
    "          let x3=((1-this.blend)*sv+this.blend*sd)*nrm; if(!isFinite(x3)) x3=0;\n"
    "          const y3=x3-this.xmDx[q]+0.9985*this.xmDy[q]; this.xmDx[q]=x3; this.xmDy[q]=y3;\n"
    "          let o3=Math.tanh(y3*this.gain*13)*this.gate*this.xmG[q]; if(!isFinite(o3)) o3=0;\n"
    "          ll+=o3*this.xmGL[q]; rr+=o3*this.xmGR[q]; }\n"
    "      }\n"
    "      if(this.fxLive()||this.spLive()){")

# ---------------- page ----------------
rep(" inGain:{label:'Mic input',",
    " xLevel:{label:'Extra mic level',min:0,max:1.5,step:0.01,val:0.7,fmt:v=>Math.round(v*100)+'%',hint:'Level of the mic picked above (Mic 2, 3 or 4).'},\n"
    " xPan:{label:'Extra mic pan',min:-1,max:1,step:0.02,val:0,fmt:v=>v<-0.03?'L '+Math.round(-v*100):v>0.03?'R '+Math.round(v*100):'centre',hint:'Where the mic picked above sits between your ears.'},\n"
    " inGain:{label:'Mic input',")
rep('      <div class="knob" data-k="width"></div>\n',
    '      <div class="knob" data-k="width"></div>\n'
    '      <div class="secttl">More mics</div>\n'
    '      <div class="row" id="micslots"></div>\n'
    '      <div class="knob" data-k="xLevel"></div>\n'
    '      <div class="knob" data-k="xPan"></div>\n'
    '      <div class="row"><button class="chip" id="xmremove">Remove this mic</button></div>\n'
    '      <div class="hint" id="xmhint" style="display:block"></div>\n')
XM = r'''
// ---- S4: extra mics ---------------------------------------------------------------------
// Mic 1 is the main pickup (with the Amp tab's pickups, amp and cabinet). Mics 2–4 are clean point
// pickups placed with the mic tool, each with its own level and pan.
state.xm=[{i:-1,g:0.7,p:-0.6},{i:-1,g:0.7,p:0.6},{i:-1,g:0.7,p:0}]; state.micSlot=0;
function xmSend(q){ if(node){ const x=state.xm[q]; node.port.postMessage({t:'xmic',k:q,i:x.i,g:x.g,p:x.p}); } }
function xmSendAll(){ for(let q=0;q<3;q++) xmSend(q); }
const micSlotsEl=document.getElementById('micslots');
function syncMicSlots(){
  [...micSlotsEl.children].forEach((c,j)=>{ c.setAttribute('aria-pressed',String(j===state.micSlot)); c.textContent='Mic '+(j+1)+(j>0&&state.xm[j-1].i<0?' (off)':''); });
  const q=state.micSlot-1, hint=document.getElementById('xmhint');
  if(q>=0){ val.xLevel=state.xm[q].g; val.xPan=state.xm[q].p; syncKnob('xLevel'); syncKnob('xPan'); }
  hint.textContent=q<0?'Mic 1 is the main pickup: Level and the Amp tab shape it. Pick Mic 2, 3 or 4 to add more mics.'
    :(state.xm[q].i<0?'Now tap a ball with the mic tool (above the picture) to place Mic '+(q+2)+'.'
    :'Mic '+(q+2)+' is on ball #'+state.xm[q].i+'. Tap another ball with the mic tool to move it.');
}
for(let j=0;j<4;j++){ const b=document.createElement('button'); b.className='chip'; b.onclick=()=>{ state.micSlot=j; syncMicSlots(); }; micSlotsEl.appendChild(b); }
document.getElementById('xmremove').onclick=()=>{ const q=state.micSlot-1; if(q<0) return; state.xm[q].i=-1; xmSend(q); syncMicSlots(); };
for(const k of ['xLevel','xPan']){ const w=document.querySelector('.knob[data-k="'+k+'"] input');
  if(w) w.addEventListener('input',()=>{ const q=state.micSlot-1; if(q<0) return; if(k==='xLevel') state.xm[q].g=val.xLevel; else state.xm[q].p=val.xPan; xmSend(q); }); }
syncMicSlots();
'''
rep("document.getElementById('micin').onclick=micToggle;\n", "document.getElementById('micin').onclick=micToggle;\n" + XM)
rep("  if(state.tool==='mic'){\n    state.micIdx=i; state.sel=i;\n",
    "  if(state.tool==='mic'){\n"
    "    if(state.micSlot>0){ const q=state.micSlot-1; state.xm[q].i=i; state.sel=i; xmSend(q); syncMicSlots(); return; }   // S4: place an extra mic\n"
    "    state.micIdx=i; state.sel=i;\n")
rep(" mark(state.hitIdx,'#FF9A55','strike');mark(state.micIdx,'#4ED8EA','mic');",
    " mark(state.hitIdx,'#FF9A55','strike');mark(state.micIdx,'#4ED8EA','mic');\n"
    " if(state.xm) state.xm.forEach((x,q)=>{ if(x.i>=0) mark(x.i,'#A7F0C8','mic '+(q+2)); });   // S4")
# deleting a mass renumbers the masses after it: the extra mics follow (a mic on the deleted mass goes off)
rep("  g.P.splice(i,1); g.F=Uint8Array.from(Array.from(g.F).filter((_,k)=>k!==i)); g.S=S2;",
    "  g.P.splice(i,1); g.F=Uint8Array.from(Array.from(g.F).filter((_,k)=>k!==i)); g.S=S2;\n"
    "  if(state.xm) state.xm.forEach(x=>{ if(x.i===i) x.i=-1; else if(x.i>i) x.i--; });   // S4: extra mics follow the renumbering")
# every rebuild: the page drops an extra mic whose ball is gone or pinned (as the engine does) and re-sends
# all three, so page and engine never disagree (pin, link, add, delete, undo, presets)
rep("  sendLvl();\n  state.disp=new Float32Array(g.P.length*3);state.spd=new Float32Array(g.P.length);\n  drawInfo();\n}\nlet drag=null;",
    "  sendLvl();\n"
    "  if(state.xm){ state.xm.forEach(x=>{ if(x.i>=g.P.length||(x.i>=0&&g.F[x.i])) x.i=-1; }); xmSendAll(); syncMicSlots(); }   // S4: page mirrors the engine\n"
    "  state.disp=new Float32Array(g.P.length*3);state.spd=new Float32Array(g.P.length);\n  drawInfo();\n}\nlet drag=null;")
# undo/redo carry the extra mics with the body
rep("shape:g.shape||state.shape,n:g.n||state.n,axis:g.axis!=null?g.axis:state.axis};",
    "shape:g.shape||state.shape,n:g.n||state.n,axis:g.axis!=null?g.axis:state.axis,\n"
    "          xm:state.xm?state.xm.map(x=>x.i):null};   // S4: where the extra mics sit")
rep("  state.micIdx=s.mic; state.hitIdx=s.hit;\n",
    "  state.micIdx=s.mic; state.hitIdx=s.hit;\n"
    "  if(s.xm&&state.xm) s.xm.forEach((i,q)=>{ state.xm[q].i=i; });   // S4\n")
# a new shape starts with the extra mics off
rep("   node.port.postMessage({t:'spec',v:state.spec||0});sendLvl();}",
    "   node.port.postMessage({t:'spec',v:state.spec||0});sendLvl();if(state.xm){state.xm.forEach(x=>{x.i=-1;});xmSendAll();syncMicSlots();}}")
# presets remember the extra mics
rep("    mods:state.mods.map(m=>({d:m.d,sh:m.sh}))};",
    "    mods:state.mods.map(m=>({d:m.d,sh:m.sh})),xm:state.xm?state.xm.map(x=>({i:x.i,g:x.g,p:x.p})):null};")
rep("             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:'',shape:state.shape,n:state.n};   // S2",
    "             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:'',shape:state.shape,n:state.n};   // S2\n"
    "  if(state.xm) state.xm=o.xm?o.xm.map(x=>({i:x.i,g:x.g,p:x.p})):[{i:-1,g:0.7,p:-0.6},{i:-1,g:0.7,p:0.6},{i:-1,g:0.7,p:0}];   // S4")

open(P, 'w', encoding='utf-8').write(s)
print('patched', P)
