# Stage I (preview): Tank only. Page only; the engine source is not touched.
#  - Gone: OMEF (Attractor, Inference, Memory, Regimes, Coupling, Specialization and the effects it drove),
#    the other seven shapes, the exciters other than the mallet (splash, plectrum, oscillator, bow, wind,
#    phone mic in), Mics 2-4, the modulators, the Amp tab, feedback, space (distance, image, reflections,
#    Doppler, rotation, elevation), the plate reverb, WAV and video recording, the building tools, the
#    Learn tab and the factory presets, Self-test and Benchmark.
#  - Every removed control stays at its old default and is still sent to the engine exactly as before, so
#    the Tank sounds bit for bit as it did. Presets can no longer switch a removed feature back on.
#  - Decay is now called Sustain.
#  - The mic and strike circles on the body: press one and slide it, or tap it and then tap where it should
#    go. Anywhere else, a drag turns the view. No tool to pick first.
# Edits apps/resonator-next.html in place; aborts on any mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:100]!r}')
    s = s.replace(old, new)

def cut(start, end, keep_end=True, new=''):
    """remove from `start` (inclusive) up to `end` (exclusive unless keep_end=False); both must be unique"""
    global s
    for a in (start, end):
        if s.count(a) != 1:
            sys.exit(f'ABORT: anchor must be unique, found {s.count(a)}: {a[:100]!r}')
    i = s.index(start); j = s.index(end)
    if j <= i:
        sys.exit(f'ABORT: end before start: {start[:60]!r} .. {end[:60]!r}')
    if not keep_end: j += len(end)
    s = s[:i] + new + s[j:]

# ================================ markup ================================
rep('<div id="brand">RESONATOR · NEXT</div>', '<div id="brand">RESONATOR · TANK</div>')
cut('    <div id="tools">\n', '    <div id="level">output silent</div>',
    new='    <div id="tools">\n      <button class="tool" id="home">reset view</button>\n    </div>\n')
rep('''    <button class="tab" data-page="amp" aria-selected="false">Amp</button>
    <button class="tab" data-page="fx" aria-selected="false">FX</button>
    <button class="tab" data-page="mod" aria-selected="false">Mod</button>
    <button class="tab" data-page="learn" aria-selected="false">Learn</button>
''', '')
rep('<button class="chip" id="selftest">Self-test</button><button class="chip" id="bench">Benchmark</button>', '')

# Body: Sustain first; no shape choice, no OMEF, no specialization, no scramble
rep('''      <div class="secttl">Shape</div>
      <div class="row" id="shapes"></div>
      <div class="knob" data-k="size"></div>
      <div class="knob" data-k="ratio"></div>
      <div class="knob" data-k="decay"></div>
''', '''      <div class="knob" data-k="decay"></div>
      <div class="knob" data-k="size"></div>
      <div class="knob" data-k="ratio"></div>
''')
cut('      <div class="knob" data-k="coup"></div>\n', '      <div class="knob" data-k="tune"></div>\n')
cut('      <div class="row">\n        <button class="chip" id="scramble">', '    <section class="page" id="page-strike">',
    new='    </section>\n\n')

# Strike: the mallet only; Hush stays; no recording
cut('      <div class="secttl">Excitation</div>\n', '      <div class="knob" data-k="drive"></div>\n',
    new='      <div class="secttl">Mallet</div>\n')
cut('      <div class="secttl">Bow</div>\n', '      <div class="knob" data-k="hit"></div>\n')
cut('      <div class="secttl">Air and microphone</div>\n', '      <div class="secttl">Scale</div>\n')
rep('''        <button class="chip" id="bow" aria-pressed="false">Bow</button>
        <button class="chip" id="hush">Hush</button>''', '''        <button class="chip" id="hush">Hush</button>''')
cut('      <div class="secttl">Recording</div>\n', '    </section>\n\n    <section class="page" id="page-fx">')

# FX, Learn, Mod and Amp pages
cut('    <section class="page" id="page-fx">', '    <section class="page" id="page-mic">')

# Mic: one mic; no stereo second mic, no more mics, no feedback; Magnify stays
cut('      <div class="knob" data-k="width"></div>\n', '      <div class="knob" data-k="mag"></div>\n')

# Learn CSS
cut('.lintro{', '</style>')

# ================================ knobs ================================
rep("decay:{label:'Decay',min:0.08,max:26,step:0.02,val:4,fmt:v=>v.toFixed(1)+' s',hint:'How long the whole body takes to give up its energy.'},",
    "decay:{label:'Sustain',min:0.08,max:26,step:0.02,val:4,fmt:v=>'rings '+(1.25*v).toFixed(1)+' s',hint:'How long the tank keeps ringing after a strike, like holding down a piano\\'s sustain pedal. The time shown is how long it takes to fade to a hundredth of its strength (40 dB), measured on the Tank; more Damping shortens it a little.'},")

# ================================ state ================================
rep("const state={shape:'String',n:14,", "const state={shape:'Tank',n:7,")

# buildShape: no extra mics any more (the engine's are off by default, as before)
rep("node.port.postMessage({t:'spec',v:state.spec||0});sendLvl();if(state.xm){state.xm.forEach(x=>{x.i=-1;});xmSendAll();syncMicSlots();}}",
    "node.port.postMessage({t:'spec',v:state.spec||0});sendLvl();}")

# engine messages to the page: no modulator meters, recording or attractor orbit
rep("     if(d.mv||state.mvShown) modMeters(d.mv||null);   // S5\n", "")
cut("   } else if(d.t==='rec'){\n", "   } else if(d.t==='ready'){\n")

# Mic in (S3) and extra mics (S4)
cut('// ---- S3: Mic in ------', '// S1: one tap copies everything needed to debug on a phone')

# Copy report: always include the input counters (Self-test is gone)
rep("document.getElementById('copydiag').onclick=async()=>{\n  const s=TUNER.stats, g=state.geo;",
    "document.getElementById('copydiag').onclick=async()=>{\n  renderDiag();   // I: the input counters, always\n  const s=TUNER.stats, g=state.geo;")
rep("    '', (diagEl.textContent||'(tap Self-test or Benchmark first for more detail)'),",
    "    '', diagEl.textContent,")
rep("  'audio underruns  '+DIAG.under+'\\n'+",
    "  'body touches     '+DIAG.cvdown+' down · '+DIAG.cvmove+' moves · '+DIAG.ctouch+' as touch · mic/strike moved '+DIAG.mmoves+'\\n'+   // I\n  'audio underruns  '+DIAG.under+'\\n'+")
rep("const DIAG={errs:[],down:0,move:0,up:0,cancel:0,tdown:0,tmove:0,taps:0,sets:0,zeroWidth:0,under:0,err:''};",
    "const DIAG={errs:[],down:0,move:0,up:0,cancel:0,tdown:0,tmove:0,taps:0,sets:0,zeroWidth:0,under:0,err:'',cvdown:0,cvmove:0,ctouch:0,mmoves:0};")
cut("let diagTimer=null;\ndocument.getElementById('selftest').onclick=()=>{", "addEventListener('error',e=>{")

# modulators (S5 routing and UI)
cut('// ---------- modulator routing ----------', '// ---------- presets ----------')
rep("   else if(/^m[123]([ra]|at|dc|su|rl|fa|fr|se)$/.test(k)) sendMod(+k[1]-1);   // S5: envelope and follower knobs too\n", "")

# ================================ presets ================================
rep("""    pk:state.pk||0,mode:state.mode||0,spec:state.spec||0,micIdx:state.micIdx,hitIdx:state.hitIdx,""",
    """    pk:0,mode:0,spec:0,micIdx:state.micIdx,hitIdx:state.hitIdx,""")
rep("""    mods:state.mods.map(m=>({d:m.d,sh:m.sh,ty:m.ty||0,dn:m.dn||0,src:m.src||0})),xm:state.xm?state.xm.map(x=>({i:x.i,g:x.g,p:x.p})):null,
""", """    xm:null,
""")
cut('function restore(o){\n', '// H: a message that the readout\'s next redraw leaves alone', new=r"""// I: Tank only. The controls that are kept; every other control stays at its old default and is still sent
// to the engine as before, so the Tank sounds exactly as it did. A preset cannot switch a removed one back on.
const KEEP=new Set(['decay','size','ratio','loss','sub','voices','nl','tune','drive','hard','hit','angle','gain','mic','blend','bite','tone','mag']);
const tankPreset=o=>!!(o&&o.P&&(o.shape||'Tank')==='Tank');
function restore(o){
  if(!tankPreset(o)) return false;
  state.shape='Tank'; state.n=o.n||state.n;
  state.scale=o.scale||0; state.root=o.root||52; state.axis=(o.axis===0||o.axis===1||o.axis===2)?o.axis:1;   // H: X (0) is a real axis
  state.pk=0; state.mode=0; state.spec=0;   // I: one pickup, the mallet, no specialization: the old defaults
  for(const k in o.val) if(k in val&&KEEP.has(k)) val[k]=o.val[k];
  for(const k in KNOBS) if(!KEEP.has(k)) val[k]=KNOBS[k].val;   // I
  state.geo={P:o.P.map(p=>p.slice()),F:Uint8Array.from(o.F),S:o.S.map(s=>s.slice()),
             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:'',shape:state.shape,n:state.n};   // S2
  state.free=state.geo.P.map((_,i)=>i).filter(i=>!state.geo.F[i]);
  state.micIdx=o.micIdx; state.hitIdx=o.hitIdx;
  [...axesEl.children].forEach((c,j)=>c.setAttribute('aria-pressed',j===state.axis));   // H
  document.querySelectorAll('[data-scale]').forEach(x=>x.setAttribute('aria-pressed',String(+x.dataset.scale===state.scale)));   // H
  { const S=SHAPES[state.shape], bt=document.getElementById('bodytext'); if(S&&bt) bt.textContent=S.note; }   // H
  for(const k in KNOBS) syncKnob(k);
  // H: build with the strike and mic the body was tuned with, then move them to where they were saved.
  // The engine tunes the loudest partial at the build-time strike and mic (S1); building with the saved
  // ones instead could tune a different partial.
  const NP=state.geo.P.length, okI=i=>Number.isInteger(i)&&i>=0&&i<NP&&!state.geo.F[i];
  const ref=o.ref&&okI(o.ref.h)&&okI(o.ref.m)?o.ref:null, want={m:state.micIdx,h:state.hitIdx,a:state.axis};
  if(ref){ state.micIdx=ref.m; state.hitIdx=ref.h; if(ref.a===0||ref.a===1||ref.a===2) state.axis=ref.a; }
  rebuild();
  state.micIdx=want.m; state.hitIdx=want.h; state.axis=want.a; pickSend();
  if(node) node.port.postMessage({t:'spec',v:0});
  buildPads();
  return true;
}
""")
# factory presets and Learn
cut('// H: factory presets. Starting points;', 'function refreshList(sel){')
rep("""  {const o=document.createElement('option');o.value='';o.textContent='— pick a preset —';l.appendChild(o);}
  // H: factory presets first, then the ones saved on this phone
  const fg=document.createElement('optgroup'); fg.label='Factory';
  FACTORY.forEach(f=>{const o=document.createElement('option');o.value='factory:'+f.name;o.textContent=f.name;fg.appendChild(o);});
  l.appendChild(fg);
  const sg=document.createElement('optgroup'); sg.label=names.length?'Saved on this phone':'Saved on this phone (none yet)';
  names.forEach(nm=>{const o=document.createElement('option');o.value=nm;o.textContent=nm;sg.appendChild(o);}); l.appendChild(sg);
  if(sel) l.value=sel;""",
"""  // I: only Tank presets are listed; presets of the removed shapes stay in storage for the main Resonator
  const tanks=names.filter(nm=>tankPreset(all[nm]));
  {const o=document.createElement('option');o.value='';o.textContent=tanks.length?'— pick a preset —':'(nothing saved yet)';l.appendChild(o);}
  tanks.forEach(nm=>{const o=document.createElement('option');o.value=nm;o.textContent=nm;l.appendChild(o);});
  if(sel) l.value=sel;""")
rep("""  if(nm.startsWith('factory:')){ const f=FACTORY.find(x=>'factory:'+x.name===nm); if(f){ restore(presetFrom(f)); say('Loaded '+f.name+'. '+f.note); } return; }   // H
""", "")
rep("""  if(nm.startsWith('factory:')){ say('Factory presets stay. Load it, change it, then Save to keep your own version.'); return; }   // H
""", "")
rep("""  if(o&&restore(o)) say('Loaded from code'); else say('That code could not be read',true);""",
    """  if(o&&o.P&&!tankPreset(o)) say('That code is for the '+o.shape+', which this version does not have.',true);
  else if(o&&restore(o)) say('Loaded from code'); else say('That code could not be read',true);""")

# benchmark, WAV recording, video
cut('// ---------- benchmark ----------', 'const hintsBtn=document.getElementById(\'hints\');')

# chips for modes, specializations, pickups and shapes; scramble; the bow
cut("const modeEl=document.getElementById('modes');", "const rateEl=document.getElementById('rates');")
cut("const pickEl=document.getElementById('pickups');", "const axesEl=document.getElementById('axes');")
cut("document.getElementById('scramble').onclick=", "document.getElementById('hush').onclick=")
rep("""document.getElementById('hush').onclick=()=>{
 if(node)node.port.postMessage({t:'hush'});
 const bb=document.getElementById('bow');
 if(bb&&bb.getAttribute('aria-pressed')==='true'){ bb.setAttribute('aria-pressed','false'); val.bow=0; }
};const bowBtn=document.getElementById('bow');bowBtn.onclick=()=>{const on=bowBtn.getAttribute('aria-pressed')!=='true';bowBtn.setAttribute('aria-pressed',on);val.bow=on?0.16:0;send('bow');};""",
    """document.getElementById('hush').onclick=()=>{ if(node)node.port.postMessage({t:'hush'}); };""")
rep("addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='z'){e.shiftKey?doRedo():doUndo();e.preventDefault();return;}\n if(e.repeat)return;",
    "addEventListener('keydown',e=>{if(e.metaKey||e.ctrlKey||e.repeat)return;")

# ================================ building tools ================================
rep("state.hist=[]; state.redo=[];\n", "")
cut('// ---- S2: free building ------', "document.getElementById('home').onclick=", new=r"""// I: a short note shown on the picture (used when a circle is picked up)
let toolMsgTimer=0;
function toolMsg(t){ const m=document.getElementById('nudgeMsg'); if(!m) return; m.textContent=t||''; clearTimeout(toolMsgTimer); if(t) toolMsgTimer=setTimeout(()=>{ m.textContent=''; },4000); }
""")
rep("""document.getElementById('undo').onclick=doUndo;
document.getElementById('redo').onclick=doRedo;
""", "")
cut("for(const tb of document.querySelectorAll('.tool[data-tool]')) tb.onclick=()=>{", "// F4: tap path for the two drag-only tools.")
rep("""function syncNudge(){const on=state.tool==='orbit'||state.tool==='move';nudgeEl.hidden=!on;
 document.getElementById('nudgeLab').textContent=state.tool==='move'?'move':'turn';nudgeMsg.textContent='';}""",
    """function syncNudge(){nudgeEl.hidden=false;document.getElementById('nudgeLab').textContent='turn';}""")
rep("""function nudge(nx,ny){
 if(state.tool==='orbit'){state.spin=false;if(nx)camRotate(1,nx*0.12);if(ny)camRotate(0,ny*0.12);return true;}
 if(state.tool!=='move')return false;
 const g=state.geo,i=state.sel;
 if(!g||i<0||i>=g.P.length){nudgeMsg.textContent='tap a mass first';return false;}
 if(!nudgeMoved){geoPush();nudgeMoved=true;}
 const {R,U}=camBasis(),st=0.012,p=g.P[i];
 for(let a=0;a<3;a++)p[a]=Math.max(-0.6,Math.min(0.6,p[a]+(R[a]*nx+U[a]*ny)*st));
 if(node)node.port.postMessage({t:'mv',i,x:p[0],y:p[1],z:p[2]});
 return true;
}""", """function nudge(nx,ny){state.spin=false;if(nx)camRotate(1,nx*0.12);if(ny)camRotate(0,ny*0.12);return true;}""")

# ================================ the canvas: touch the circles ================================
cut("let drag=null;\ncv.addEventListener('pointerdown',e=>{", "// orientation as a 3x3 matrix mapping world -> camera", new=r"""// I: the mic and the strike are the two circles on the body. Press one and slide it along the body, or tap
// it and then tap where it should go. Anywhere else, a drag turns the view. Nothing to select first.
// Touch events drive it on a phone (pointer events of type touch are ignored, so a gesture never runs
// twice); a mouse or pen uses pointer events.
let drag=null;
const GRAB=30;   // px: a fingertip's reach around each circle
function markerAt(x,y){
  const g=state.geo; if(!g||!_px) return null;
  const r=cv.getBoundingClientRect(), px=x-r.left, py=y-r.top, N=g.P.length;
  const d=i=>(i==null||i<0||i>=N)?1e9:Math.hypot(_px[i]-px,_py[i]-py);
  const ds=d(state.hitIdx), dm=d(state.micIdx), reach=i=>Math.max(GRAB,18*((_pf&&_pf[i])||1));
  const s=ds<=reach(state.hitIdx), m=dm<=reach(state.micIdx);
  if(s&&m) return ds<dm-2?'strike':dm<ds-2?'mic':(state.lastKind==='strike'?'mic':'strike');   // stacked: the other one than last time
  return s?'strike':m?'mic':null;
}
function placeMarker(kind,i){
  const g=state.geo; if(!g||i<0||i>=g.P.length||g.F[i]) return false;
  if(kind==='strike'){ if(state.hitIdx===i) return false; state.hitIdx=i; if(node) node.port.postMessage({t:'hit',i,a:state.axis}); }
  else { if(state.micIdx===i) return false; state.micIdx=i;
    if(node){ node.port.postMessage({t:'mic',i,a:state.axis});
      const F=state.free,nn=F.length; state.micIdx2=F[(Math.max(0,F.indexOf(i))+Math.max(1,Math.floor(nn/2)))%Math.max(1,nn)];
      node.port.postMessage({t:'mic2',i:state.micIdx2}); } }
  state.lastKind=kind; syncPickSliders(); DIAG.mmoves++; return true;
}
function audition(){ if(!state.running) return; const k=SCALES[state.scale][0]; play(k,0.75); setTimeout(()=>stop(k),450); }   // hear where it went
function gestureStart(x,y){
  DIAG.cvdown++; state.spin=false;
  const k=markerAt(x,y);
  drag=k?{kind:k,x0:x,y0:y,moved:false,changed:false}:{x,y,x0:x,y0:y,moved:false};
  state.grab=k||null;
}
function gestureMove(x,y){
  if(!drag) return; DIAG.cvmove++;
  if(!drag.moved&&Math.hypot(x-drag.x0,y-drag.y0)>8) drag.moved=true;
  if(drag.kind){ if(drag.moved){ const i=pick(x,y,true); if(i>=0&&placeMarker(drag.kind,i)) drag.changed=true; } return; }
  camRotate(1,(x-drag.x)*0.008); camRotate(0,(y-drag.y)*0.008); drag.x=x; drag.y=y;
}
function gestureEnd(x,y){
  if(!drag) return; const d=drag; drag=null; state.grab=null;
  if(d.kind){
    if(d.moved){ if(d.changed) audition(); state.carry=null; toolMsg(''); return; }
    if(state.carry===d.kind){ state.carry=null; toolMsg(''); return; }   // tapped again: put it back down
    state.carry=d.kind; toolMsg('now tap where the '+(d.kind==='mic'?'mic':'strike')+' should go'); return;
  }
  if(!d.moved&&state.carry){ const i=pick(x,y,true); if(i>=0&&placeMarker(state.carry,i)) audition(); state.carry=null; toolMsg(''); }
}
let touchId=null;
cv.addEventListener('touchstart',e=>{
  if(e.touches.length!==1){ drag=null; state.grab=null; touchId=null; return; }   // two fingers: the roll gesture below
  const t=e.changedTouches[0]; touchId=t.identifier; DIAG.ctouch++; gestureStart(t.clientX,t.clientY); e.preventDefault();
},{passive:false});
cv.addEventListener('touchmove',e=>{ if(touchId===null) return;
  for(const t of e.changedTouches) if(t.identifier===touchId){ gestureMove(t.clientX,t.clientY); e.preventDefault(); } },{passive:false});
cv.addEventListener('touchend',e=>{ if(touchId===null) return;
  for(const t of e.changedTouches) if(t.identifier===touchId){ touchId=null; gestureEnd(t.clientX,t.clientY); } },{passive:true});
cv.addEventListener('touchcancel',()=>{ touchId=null; drag=null; state.grab=null; },{passive:true});
cv.addEventListener('pointerdown',e=>{ if(e.pointerType==='touch') return; try{ cv.setPointerCapture(e.pointerId); }catch(_){} gestureStart(e.clientX,e.clientY); });
cv.addEventListener('pointermove',e=>{ if(e.pointerType==='touch') return; gestureMove(e.clientX,e.clientY); });
cv.addEventListener('pointerup',e=>{ if(e.pointerType==='touch') return; gestureEnd(e.clientX,e.clientY); });
cv.addEventListener('pointercancel',e=>{ if(e.pointerType==='touch') return; drag=null; state.grab=null; });
""")

# ================================ drawing ================================
rep("if(state.tool!=='orbit'&&!drag&&!VREC.on&&ts-(state._lastDraw||0)<100)return;", "if(state.tool!=='orbit'&&!drag&&ts-(state._lastDraw||0)<100)return;")
rep("g2.clearRect(0,0,W,H);if(VREC.on)vrecBg();", "g2.clearRect(0,0,W,H);")
cut(" if(state.orbit&&val.att>0.02){\n", " mark(state.hitIdx,'#FF9A55','strike');mark(state.micIdx,'#4ED8EA','mic');\n")
rep(""" if(state.xm) state.xm.forEach((x,q)=>{ if(x.i>=0) mark(x.i,'#A7F0C8','mic '+(q+2)); });   // S4
 if(state.tool==='strike'||state.tool==='mic'){
   const col=state.tool==='strike'?'#FF9A55':'#4ED8EA';
   const idx=state.tool==='strike'?state.hitIdx:state.micIdx;
   if(idx!=null&&idx<N){
     g2.strokeStyle=col;g2.globalAlpha=0.55;g2.lineWidth=1;
     g2.beginPath();g2.arc(px[idx],py[idx],22*pf[idx],0,7);g2.stroke();
     g2.globalAlpha=1;
   }
 }""", """ { const act=state.grab||state.carry;   // I: the circle in hand, or picked up and waiting for a tap
   if(act){ const idx=act==='strike'?state.hitIdx:state.micIdx, col=act==='strike'?'#FF9A55':'#4ED8EA';
     if(idx!=null&&idx<N){ g2.strokeStyle=col;g2.lineWidth=1.6;g2.globalAlpha=state.grab?0.85:0.5+0.35*Math.sin(ts/170);
       g2.beginPath();g2.arc(px[idx],py[idx],22*pf[idx],0,7);g2.stroke();g2.globalAlpha=1; } } }""")
rep(" if(VREC.on) vrecOverlay();   // G\n", "")

# the readout: no OMEF lines
rep(""" if(i&&val.infer>0.02) s+='<br>certainty: <b>'+Math.round((1-(i.dpf||1))*100)+'%</b>';
 if(i&&val.mem>0.02) s+='<br>strain: <b>'+Math.round((i.h||0)*100)+'%</b>';
 if(i&&val.regime>0.02) s+='<br>regime: <b>'+['expansion','rate stress','credit stress','recession'][i.regime||0]+'</b>';
""", "")

# first message after waking: how to move the circles
rep("state.running=true;buildShape(true);\n}",
    "state.running=true;buildShape(true);\n say('Press the mic or strike circle and slide it along the tank.');   // I\n}")


# leftovers of the building tools and extra mics (guarded, now never true): taken out
rep(" if(state.hist&&state.geo){state.hist.push(geoSnap());if(state.hist.length>40)state.hist.shift();state.redo.length=0;syncUndo();}   // S2: shape/Size changes are undoable\n", "")
rep("  if(state.xm){ state.xm.forEach(x=>{ if(x.i>=g.P.length||(x.i>=0&&g.F[x.i])) x.i=-1; }); xmSendAll(); syncMicSlots(); }   // S4: page mirrors the engine\n", "")
rep("let nudgeMoved=false;\n", "")
rep(" const stop=()=>{if(timer){clearInterval(timer);timer=null;}held=0;if(nudgeMoved){nudgeMoved=false;drawInfo();}};", " const stop=()=>{if(timer){clearInterval(timer);timer=null;}held=0;};")
rep(" nb.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();nudge(nx,ny);if(nudgeMoved){nudgeMoved=false;drawInfo();}}});", " nb.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();nudge(nx,ny);}});")
cut("// screen-space camera basis, so a drag moves a mass in the plane you are looking at\nfunction camBasis(){", "function pick(cx,cy2,freeOnly){")


# the turn arrows move from the right side of the picture to a row at its bottom right, so no part of the
# tank (or a circle on it) sits under a button
rep("#nudge{position:absolute;right:10px;top:52px;display:grid;grid-template-columns:repeat(3,40px);grid-template-rows:repeat(3,40px);gap:3px}",
    "#nudge{position:absolute;right:10px;bottom:8px;display:flex;gap:4px}\n#nudge .nb{width:38px;height:36px}\n#nudge [aria-label=left]{order:1}#nudge [aria-label=right]{order:2}#nudge [aria-label=up]{order:3}#nudge [aria-label=down]{order:4}")
rep("#nudge .nl{grid-column:2;grid-row:2;align-self:center;text-align:center;font-size:9px;color:var(--dim);pointer-events:none}",
    "#nudge .nl{display:none}")
rep("#nudgeMsg{position:absolute;right:10px;top:182px;font-size:10px;color:var(--tension);pointer-events:none;text-shadow:0 1px 3px #000}",
    "#nudgeMsg{position:absolute;left:12px;bottom:52px;font-size:11px;color:var(--tension);pointer-events:none;text-shadow:0 1px 3px #000}")
rep("#tools{position:absolute;left:10px;right:10px;bottom:8px;display:flex;flex-wrap:wrap;gap:4px}",
    "#tools{position:absolute;left:10px;bottom:8px;display:flex;gap:4px}")


# every message goes through say(), so a timer from an earlier message cannot wipe a later one (the CPU
# governor's note was cleared this way in testing)
rep("""function govNote(){ const m=document.getElementById('msg'); if(!m) return; m.className='warn';
 m.textContent='The phone was running out of time, so a quiet older voice was let go to keep the sound clean. Fewer Voices, a smaller Size or a lower engine rate gives more room.'; }""",
    """function govNote(){ say('The phone was running out of time, so a quiet older voice was let go to keep the sound clean. Fewer Voices, a smaller Size or a lower engine rate gives more room.',true); }""")
rep("""  const m=document.getElementById('msg');
  m.className=ok?'':'warn';
  m.textContent=ok?'Saved as '+nm
    :'Saved for this session only — this browser blocks storage. Use Copy code to keep it.';""",
    """  say(ok?'Saved as '+nm:'Saved for this session only — this browser blocks storage. Use Copy code to keep it.',!ok);""")
rep("""  document.getElementById('msg').textContent='Deleted '+nm;""", """  say('Deleted '+nm);""")
rep("""  document.getElementById('msg').textContent='Preset code ready — copy it anywhere';""", """  say('Preset code ready — copy it anywhere');""")
rep("""   document.getElementById('msg').className='warn';
   document.getElementById('msg').textContent='Rate set to '+(r/1000)+' kHz — reload the page to apply it.';""",
    """   say('Rate set to '+(r/1000)+' kHz — reload the page to apply it.',true);""")

open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
