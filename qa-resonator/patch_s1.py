# Stage 1 (preview): tuning maths off the audio thread, octave-trap fix, Copy report, preview label.
# Reads apps/resonator.html, writes apps/resonator-next.html. Every edit must match exactly once
# or the script aborts without writing anything.
import sys
SRC, DST = sys.argv[1], sys.argv[2]
s = open(SRC, encoding='utf-8').read()

def rep(old, new, where='page'):
    global s
    n = s.count(old)
    if n != 1:
        sys.exit(f'ABORT ({where}): expected 1 match, found {n}: {old[:80]!r}')
    s = s.replace(old, new)

# ---------------- engine (inside the WORKLET string: no backticks, no template expressions) -------
ENGINE_EDITS = [
    ("    this.pool=[];                                     // FIX8: frame buffer pool\n",
     "    this.pool=[];                                     // FIX8: frame buffer pool\n"
     "    this.asyncCal=false; this.refPick=null;           // S1: tuning computed off the audio thread / reference pickups\n"),
    ("      case 'ret': if(this.pool.length<3) this.pool.push(d.P); break; // FIX8\n",
     "      case 'ret': if(this.pool.length<3) this.pool.push(d.P); break; // FIX8\n"
     "      case 'cal': if(!this.ok) break; this.applyCal(d.cal); this.calDirty=false; this.pitch(); this.report('ready'); break; // S1\n"
     "      case 'asyncCal': this.asyncCal=!!d.v; break;                                                                         // S1\n"),
    ("        if(this.calDirty){ this.calibrate(); this.calDirty=false; } // FIX4\n",
     "        if(this.calDirty&&!this.asyncCal){ this.calibrate(); this.calDirty=false; } // FIX4 (S1: with async tuning the shadow engine retunes)\n"),
    ("    this.ok=true; this.calibrate(); this.calDirty=false; this.pitch();\n",
     "    this.refPick={hitI:this.hitI,micI:this.micI,hitVec:this.hitVec.slice(),micVec:this.micVec.slice()}; // S1: tuning reference fixed at build\n"
     "    this.ok=true;\n"
     "    if(d.cal) this.applyCal(d.cal); else this.calibrate();   // S1: a table computed off the audio thread rides in with the body\n"
     "    this.calDirty=false; this.pitch();\n"),
    ("  calibrate(){\n    this.anchored=false;",
     "  // S1: modes are always ranked with the strike and mic the body was built with, so moving the\n"
     "  // strike or mic and then touching Stiffness/Substrate can no longer change which partial is tuned.\n"
     "  calibrate(){\n"
     "    const r=this.refPick;\n"
     "    const same=(a,b)=>a[0]===b[0]&&a[1]===b[1]&&a[2]===b[2];\n"
     "    if(!r||(r.hitI===this.hitI&&r.micI===this.micI&&same(r.hitVec,this.hitVec)&&same(r.micVec,this.micVec))) return this.calibrateNow();\n"
     "    const cur={hitI:this.hitI,micI:this.micI,hitVec:this.hitVec,micVec:this.micVec};\n"
     "    this.hitI=r.hitI; this.micI=r.micI; this.hitVec=r.hitVec; this.micVec=r.micVec;\n"
     "    try{ return this.calibrateNow(); }\n"
     "    finally{ this.hitI=cur.hitI; this.micI=cur.micI; this.hitVec=cur.hitVec; this.micVec=cur.micVec; }\n"
     "  }\n"
     "  calState(){ return {anchored:this.anchored,modeIdx:this.modeIdx,fRef:this.fRef,modeAmp:this.modeAmp,table:this.table,\n"
     "    fastFallbacks:this.fastFallbacks||0,rigidN:this.rigidN,rigidLow:this.rigidLow,orderedScan:this.orderedScan}; }\n"
     "  applyCal(c){ this.anchored=c.anchored; this.dofMap(); this.modeIdx=c.modeIdx; this.fRef=c.fRef; this.modeAmp=c.modeAmp;\n"
     "    this.table=c.table; this.fastFallbacks=c.fastFallbacks; this.rigidN=c.rigidN; this.rigidLow=c.rigidLow; this.orderedScan=c.orderedScan; }\n"
     "  calibrateNow(){\n    this.anchored=false;"),
]
a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a)
for old, new in ENGINE_EDITS:
    assert '`' not in new and '${' not in new, 'ABORT: template characters in engine edit'
    seg = s[a:b]
    if seg.count(old) != 1:
        sys.exit(f'ABORT (engine): expected 1 match, found {seg.count(old)}: {old[:80]!r}')
    s = s[:a] + seg.replace(old, new) + s[b:]
    b = s.index('`;', a)

# ---------------- main thread ---------------------------------------------------------------
TUNER = r'''
// ---- S1: tuning maths in a background Worker ---------------------------------------------
// A shadow copy of the engine runs in a Worker and receives every control message the real engine
// gets (never notes or buffer returns), so its state is identical. It computes the tuning table
// there, so nothing on the audio thread waits for it. A new body reaches the real engine together
// with its table, and notes that need a fresh table wait for it, so everything still plays in tune.
// Messages to the engine keep their order because only this page sequences them (ordering is
// guaranteed within one channel, not across channels). If the Worker can't start or stops
// answering, the engine goes back to tuning itself.
const TUNER={on:false,w:null,url:null,raw:null,seq:0,q:[],recalWant:0,recalDone:0,timer:0,up:false,upTimer:0,
  stats:{structs:0,recals:0,lastMs:0,maxMs:0,fails:0,why:''}};
const TUNER_SRC=[
"let P=null,deb=0,last=0;",
"function reply(kind,seq){postMessage({t:'cal',kind:kind,seq:seq,cal:P.calState()});}",
"function recalNow(){deb=0;if(P.calDirty){P.calibrate();P.calDirty=false;}reply('recal',last);}",
"function fail(err){postMessage({t:'err',msg:String(err&&err.message||err)});}",
"onmessage=function(e){var d=e.data;try{",
" if(d.t==='init'){var K=null;class Shim{constructor(){this.port={onmessage:null,postMessage:function(){}};}}",
"  new Function('AudioWorkletProcessor','registerProcessor','sampleRate',d.src)(Shim,function(n,k){K=k;},d.rate);",
"  P=new K();postMessage({t:'up'});return;}",
" if(d.t==='struct'){if(deb){clearTimeout(deb);recalNow();}last=d.seq;P.msg(d);P.calDirty=false;reply('struct',d.seq);return;}",
" last=d.seq;P.msg(d);",
" var trig=(d.t==='p'&&(d.k==='ratio'||d.k==='sub'))||d.t==='mv';",
" if(trig||P.calDirty){if(deb)clearTimeout(deb);deb=setTimeout(function(){try{recalNow();}catch(err){fail(err);}},30);}",
"}catch(err){fail(err);}};"
].join('\n');
function tunerStart(){
  if(TUNER.w||!window.Worker||!window.Blob||!window.URL) return;
  try{
    TUNER.url=URL.createObjectURL(new Blob([TUNER_SRC],{type:'application/javascript'}));
    const w=new Worker(TUNER.url);
    TUNER.w=w; TUNER.raw=node.port.postMessage.bind(node.port);
    w.onmessage=tunerReply;
    w.onerror=e=>{ if(e&&e.preventDefault) e.preventDefault(); tunerFail('worker error'+(e&&e.message?': '+e.message:'')); };
    w.postMessage({t:'init',src:WORKLET,rate:ctx.sampleRate});
    node.port.postMessage=tunerRoute;
    TUNER.on=true; TUNER.raw({t:'asyncCal',v:1});
    TUNER.upTimer=setTimeout(()=>{ if(!TUNER.up) tunerFail('worker did not start'); },4000);
  }catch(e){ TUNER.on=false; TUNER.stats.why=String(e&&e.message||e); }
}
function tunerRoute(m,tr){
  if(!TUNER.on) return TUNER.raw(m,tr);
  const t=m&&m.t;
  if(t==='struct'){
    const seq=++TUNER.seq;
    TUNER.w.postMessage(Object.assign({},m,{seq}));
    TUNER.q.push({m,struct:true,seq,cal:null,t0:performance.now()});
    tunerArm(); tunerUI(); return;
  }
  if(t!=='note'&&t!=='ret'&&t!=='rec'){
    const seq=++TUNER.seq; TUNER.w.postMessage(Object.assign({},m,{seq}));
    if((t==='p'&&(m.k==='ratio'||m.k==='sub'))||t==='mv') TUNER.recalWant=seq;
  }
  if(TUNER.q.length||(t==='note'&&TUNER.recalDone<TUNER.recalWant)){
    TUNER.q.push({m,tr,struct:false,need:t==='note'?TUNER.recalWant:0});
    if(t==='note') tunerArm();
    return;
  }
  TUNER.raw(m,tr);
}
function tunerReply(e){
  const d=e.data;
  if(d.t==='up'){ TUNER.up=true; clearTimeout(TUNER.upTimer); try{URL.revokeObjectURL(TUNER.url);}catch(_){} return; }
  if(d.t==='err'){ tunerFail(d.msg); return; }
  if(d.t!=='cal'||!TUNER.on) return;
  const q=TUNER.q, st=TUNER.stats;
  if(d.kind==='struct'){
    const it=q.find(x=>x.struct&&x.seq===d.seq);
    if(it){ it.cal=d.cal; const ms=Math.round(performance.now()-it.t0); st.structs++; st.lastMs=ms; st.maxMs=Math.max(st.maxMs,ms); }
  } else {
    st.recals++; TUNER.recalDone=Math.max(TUNER.recalDone,d.seq);
    // a newer table for a body still waiting in the queue rides along with it; otherwise it goes now
    let host=null; for(const x of q) if(x.struct&&x.seq<d.seq) host=x;
    if(host) host.cal=d.cal; else TUNER.raw({t:'cal',cal:d.cal});
  }
  tunerDrain();
}
function tunerDrain(){
  const q=TUNER.q;
  while(q.length){
    const it=q[0];
    if(it.struct){ if(!it.cal) break; TUNER.raw(Object.assign({},it.m,{cal:it.cal})); q.shift(); continue; }
    if(it.m.t==='note'&&TUNER.recalDone<it.need) break;
    TUNER.raw(it.m,it.tr); q.shift();
  }
  if(!q.length) tunerDisarm();
  tunerUI();
}
function tunerArm(){ if(!TUNER.timer) TUNER.timer=setTimeout(()=>tunerFail('no answer in 20 s'),20000); }
function tunerDisarm(){ if(TUNER.timer){ clearTimeout(TUNER.timer); TUNER.timer=0; } }
function tunerFail(why){
  if(!TUNER.on) return;
  TUNER.on=false; TUNER.stats.fails++; TUNER.stats.why=why; tunerDisarm(); clearTimeout(TUNER.upTimer);
  try{ if(TUNER.w) TUNER.w.terminate(); }catch(_){}
  TUNER.raw({t:'asyncCal',v:0});
  const q=TUNER.q.splice(0);
  for(const it of q){ if(it.struct) TUNER.raw(it.cal?Object.assign({},it.m,{cal:it.cal}):it.m); else TUNER.raw(it.m,it.tr); }
  if(TUNER.recalDone<TUNER.recalWant) TUNER.raw({t:'p',k:'sub',v:val.sub});   // a retune was in flight: let the engine redo it
  tunerUI();
}
function tunerUI(){ const on=TUNER.q.some(x=>x.struct); if(on!==!!state.tuning){ state.tuning=on; drawInfo(); } }
'''
rep("function send(k){if(node)node.port.postMessage({t:'p',k,v:val[k]});}\n",
    "function send(k){if(node)node.port.postMessage({t:'p',k,v:val[k]});}\n" + TUNER)
rep(" if(state.audioMode==='buffered'){node.port.postMessage({t:'p',k:'osMax',v:10});}\n",
    " tunerStart();   // S1\n if(state.audioMode==='buffered'){node.port.postMessage({t:'p',k:'osMax',v:10});}\n")
rep(" s+= i?`reference mode <b>${i.fRef.toFixed(1)} Hz</b><br>${i.os}× · ${(ctx.sampleRate/1000).toFixed(0)} kHz · ${state.audioMode}`:'measuring…';\n",
    " s+= i?`reference mode <b>${i.fRef.toFixed(1)} Hz</b><br>${i.os}× · ${(ctx.sampleRate/1000).toFixed(0)} kHz · ${state.audioMode}`:'measuring…';\n"
    " if(state.tuning) s+='<br><b>tuning…</b>';   // S1\n")

# Copy report (S1): everything needed to debug from a phone, in one tap
rep('<button class="chip" id="bench">Benchmark</button></div>',
    '<button class="chip" id="bench">Benchmark</button><button class="chip" id="copydiag">Copy report</button></div>')
COPY = r'''
// S1: one tap copies everything needed to debug on a phone (paste it into the chat)
document.getElementById('copydiag').onclick=async()=>{
  const s=TUNER.stats, g=state.geo;
  const txt=['RESONATOR report · '+new Date().toISOString(), navigator.userAgent,
    'engine: '+(state.audioMode||'not started')+(ctx?' · '+ctx.sampleRate+' Hz':''),
    'tuning thread: '+(TUNER.on?'background':'audio')+' · bodies '+s.structs+' · retunes '+s.recals+' · last '+s.lastMs+' ms · slowest '+s.maxMs+' ms'+(s.fails?' · fallbacks '+s.fails+' ('+s.why+')':''),
    'shape: '+state.shape+' · masses '+(g?g.P.length:0)+' · springs '+(g?g.S.length:0),
    '', (diagEl.textContent||'(tap Self-test or Benchmark first for more detail)'),
    '', 'recent: '+JSON.stringify((window.RESONATOR_DIAG||[]).slice(-4))].join('\n');
  let ok=false;
  try{ await navigator.clipboard.writeText(txt); ok=true; }catch(e){}
  if(!ok){ const ta=document.createElement('textarea'); ta.value=txt; ta.setAttribute('readonly',''); ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.select(); ta.setSelectionRange(0,txt.length); try{ ok=document.execCommand('copy'); }catch(e){} ta.remove(); }
  const b=document.getElementById('copydiag'); b.textContent=ok?'Copied ✓':'Copy failed'; setTimeout(()=>{ b.textContent='Copy report'; },1600);
};
'''
rep("const diagEl=document.getElementById('diag');\n", "const diagEl=document.getElementById('diag');\n" + COPY)

# preview label
rep('<title>RESONATOR</title>', '<title>RESONATOR next</title>')
rep('<div id="brand">RESONATOR</div>', '<div id="brand">RESONATOR · NEXT</div>')

open(DST, 'w', encoding='utf-8').write(s)
print('wrote', DST)
