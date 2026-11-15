# Stage 3 (preview): new exciters — plectrum, oscillator, wind, phone microphone — and key release
# (hold-to-sustain). Edits apps/resonator-next.html in place; aborts on any mismatch.
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
eng("    this.asyncCal=false; this.refPick=null;",
    "    this.asyncCal=false; this.refPick=null;\n"
    "    // S3: exciters. Calibrated so each lands near the mallet's level at default settings.\n"
    "    this.wind=0; this.inGain=0.5; this.micIn=0; this.windL=null; this.windW=null; this.windOn=false;\n"
    "    this.exAny=false; this.exLive=false; this.plK=PLK; this.oscK=OSCK; this.windK=WINDK; this.inK=INK; this.oscNz=OSCNZ;\n"
    "    this.oscOn=new Uint8Array(this.VMAX); this.oscEnv=new Float64Array(this.VMAX); this.oscPh=new Float64Array(this.VMAX);\n"
    "    this.oscF=new Float64Array(this.VMAX); this.oscA=new Float64Array(this.VMAX); this.exF=new Float64Array(this.VMAX);\n"
    "    this.oscAtk=1-Math.exp(-1/(0.012*sampleRate)); this.oscRel=1-Math.exp(-1/(0.15*sampleRate));\n"
    "    this.windA=1-Math.exp(-2*Math.PI*400/sampleRate);")
eng("      case 'mode': this.mode=d.v; break;",
    "      case 'mode': this.mode=d.v; if(d.v!==3) this.oscOn.fill(0); break;   // S3: leaving oscillator mode releases it\n"
    "      case 'off': for(let v=0;v<this.VMAX;v++) if(this.oscOn[v]&&this.vf0[v]===d.f) this.oscOn[v]=0; break;   // S3: key released")
eng("      case 'hush': this.gateTarget=0; this.pendingReset=true; this.bow=0; this.modBase.bow=0;",
    "      case 'hush': this.gateTarget=0; this.pendingReset=true; this.bow=0; this.modBase.bow=0;\n"
    "        this.oscOn.fill(0); this.oscEnv.fill(0); if(this.windL) this.windL.fill(0);   // S3")
# plectrum: a pulse with a smooth pull and a quick release (pulses without `rise` are unchanged)
eng("          const t=1-p.left/p.dur, w=Math.sin(Math.PI*t);\n          A+=p.amp*w*w;",
    "          if(p.rise){   // S3 plectrum: smooth pull, then the string slips off\n"
    "            const el=p.dur-p.left;\n"
    "            A+=p.amp*(el<p.rise?0.5-0.5*Math.cos(Math.PI*el/p.rise):0.5+0.5*Math.cos(Math.PI*(el-p.rise)/Math.max(1,p.dur-p.rise)));\n"
    "          } else {\n"
    "            const t=1-p.left/p.dur, w=Math.sin(Math.PI*t);\n"
    "            A+=p.amp*w*w;\n"
    "          }")
eng("        frc[hb]+=A*hv[0]; frc[hb+1]+=A*hv[1]; frc[hb+2]+=A*hv[2];\n      }\n      if(this.fbF!==0){",
    "        frc[hb]+=A*hv[0]; frc[hb+1]+=A*hv[1]; frc[hb+2]+=A*hv[2];\n      }\n"
    "      if(this.exAny){   // S3: oscillator / microphone force at the strike point, wind on every mass\n"
    "        const F=this.exF[v];\n"
    "        if(F!==0){ const hv=this.hitVec, hb=b+this.hitI*3; frc[hb]+=F*hv[0]; frc[hb+1]+=F*hv[1]; frc[hb+2]+=F*hv[2]; }\n"
    "        if(this.windOn){ const Wf=this.windW, n3=N*3; for(let i=0;i<n3;i++) frc[b+i]+=Wf[i]; }\n"
    "      }\n"
    "      if(this.fbF!==0){")
eng("  strike(v){\n    this.pulses.length=0; this.pending.length=0;\n",
    "  strike(v){\n    this.pulses.length=0; this.pending.length=0;\n"
    "    if(this.mode===2){   // S3 plectrum: pull the strike point aside, then let it slip off\n"
    "      const sr=sampleRate, os=this.os, f=Math.max(20,this.f0);\n"
    "      const rise=Math.min(0.03,Math.max(0.005,1.2/f+0.004))*sr*os;\n"
    "      const slip=Math.max(2,(0.00008+0.004*this.hard*this.hard)*Math.pow(220/f,0.6)*sr*os);\n"
    "      this.pulses.push({left:rise+slip,dur:rise+slip,amp:this.plK*this.drive*v*this.kT*this.aChar,rise});\n"
    "      return;\n"
    "    }\n")
eng("  strikeVoice(vi,vel){\n    this.pulses=this.vPul[vi]; this.pending=this.vPen[vi];\n    this.strike(vel);\n  }",
    "  strikeVoice(vi,vel){\n    this.pulses=this.vPul[vi]; this.pending=this.vPen[vi];\n"
    "    if(this.mode===3){ this.pulses.length=0; this.pending.length=0; this.oscStart(vi,vel); return; }   // S3\n"
    "    this.strike(vel);\n  }\n"
    "  // S3 oscillator exciter: a force at the strike point at the played pitch, with a short attack and\n"
    "  // a release when the key comes up. Mallet sets the tone (hard = brighter, soft = a pure sine).\n"
    "  oscStart(v,vel){\n"
    "    this.oscF[v]=this.vf0[v]*Math.pow(2,this.tune/1200); this.oscOn[v]=1; this.exLive=true;\n"
    "    this.oscA[v]=this.oscK*this.drive*vel*(this.vkTt[v]||this.kT)*this.aChar;\n"
    "  }\n"
    "  // S3: oscillator, microphone and wind forces for one audio sample (held across its substeps).\n"
    "  // Does nothing at all while every exciter is off, so ordinary sounds are unchanged.\n"
    "  exciteSample(inp,k){\n"
    "    let any=false; const sr=sampleRate;\n"
    "    let xin=0;\n"
    "    if(this.micIn&&this.inGain>0&&inp&&inp[0]&&inp[0][0]){ xin=inp[0][0][k]||0; if(!isFinite(xin)) xin=0; }\n"
    "    let osc=false;\n"
    "    for(let v=0;v<this.voices;v++){\n"
    "      let F=0;\n"
    "      if(this.oscOn[v]||this.oscEnv[v]>0){\n"
    "        osc=true;\n"
    "        const tgt=this.oscOn[v]?1:0;\n"
    "        this.oscEnv[v]+=(tgt-this.oscEnv[v])*(tgt?this.oscAtk:this.oscRel); if(!tgt&&this.oscEnv[v]<1e-5) this.oscEnv[v]=0;\n"
    "        let ph=this.oscPh[v]+this.oscF[v]/sr; ph-=Math.floor(ph); this.oscPh[v]=ph;\n"
    "        const bb=1-this.hard, w=2*Math.PI*ph;\n"
    "        // the body only rings at its own partials, so harmonics of the drive barely sound; a little\n"
    "        // broadband roughness (hard = rough, soft = a pure sine) is what reaches the upper partials\n"
    "        const nz=bb>0.02?(this.rnd()*2-1):0;\n"
    "        F+=this.oscA[v]*this.oscEnv[v]*(Math.sin(w)+bb*0.5*Math.sin(2*w)+bb*bb*0.3333*Math.sin(3*w)+bb*bb*this.oscNz*nz);\n"
    "      }\n"
    "      if(xin!==0) F+=this.inK*this.inGain*this.inGain*xin*(this.vkT[v]||this.kT)*this.aChar;\n"
    "      this.exF[v]=F; if(F!==0) any=true;\n"
    "    }\n"
    "    if(this.wind>0&&this.N){\n"
    "      const n3=this.N*3;\n"
    "      if(!this.windL||this.windL.length!==n3){ this.windL=new Float64Array(n3); this.windW=new Float64Array(n3); }\n"
    "      const W=this.windK*this.wind*this.wind*(this.vkT[0]||this.kT)*this.aChar, a=this.windA, L=this.windL, Wf=this.windW, fx=this.fixed;\n"
    "      for(let q=0;q<this.N;q++){ if(fx[q]) continue; const i=q*3;\n"
    "        for(let c=0;c<3;c++){ L[i+c]+=a*((this.rnd()*2-1)-L[i+c]); Wf[i+c]=W*L[i+c]; } }\n"
    "      this.windOn=true; any=true;\n"
    "    } else if(this.windOn){ this.windW.fill(0); this.windOn=false; }\n"
    "    this.exAny=any; this.exLive=osc||this.windOn||(this.micIn&&this.inGain>0);\n"
    "  }")
eng("      for(let s=0;s<os;s++){ this.advance(1);",
    "      if(this.exLive||this.micIn||this.wind>0) this.exciteSample(inputs,k);   // S3\n"
    "      for(let s=0;s<os;s++){ this.advance(1);")

# --- static compliance at the strike point (how far it moves per unit force), from the same modal
# solve the tuning already does: sum over elastic modes of (mode shape at the strike point)^2 / stiffness.
# The new exciters aim for a displacement, not a force, so they sound at similar levels on every shape.
eng("      const w=Math.sqrt(lam[m]);\n      let h=0,c=0;\n      for(let a=0;a<3;a++){ h+=V[(3*hi+a)*n+m]*this.hitVec[a]; c+=V[(3*mi+a)*n+m]*this.micVec[a]; }\n      out.push({f:w/(2*Math.PI), amp:Math.abs(h*c)/w});",
    "      elastic++;   // S3: count accepted modes (the rigid-modes-are-lowest check was never armed)\n"
    "      const w=Math.sqrt(lam[m]);\n      let h=0,c=0;\n      for(let a=0;a<3;a++){ h+=V[(3*hi+a)*n+m]*this.hitVec[a]; c+=V[(3*mi+a)*n+m]*this.micVec[a]; }\n"
    "      cmp+=h*h/lam[m];   // S3: static compliance at the strike point\n"
    "      out.push({f:w/(2*Math.PI), amp:Math.abs(h*c)/w});")
eng("    let rigN=0,rigLow=true,elastic=0;", "    let rigN=0,rigLow=true,elastic=0,cmp=0;")
eng("    this.rigidN=rigN; this.rigidLow=rigLow&&this.orderedScan;\n    return out;",
    "    this.rigidN=rigN; this.rigidLow=rigLow&&this.orderedScan; this.lastComp=cmp;\n    return out;")
eng("    this.modeIdx=bi; this.fRef=sp0[bi].f; this.modeAmp=sp0[bi].amp;",
    "    this.modeIdx=bi; this.fRef=sp0[bi].f; this.modeAmp=sp0[bi].amp; this.comp0=this.lastComp;   // S3")
eng("fastFallbacks:this.fastFallbacks||0,rigidN:this.rigidN,rigidLow:this.rigidLow,orderedScan:this.orderedScan}; }",
    "fastFallbacks:this.fastFallbacks||0,rigidN:this.rigidN,rigidLow:this.rigidLow,orderedScan:this.orderedScan,comp0:this.comp0}; }")
eng("this.rigidN=c.rigidN; this.rigidLow=c.rigidLow; this.orderedScan=c.orderedScan; }",
    "this.rigidN=c.rigidN; this.rigidLow=c.rigidLow; this.orderedScan=c.orderedScan; this.comp0=c.comp0; }\n"
    "  compAt(kT){ return this.comp0>0?this.comp0*this.kRef/Math.max(1e-9,kT):1/(0.3*Math.max(1e-9,kT)); }   // S3: compliance at this stiffness")
eng("this.pulses.push({left:rise+slip,dur:rise+slip,amp:this.plK*this.drive*v*this.kT*this.aChar,rise});",
    "this.pulses.push({left:rise+slip,dur:rise+slip,amp:this.plK*this.drive*v*this.aChar/this.compAt(this.kT),rise});")
eng("this.oscA[v]=this.oscK*this.drive*vel*(this.vkTt[v]||this.kT)*this.aChar;",
    "this.oscA[v]=this.oscK*this.drive*vel*this.aChar/this.compAt(this.vkTt[v]||this.kT);")
eng("F+=this.inK*this.inGain*this.inGain*xin*(this.vkT[v]||this.kT)*this.aChar;",
    "F+=this.inK*this.inGain*this.inGain*xin*this.aChar/this.compAt(this.vkT[v]||this.kT);")
eng("const W=this.windK*this.wind*this.wind*(this.vkT[0]||this.kT)*this.aChar,",
    "const W=this.windK*this.wind*this.wind*this.aChar/this.compAt(this.vkT[0]||this.kT),")

# ---------------- tuner: one tuning per shape change ----------------
# A shape change sends the body and then re-sends every knob (Stiffness and Substrate among them),
# which made the shadow tune twice. It now waits for that burst to settle (12 ms, at most ~70 ms)
# and tunes once with the final state; the result is the table the second tuning produced.
rep('''"let P=null,deb=0,last=0;",''', '''"let P=null,deb=0,last=0,sSeq=0,sT=0;",''')
rep('''"function recalNow(){deb=0;if(P.calDirty){P.calibrate();P.calDirty=false;}reply('recal',last);}",''',
    '''"function flush(){deb=0;if(sSeq){P.calibrate();P.calDirty=false;reply('struct',sSeq);if(last>sSeq)reply('recal',last);sSeq=0;return;}if(P.calDirty){P.calibrate();P.calDirty=false;}reply('recal',last);}",
"function later(ms){if(deb)clearTimeout(deb);deb=setTimeout(function(){try{flush();}catch(err){fail(err);}},ms);}",''')
rep('''" if(d.t==='struct'){if(deb){clearTimeout(deb);recalNow();}last=d.seq;P.msg(d);P.calDirty=false;reply('struct',d.seq);return;}",''',
    '''" if(d.t==='struct'){if(deb){clearTimeout(deb);flush();}last=d.seq;var real=P.calibrate;P.calibrate=function(){};try{P.msg(d);}finally{P.calibrate=real;}sSeq=d.seq;sT=Date.now();later(12);return;}",''')
rep('''" if(trig||P.calDirty){if(deb)clearTimeout(deb);deb=setTimeout(function(){try{recalNow();}catch(err){fail(err);}},30);}",''',
    '''" if(sSeq){P.calDirty=false;if(Date.now()-sT<60)later(12);return;}",
" if(trig||P.calDirty)later(30);",''')

# ---------------- page ----------------
rep(" gain:{label:'Level',min:0,max:1.6,step:0.01,val:0.85,fmt:v=>Math.round(v*62)+'',hint:''},",
    " gain:{label:'Level',min:0,max:1.6,step:0.01,val:0.85,fmt:v=>Math.round(v*62)+'',hint:''},\n"
    " wind:{label:'Wind',min:0,max:1,step:0.01,val:0,fmt:v=>v<0.02?'still':Math.round(v*100)+'%',hint:'Turbulent air pushing on every mass at once. Keeps the body singing with no strike at all: breathy, and it never repeats.'},\n"
    " inGain:{label:'Mic input',min:0,max:1,step:0.01,val:0.5,fmt:v=>Math.round(v*100)+'%',hint:'How hard the sound from your phone’s microphone pushes the strike point. Turn on Mic in below.'},")
rep('      <div class="knob" data-k="gain"></div>\n',
    '      <div class="knob" data-k="gain"></div>\n'
    '      <div class="secttl">Air and microphone</div>\n'
    '      <div class="knob" data-k="wind"></div>\n'
    '      <div class="knob" data-k="inGain"></div>\n'
    '      <div class="row"><button class="chip" id="micin" aria-pressed="false">Mic in</button></div>\n'
    '      <div class="hint" style="display:block">Your voice or any sound drives the body. While the mic is on, iPhone plays everything at about half volume (an iOS limitation), and headphones stop feedback.</div>\n')
rep("['Mallet','Worthington splash'].forEach((nm,i)=>{",
    "['Mallet','Worthington splash','Plectrum','Oscillator'].forEach((nm,i)=>{   // S3: plectrum and oscillator")
rep("'spRot','spElev','bowSpd','bowVc'])send(k)", "'spRot','spElev','bowSpd','bowVc','wind','inGain'])send(k)", count=3)
# key release: hold a key to sustain (releases the oscillator)
rep("const fire=e=>{e.preventDefault();if(!state.running)return;play(semi,0.55+0.45*Math.random());b.classList.add('lit');setTimeout(()=>b.classList.remove('lit'),130);};b.addEventListener('pointerdown',fire);",
    "const fire=e=>{e.preventDefault();if(!state.running)return;play(semi,0.55+0.45*Math.random());b.classList.add('lit');setTimeout(()=>b.classList.remove('lit'),130);};b.addEventListener('pointerdown',fire);"
    "const rel=()=>{if(state.running)stop(semi);};b.addEventListener('pointerup',rel);b.addEventListener('pointercancel',rel);b.addEventListener('pointerleave',rel);")
rep("function play(semi,vel){",
    "function stop(semi){   // S3: key released\n"
    " if(!node)return; const m=state.root+semi; node.port.postMessage({t:'off',f:440*Math.pow(2,(m-69)/12)});\n"
    "}\nfunction play(semi,vel){")
rep("    if(state.running) play(SCALES[state.scale][0], 0.75);",
    "    if(state.running){ play(SCALES[state.scale][0], 0.75); setTimeout(()=>stop(SCALES[state.scale][0]),450); }   // S3: auditions release themselves")
rep("  if(t!=='note'&&t!=='ret'&&t!=='rec'){", "  if(t!=='note'&&t!=='off'&&t!=='ret'&&t!=='rec'){")
rep("node=new AudioWorkletNode(ctx,'resonator',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[2]});",
    "node=new AudioWorkletNode(ctx,'resonator',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[2]});   // S3: one input, for Mic in")
MIC = r'''
// ---- S3: Mic in -------------------------------------------------------------------------
// The phone's microphone drives the strike point. iOS switches to a play-and-record session while
// the mic is on (Web Audio plays at about half volume: WebKit bug 236219); switching the session
// back to playback when the mic goes off restores the volume.
const MIC={on:false,stream:null,src:null};
async function micToggle(){
  const b=document.getElementById('micin');
  if(MIC.on){
    try{ if(MIC.src) MIC.src.disconnect(); }catch(e){}
    try{ if(MIC.stream) MIC.stream.getTracks().forEach(t=>t.stop()); }catch(e){}
    MIC.on=false; MIC.src=null; MIC.stream=null;
    if(node) node.port.postMessage({t:'p',k:'micIn',v:0});
    try{ if(navigator.audioSession) navigator.audioSession.type='playback'; }catch(e){}
    b.setAttribute('aria-pressed','false'); b.textContent='Mic in'; return;
  }
  if(!node||state.audioMode!=='audio worklet'){ b.textContent='Mic in: needs the low-latency engine'; return; }
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){ b.textContent='Mic in: not available here'; return; }
  b.textContent='Mic in: asking…';
  try{
    try{ if(navigator.audioSession) navigator.audioSession.type='play-and-record'; }catch(e){}
    const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:false,autoGainControl:false}});
    if(ctx.state==='suspended') await ctx.resume();
    const src=ctx.createMediaStreamSource(stream); src.connect(node);
    MIC.on=true; MIC.stream=stream; MIC.src=src;
    node.port.postMessage({t:'p',k:'micIn',v:1});
    b.setAttribute('aria-pressed','true'); b.textContent='Mic in: on';
  }catch(e){
    try{ if(navigator.audioSession) navigator.audioSession.type='playback'; }catch(_){}
    b.textContent='Mic in: '+(e&&e.name==='NotAllowedError'?'permission denied':'unavailable');
  }
}
document.getElementById('micin').onclick=micToggle;
'''
rep("const diagEl=document.getElementById('diag');\n", "const diagEl=document.getElementById('diag');\n" + MIC)
# calibration constants (set below from measurements)
for k, v in {'PLK': sys.argv[2], 'OSCK': sys.argv[3], 'WINDK': sys.argv[4], 'INK': sys.argv[5], 'OSCNZ': sys.argv[6]}.items():
    a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a)
    seg = s[a:b]
    if seg.count(k) != 1: sys.exit(f'ABORT: constant {k}')
    s = s[:a] + seg.replace(k, v) + s[b:]
open(P, 'w', encoding='utf-8').write(s)
print('patched', P)
