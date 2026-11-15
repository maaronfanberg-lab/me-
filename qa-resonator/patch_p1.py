# Phone performance, stage P1 (preview): the engine stops spending time on silence and measures its own
# load on the device. Edits apps/resonator-next.html in place; aborts on any mismatch.
#  - Voices that sit exactly at rest with nothing pushing them are skipped (exact: such a voice computes
#    zero force, so simulating it changes nothing, bit for bit).
#  - Sleep (page-enabled): a voice whose motion has died below 1e-8 of its own scale is set exactly to
#    rest and then skipped (about -110 dBFS at the output).
#  - CPU load measured on the device every 0.25 s; shown on the page and in Copy report.
#  - Governor (page-enabled): past 85% of real time twice in a row, the quietest older voice is muted
#    (damped hard, like a hand on a string, then put to sleep) and fewer voices may ring at once.
#  - The effects no longer create a new array for every audio sample (garbage-collector pauses).
#  - Two settings are read once per step instead of once per spring (same values, same arithmetic).
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1, where='page'):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT ({where}): expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)

def seg_bounds():
    a = s.index('const WORKLET = String.raw`'); b = s.index('`;', a); return a, b

def eng(old, new, within=None):
    """Replace exactly one occurrence inside the engine (optionally inside one method)."""
    global s
    assert '`' not in new and '${' not in new, 'ABORT: template characters in engine edit'
    a, b = seg_bounds(); seg = s[a:b]
    if within:
        f0 = seg.index(within[0]); f1 = seg.index(within[1], f0 + 1)
        part = seg[f0:f1]
        if part.count(old) != 1:
            sys.exit(f'ABORT (engine/{within[0].strip()}): expected 1 match, found {part.count(old)}: {old[:90]!r}')
        seg = seg[:f0] + part.replace(old, new) + seg[f1:]
    else:
        if seg.count(old) != 1:
            sys.exit(f'ABORT (engine): expected 1 match, found {seg.count(old)}: {old[:90]!r}')
        seg = seg.replace(old, new)
    s = s[:a] + seg + s[b:]

ADV = ('  advance(dt_scale){', '  hardReset(){')

# ---------------- engine: state ----------------
eng("    this.pool=[];                                     // FIX8: frame buffer pool\n",
    "    this.pool=[];                                     // FIX8: frame buffer pool\n"
    "    // P1: per-voice rest/mute flags, sleep and CPU governor (both off unless the page turns them on)\n"
    "    this.vRest=new Uint8Array(8).fill(1); this.vMute=new Uint8Array(8); this.anyMute=false;\n"
    "    this.perfSleep=false; this.perfGov=false; this.vCap=8; this.govHot=0; this.govCool=0; this.govActs=0;\n"
    "    this.sleeps=0; this.slScan=0; this.cpuAcc=0; this.cpuN=0; this.cpu=0; this.cpuMax=0;\n"
    "    this.spL=0; this.spR=0; this.fxL=0; this.fxR=0;\n")
eng("      case 'mv': this.moveMass(d.i,d.x,d.y,d.z); break;\n",
    "      case 'mv': this.moveMass(d.i,d.x,d.y,d.z); this.vRest.fill(0); break;   // P1: a moved mass may no longer be at rest\n"
    "      case 'perf': this.perfSleep=!!d.sleep; this.perfGov=!!d.gov; if(!this.perfGov){ this.vCap=this.VMAX; } break;   // P1\n"
    "      case 'perfTest': if(this.perfGov) this.governCpu(d.c); break;   // P1: lets a test drive the governor\n")
eng("    this.pos.set(this.rest);\n",
    "    this.pos.set(this.rest);\n"
    "    this.vRest.fill(1); this.vMute.fill(0); this.anyMute=false;   // P1: every voice exactly at rest\n")
eng("    this.vel.fill(0); this.pos.set(this.rest); this.pulses.length=0; this.pending.length=0; this.haveGood=false;\n",
    "    this.vel.fill(0); this.pos.set(this.rest); this.pulses.length=0; this.pending.length=0; this.haveGood=false;\n"
    "    this.vRest.fill(1); this.vMute.fill(0); this.anyMute=false;   // P1\n")
eng("          for(let i=0;i<lv;i++) this.vel[i]*=0.35;\n",
    "          for(let i=0;i<lv;i++) this.vel[i]*=0.35;\n"
    "          this.vRest.fill(0);   // P1: a rewind can put any voice back in motion\n")

# ---------------- engine: the physics step ----------------
eng("    const dmp=this.decay>0?Math.exp(-(6.91/this.decay)*dt):1;\n",
    "    const dmp=this.decay>0?Math.exp(-(6.91/this.decay)*dt):1;\n"
    "    // P1: read once per step (same values, same arithmetic as before)\n"
    "    const nl=this.nl, nlCap=this.nlCap||6, vRest=this.vRest;\n"
    "    const gForce=this.windOn||this.fbF!==0||this.bow>0;            // forces that reach every voice\n"
    "    const mk=this.anyMute?Math.exp(-(6.91/0.015)*dt):1;               // a muted voice loses 60 dB in 15 ms\n", within=ADV)
eng("      const b=v*st;\n",
    "      const b=v*st;\n"
    "      if(vRest[v]){   // P1: exactly at rest and nothing pushing it: zero force, so nothing to compute\n"
    "        if(!gForce&&!this.vPul[v].length&&!this.vPen[v].length&&!(this.exAny&&this.exF[v]!==0)) continue;\n"
    "        vRest[v]=0;\n"
    "      }\n", within=ADV)
eng("        if(this.nl>0){\n", "        if(nl>0){\n", within=ADV)
eng("          T*=Math.min(this.nlCap||6,1+this.nl*1600*(bx*bx+by*by+bz*bz));\n",
    "          T*=Math.min(nlCap,1+nl*1600*(bx*bx+by*by+bz*bz));\n", within=ADV)
eng("        const e=kL*(L-a)*(1+this.nl*st*st);\n", "        const e=kL*(L-a)*(1+nl*st*st);\n", within=ADV)
eng("      for(let n=0;n<N;n++){\n        if(fixed[n]) continue; const i=b+n*3;\n",
    "      const dmpv=(mk!==1&&this.vMute[v])?dmp*mk:dmp;   // P1: muted voices are damped hard, then sleep\n"
    "      for(let n=0;n<N;n++){\n        if(fixed[n]) continue; const i=b+n*3;\n", within=ADV)
eng("        vx*=dmp;vy*=dmp;vz*=dmp; vel[i]=vx;vel[i+1]=vy;vel[i+2]=vz;\n",
    "        vx*=dmpv;vy*=dmpv;vz*=dmpv; vel[i]=vx;vel[i+1]=vy;vel[i+2]=vz;\n", within=ADV)

# ---------------- engine: sleep, governor ----------------
eng("  hardReset(){\n",
    "  // P1: a voice whose motion has died below 1e-8 (velocity re its pitch, displacement re the body's\n"
    "  // size; about -110 dBFS at the output) is set exactly to rest and skipped until something moves it.\n"
    "  // all=false: only voices the governor muted are considered.\n"
    "  sleepCheck(all){\n"
    "    const st=this.stride, V=this.voices, ac=this.aChar||1, pos=this.pos, vel=this.vel, rest=this.rest; let mute=false;\n"
    "    const gForce=this.windOn||this.fbF!==0||this.bow>0;\n"
    "    for(let v=0;v<V;v++){\n"
    "      if(this.vRest[v]) continue;\n"
    "      if(!all&&!this.vMute[v]) continue;\n"
    "      if(gForce||this.vPul[v].length||this.vPen[v].length||(this.exAny&&this.exF[v]!==0)||this.oscOn[v]){ if(this.vMute[v]) mute=true; continue; }\n"
    "      const b=v*st, e=b+st; let mv=0, mp=0;\n"
    "      for(let i=b;i<e;i++){ const a=Math.abs(vel[i]); if(a>mv) mv=a; const d=Math.abs(pos[i]-rest[i]); if(d>mp) mp=d; }\n"
    "      const f=this.vf0[v]||this.f0||220;\n"
    "      if(mv/(2*Math.PI*f*ac)<1e-8&&mp/ac<1e-8){\n"
    "        for(let i=b;i<e;i++){ pos[i]=rest[i]; vel[i]=0; }\n"
    "        this.vRest[v]=1; this.vMute[v]=0; this.vOn[v]=0; this.sleeps++;\n"
    "      } else if(this.vMute[v]) mute=true;\n"
    "    }\n"
    "    this.anyMute=mute;\n"
    "  }\n"
    "  awakeCount(){ let n=0; for(let v=0;v<this.voices;v++) if(!this.vRest[v]&&!this.vMute[v]) n++; return n; }\n"
    "  // P1: the load is measured on the device itself. Past 85% of real time twice in a row (0.5 s), the\n"
    "  // quietest older voice is muted and fewer voices may ring at once; the limit climbs back after 2 s\n"
    "  // under 60%.\n"
    "  governCpu(c){\n"
    "    if(c>0.85){ this.govCool=0; if(++this.govHot>=2){ this.govHot=0; this.shedVoice(); } }\n"
    "    else if(c<0.6){ this.govHot=0; if(++this.govCool>=8){ this.govCool=0; if(this.vCap<this.voices) this.vCap++; } }\n"
    "    else { this.govHot=0; this.govCool=0; }\n"
    "  }\n"
    "  shedVoice(){\n"
    "    const V=this.voices; if(V<=1) return;\n"
    "    let aw=0, newest=-1;\n"
    "    for(let v=0;v<V;v++) if(!this.vRest[v]&&!this.vMute[v]){ aw++; if(newest<0||this.vAge[v]>this.vAge[newest]) newest=v; }\n"
    "    if(aw<=1) return;\n"
    "    const st=this.stride, vel=this.vel; let best=-1, bq=Infinity;\n"
    "    for(let v=0;v<V;v++){\n"
    "      if(this.vRest[v]||this.vMute[v]||v===newest||this.oscOn[v]) continue;   // never the newest note or a held key\n"
    "      let m=0; for(let i=v*st;i<(v+1)*st;i++){ const a=Math.abs(vel[i]); if(a>m) m=a; }\n"
    "      const q=m/(2*Math.PI*(this.vf0[v]||this.f0||220));\n"
    "      if(q<bq){ bq=q; best=v; }\n"
    "    }\n"
    "    if(best<0) return;\n"
    "    this.vMute[best]=1; this.anyMute=true; this.vOn[best]=0; this.vCap=Math.max(1,aw-1); this.govActs++;\n"
    "  }\n"
    "  hardReset(){\n")
eng("  pickVoice(){\n    if(this.voices<=1) return 0;\n",
    "  pickVoice(){\n    if(this.voices<=1) return 0;\n"
    "    if(this.perfGov&&this.vCap<this.voices){   // P1: at the governor's limit, reuse a ringing voice\n"
    "      let aw=0; for(let v=0;v<this.voices;v++) if(!this.vRest[v]&&!this.vMute[v]) aw++;\n"
    "      if(aw>=this.vCap){\n"
    "        for(let v=0;v<this.voices;v++) if(!this.vRest[v]&&!this.vMute[v]&&!this.vOn[v]) return v;\n"
    "        let best=-1; for(let v=0;v<this.voices;v++) if(!this.vRest[v]&&!this.vMute[v]&&(best<0||this.vAge[v]<this.vAge[best])) best=v;\n"
    "        if(best>=0) return best;\n"
    "      }\n"
    "    }\n")
eng("    const v=this.pickVoice();\n",
    "    const v=this.pickVoice();\n"
    "    if(this.vMute[v]) this.vMute[v]=0;   // P1: a new note on a muted voice un-mutes it\n")
eng("    this.scan+=n;\n    if(this.scan>=128){\n",
    "    if(this.perfSleep||this.anyMute){   // P1\n"
    "      this.slScan+=n; if(this.slScan>=1024){ this.slScan=0; this.sleepCheck(this.perfSleep); }\n"
    "    }\n"
    "    this.scan+=n;\n    if(this.scan>=128){\n")

# ---------------- engine: CPU measurement around process() ----------------
eng("  process(inputs, outputs){\n    const out=outputs[0]; if(!this.ok){",
    "  // P1: how much of real time the audio thread spends here, measured on the device (Date.now has\n"
    "  // 1 ms steps; summed over 0.25 s of audio). The page shows it; the governor uses it.\n"
    "  process(inputs, outputs){\n"
    "    const t0=Date.now(); const r=this.processInner(inputs, outputs);\n"
    "    this.cpuAcc+=Date.now()-t0; this.cpuN+=(outputs[0]&&outputs[0][0])?outputs[0][0].length:128;\n"
    "    if(this.cpuN>=0.25*sampleRate){ const c=this.cpuAcc/(1000*this.cpuN/sampleRate); this.cpuAcc=0; this.cpuN=0;\n"
    "      this.cpu=c; if(c>this.cpuMax) this.cpuMax=c; if(this.perfGov) this.governCpu(c); }\n"
    "    return r;\n"
    "  }\n"
    "  processInner(inputs, outputs){\n    const out=outputs[0]; if(!this.ok){")
eng("      this.port.postMessage(M[0].ty||M[1].ty||M[2].ty?{t:'frame',pk:this.peak,mv:[M[0].e,M[1].e,M[2].e]}:{t:'frame',pk:this.peak});\n",
    "      const fr=M[0].ty||M[1].ty||M[2].ty?{t:'frame',pk:this.peak,mv:[M[0].e,M[1].e,M[2].e]}:{t:'frame',pk:this.peak};\n"
    "      fr.cpu=this.cpu; fr.cpuMax=this.cpuMax; fr.aw=this.awakeCount(); fr.cap=Math.min(this.vCap,this.voices); fr.ga=this.govActs; fr.sl=this.sleeps;   // P1\n"
    "      this.port.postMessage(fr);\n")

# ---------------- engine: no new array per audio sample in the effects ----------------
eng("    if(!isFinite(l)) l=0; if(!isFinite(r)) r=0;\n    return [l,r];\n  }\n  fx(o){",
    "    if(!isFinite(l)) l=0; if(!isFinite(r)) r=0;\n    this.spL=l; this.spR=r;   // P1: results in fields, no array per sample\n  }\n  fx(o){")
eng("    return [Math.max(-1.2,Math.min(1.2,l)),Math.max(-1.2,Math.min(1.2,r))];\n  }\n  observe(dtBlock){",
    "    this.fxL=Math.max(-1.2,Math.min(1.2,l)); this.fxR=Math.max(-1.2,Math.min(1.2,r));   // P1\n  }\n  observe(dtBlock){")
eng("        if(this.fxLive()){ const f=this.fx(mid); mid=(f[0]+f[1])*0.5; side+=(f[0]-f[1])*0.5; }\n",
    "        if(this.fxLive()){ this.fx(mid); mid=(this.fxL+this.fxR)*0.5; side+=(this.fxL-this.fxR)*0.5; }\n")
eng("        if(this.spLive()){ const s=this.spatial(mid, mi); mid=(s[0]+s[1])*0.5; side+=(s[0]-s[1])*0.5; }\n",
    "        if(this.spLive()){ this.spatial(mid, mi); mid=(this.spL+this.spR)*0.5; side+=(this.spL-this.spR)*0.5; }\n")

# ---------------- page ----------------
rep(" tunerStart();   // S1\n",
    " tunerStart();   // S1\n"
    " node.port.postMessage({t:'perf',sleep:1,gov:1});   // P1: sleeping voices and the CPU governor, live play only\n")
rep("     state.peak=d.pk; state.ranOnce=true; drawLevel();\n",
    "     state.peak=d.pk; state.ranOnce=true; drawLevel();\n"
    "     if(d.cpu!==undefined){ state.cpu=d.cpu; state.cpuMax=d.cpuMax; state.aw=d.aw; state.cap=d.cap; state.sl=d.sl;   // P1\n"
    "       if(d.ga>(state.ga||0)){ state.ga=d.ga; govNote(); } cpuShow(); }\n")
rep("function drawLevel(){\n",
    "// P1: the audio thread's own load, measured on this device\n"
    "function cpuShow(){ const el=document.getElementById('cpuinfo'); if(!el||state.cpu===undefined) return;\n"
    " const c=Math.round(state.cpu*100); el.textContent='CPU '+c+'%'; el.style.color=c>=85?'var(--tension)':''; }\n"
    "function govNote(){ const m=document.getElementById('msg'); if(!m) return; m.className='warn';\n"
    " m.textContent='The phone was running out of time, so a quiet older voice was let go to keep the sound clean. Fewer Voices, a smaller Size or a lower engine rate gives more room.'; }\n"
    "function drawLevel(){\n")
rep("${i.os}× · ${(ctx.sampleRate/1000).toFixed(0)} kHz · ${state.audioMode}`:'measuring…';\n",
    "${i.os}× · ${(ctx.sampleRate/1000).toFixed(0)} kHz · ${state.audioMode} · <span id=\"cpuinfo\"></span>`:'measuring…';\n")
rep(" el.innerHTML=s;\n const load=g.S.length*(i?i.os:1),m=document.getElementById('msg');\n",
    " el.innerHTML=s; cpuShow();\n const load=g.S.length*(i?i.os:1),m=document.getElementById('msg');\n")
rep("    'shape: '+state.shape+' · masses '+(g?g.P.length:0)+' · springs '+(g?g.S.length:0),\n",
    "    'shape: '+state.shape+' · masses '+(g?g.P.length:0)+' · springs '+(g?g.S.length:0),\n"
    "    'cpu: '+(state.cpu!==undefined?Math.round(state.cpu*100)+'% now · '+Math.round((state.cpuMax||0)*100)+'% highest · voices ringing '+state.aw+' of '+val.voices+' (limit '+state.cap+') · let go '+(state.ga||0)+' · slept '+(state.sl||0):'not measured yet'),   // P1\n")

open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
