# Stage J1 (preview): finish the strip. The engine loses the code for every feature Stage I took off the
# page (OMEF and its regimes, inference, memory, coupling and attractor; space; FX; plate reverb; exciters other
# than the mallet; Mics 2-4 and the stereo second mic; modulators; feedback; humbucker coils; amp, tone stack and
# cabinet; WAV recording). Every one of them was switched off and unreachable, so the Tank must sound bit for bit
# the same: proved by qa-resonator/j1_verify.mjs (old engine vs new, same messages) and by the Stage I replay.
# The page loses the unused second Tank definition, the other seven shapes, the removed knobs and the messages
# that only existed for them. The engine now accepts only the controls the page still has ('p' whitelist), so an
# old preset or a stray message cannot switch a removed path back on (there is no path left to switch on).
# Edits apps/resonator-next.html in place; aborts on any mismatch.
import re, sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:100]!r}')
    s = s.replace(old, new)

# ------------------------------------------------------------------ engine
w0 = s.index('const WORKLET = String.raw`') + len('const WORKLET = String.raw`')
w1 = s.index('`;', w0)
W = s[w0:w1]

def method_span(W, name):
    """[start, end) of a class method at two-space indent, including the // comment lines right above it"""
    m = list(re.finditer(r'\n  ' + re.escape(name) + r'\([^)]*\)\s*\{', W))
    if len(m) != 1:
        sys.exit(f'ABORT: method {name}: found {len(m)}')
    a = m[0].start() + 1
    # absorb comment lines immediately above
    while True:
        prev = W.rfind('\n', 0, a - 1)
        line = W[prev + 1:a - 1]
        if line.startswith('  //') or line.startswith('  /*') or line.startswith('   *'):
            a = prev + 1
        else:
            break
    # matching brace
    i = W.index('{', m[0].end() - 1); depth = 0
    for j in range(i, len(W)):
        c = W[j]
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = j + 1
                if W[end:end + 1] == '\n': end += 1
                return a, end
    sys.exit(f'ABORT: no end for {name}')

def drop(name):
    global W
    a, b = method_span(W, name); W = W[:a] + W[b:]

def swap(name, new):
    global W
    a, b = method_span(W, name)
    old = W[a:b]
    W = W[:a] + new.strip('\n') + '\n' + W[b:]
    return old

for nm in ['oscStart', 'exciteSample', 'modSpan', 'modShape', 'modStep', 'envNote', 'applyMods', 'resetOrgans',
           'couple', 'spLive', 'setTrim', 'fxLive', 'attractor', 'spatial', 'fx', 'rvSet', 'rvAlloc', 'rvClear',
           'rvRd', 'rvWr', 'rvTap', 'rvAp', 'rvApm', 'reverbSample', 'observe', 'filter', 'strain', 'regimes']:
    drop(nm)

# the long comment blocks that described the removed layers sit between methods, not above one
for blk in ['''  // OMEF regime layer. Logits drift under a two-cycle drive whose periods sit in
  // golden ratio, so the pair never realigns; softmax turns them into a mixture,
  // and the mixture pulls the organ vector toward four characteristic states.
  // Strain accumulates from playing and forgets on a Fibonacci curve: it holds on
  // at first, then lets go faster than an exponential would.
  // Four observation profiles: [note rate, force, register, accumulated strain].
  // The filter carries particles over regimes, weights them by how well the
  // regime explains what it just heard, and resamples when they degenerate.
  // U_{n+1} = R(C,M,F) + C^phi + h e_h, with every term from the printed recursion.
''', '''  // Z^phi is a pure rotation at the golden angle: two quadrature signals that
  // never realign -> chorus. F rotates slowly -> tremolo and pan. L is the
  // innovation memory, i.e. filtered noise -> tape wow. C is the accounting-
  // projected vector, ten coordinates -> ten delay taps. ||U|| is orbit radius
  // -> how hard the saturator is driven.
  // Interaural time and level from the mic's actual azimuth, air absorption and
  // attenuation from its actual distance, Doppler from its actual radial
  // velocity, and early reflections from a room scaled to the body.
''', '''  // F: plate reverb. Dattorro's figure-of-eight tank, scaled from his 29761 Hz to this engine's rate.
  // T60 from Reverb time: one trip round the eight is 21589 samples at 29761 Hz with decay applied four
  // times, so decay = 0.001^(trip / (4 T60)) (low frequencies; the damping filter shortens the highs).
''', '''  // OMEF cross-organ weight matrix, seven organs mapped onto seven parameters.
  // Offsets are computed from the BASE values only, never from coupled ones, so
  // the system cannot feed back on itself.
  // Every organ returns to the user's own setting at the start of each block, so
  // the coupling and regime layers stack onto a fixed base instead of onto their
  // own previous output.
''']:
    if blk in W:   # some were absorbed as the comment above a dropped method
        W = W.replace(blk, '', 1)

swap('constructor', r'''
  constructor(){
    super();
    this.ok=false; this.N=0; this.S=0; this.os=1; this.deg=2;
    this.VMAX=8; this.V=1; this.voices=1; this.stride=0; this.osMax=28; this.peak=0; this.ageC=0; this.slewing=false; this.smOs=-1; this.smVal=0;
    this.vf0=new Float64Array(8).fill(220); this.vkT=new Float64Array(8); this.vkL=new Float64Array(8);
    this.vkTt=new Float64Array(8); this.vkLt=new Float64Array(8);
    this.vAge=new Float64Array(8); this.vOn=new Uint8Array(8);
    this.vLp=new Float64Array(8); this.vLpB=new Float64Array(8);
    this.vPul=[[],[],[],[],[],[],[],[]]; this.vPen=[[],[],[],[],[],[],[],[]];
    this.f0=220; this.fRef=0; this.kRef=1e8; this.kT=0; this.kL=0; this.kTt=0; this.kLt=0; this.snapNext=true;
    this.ratio=6; this.decay=4; this.loss=0.5; this.sub=0.0006; this.drive=1;
    this.hard=0.3; this.blend=0.12; this.gain=0.85; this.tune=0;
    this.tone=6000; this.bite=0; this.nl=0; this.angle=0.4;
    // the pickup: a coil of fixed aperture over the mic point, then its inductance/cable resonance
    this.nlCap=6; this.pkAp=0.18; this.pkRes=3000; this.pkQ=1.6;
    this.c1=0; this.c2=0;
    this.micI=0; this.micA=1; this.hitI=0; this.hitA=1;
    this.pulses=[]; this.pending=[];
    this.lp=0; this.lpB=0; this.dcx=0; this.dcy=0; this.tick=0;
    this.specTrim=2.6;   // J1: the level trim of the old 'even' specialization, which the Tank always used
    this.gate=1; this.gateTarget=1; this.gateStep=0;  // FIX7: click-free gating
    this.calDirty=false; this.capped=false;           // FIX4 / FIX2
    this.clampHits=0; this.trips=0; this.scan=0; this.badScans=0; this.governed=0; this.load=0;      // FIX1 / D9 telemetry
    this.pool=[];                                     // FIX8: frame buffer pool
    // P1: per-voice rest/mute flags, sleep and CPU governor (both off unless the page turns them on)
    this.vRest=new Uint8Array(8).fill(1); this.vMute=new Uint8Array(8); this.anyMute=false;
    this.perfSleep=false; this.perfGov=false; this.vCap=8; this.govHot=0; this.govCool=0; this.govActs=0;
    this.sleeps=0; this.slScan=0; this.cpuAcc=0; this.cpuN=0; this.cpu=0; this.cpuMax=0;
    this.asyncCal=false; this.refPick=null;
    // F1: seeded PRNG so the same input always gives the same output
    this.seed0=0x2545F491; this.rs=this.seed0;
    // F2/F3: level calibration and ceiling limiter (gain is exactly 1 below the ceiling)
    this.lvl=1; this.limG=1; this.limC=0.7674;   /* -2.3 dBFS internal: covers the measured 1.1 dB under-read of the 16-tap estimator, so output holds -1 dBTP */ this.limRel=1-Math.exp(-1/(0.08*sampleRate));
    // 16-sample lookahead (0.33 ms at 48 kHz). Peaks between samples are found by 4x
    // windowed-sinc interpolation, so the ceiling holds as true peak, not just sample peak.
    this.tpD=16; this.tpL=new Float64Array(32); this.tpR=new Float64Array(32); this.tpGr=new Float64Array(32).fill(1); this.tpI=0;
    this.tpK=[]; for(let f=1;f<4;f++){ const fr=f/4, k=new Float64Array(16);
      for(let j=0;j<16;j++){ const t=(j-7)-fr; const w=0.5+0.5*Math.cos(Math.PI*t/8.5); k[j]=(t===0?1:Math.sin(Math.PI*t)/(Math.PI*t))*w; }
      this.tpK.push(k); }
    this.port.onmessage = e => this.msg(e.data);
  }
''')

swap('msg', r'''
  msg(d){
    switch(d.t){
      case 'struct': this.rs=this.seed0; this.build(d); break;
      case 'seed': this.seed0=(d.v|0)||0x2545F491; this.rs=this.seed0; break;
      case 'lvl': this.lvl=(d.v>0&&d.v<32)?d.v:1; break;
      case 'p':
        if(!KEYS.has(d.k)) break;   // J1: only the controls the page has; nothing else can be set
        this[d.k]=d.v;
        if(d.k==='angle'){ this.vectors(); }
        if(d.k==='nl') this.pitch();
        if(d.k==='voices'){ this.voices=Math.max(1,Math.min(this.VMAX,Math.round(d.v)));
          for(let v=1;v<this.VMAX;v++){ this.vOn[v]=0; this.vPul[v].length=0; this.vPen[v].length=0; }
          this.pitch(); }
        if(d.k==='ratio'||d.k==='sub'){ this.calDirty=true; this.pitch(); }   // FIX4/FIX10
        else if(d.k==='tune') this.pitch();
        break;
      case 'note':
        if(this.calDirty&&!this.asyncCal){ this.calibrate(); this.calDirty=false; } // FIX4 (S1: with async tuning the shadow engine retunes)
        this.noteOn(d.f,d.v); break;
      case 'mic': this.micI=d.i; this.micA=d.a; this.vectors(); break;
      case 'mv': this.moveMass(d.i,d.x,d.y,d.z); this.vRest.fill(0); break;   // P1: a moved mass may no longer be at rest
      case 'perf': this.perfSleep=!!d.sleep; this.perfGov=!!d.gov; if(!this.perfGov){ this.vCap=this.VMAX; } break;   // P1
      case 'perfTest': if(this.perfGov) this.governCpu(d.c); break;   // P1: lets a test drive the governor
      case 'hit': this.hitI=d.i; this.hitA=d.a; this.vectors(); break;
      case 'hush': this.gateTarget=0; this.pendingReset=true;
        for(let v=0;v<this.VMAX;v++){ this.vPul[v].length=0; this.vPen[v].length=0; this.vOn[v]=0; }
        this.pulses=this.vPul[0]; this.pending=this.vPen[0]; break; // FIX7
      case 'ret': if(this.pool.length<3) this.pool.push(d.P); break; // FIX8
      case 'cal': if(!this.ok) break; this.applyCal(d.cal); this.calDirty=false; this.pitch(); this.report('ready'); break; // S1
      case 'asyncCal': this.asyncCal=!!d.v; break;
    }
  }
''')

swap('build', r'''
  build(d){
    const N=d.n, S=d.si.length, V=this.VMAX;
    this.N=N; this.S=S; this.stride=N*3;
    this.restOne=Float64Array.from(d.pos);
    this.rest=new Float64Array(V*N*3); this.pos=new Float64Array(V*N*3);
    for(let v=0;v<V;v++){ this.rest.set(this.restOne, v*N*3); }
    for(let v=0;v<V;v++){ this.vPul[v].length=0; this.vPen[v].length=0; this.vOn[v]=0; }
    this.pos.set(this.rest);
    this.vRest.fill(1); this.vMute.fill(0); this.anyMute=false;   // P1: every voice exactly at rest
    this.vel=new Float64Array(V*N*3); this.frc=new Float64Array(V*N*3);
    this.goodPos=new Float64Array(V*N*3); this.goodVel=new Float64Array(V*N*3); this.haveGood=false;
    this.fixed=Uint8Array.from(d.fixed); this.si=Int32Array.from(d.si); this.sj=Int32Array.from(d.sj);
    this.sa=new Float64Array(S); this.su=new Float64Array(S*3);
    const deg=new Int32Array(N);
    for(let s=0;s<S;s++){
      const i=this.si[s]*3, j=this.sj[s]*3;
      const x=this.restOne[j]-this.restOne[i], y=this.restOne[j+1]-this.restOne[i+1], z=this.restOne[j+2]-this.restOne[i+2];
      const a=Math.max(1e-9,Math.sqrt(x*x+y*y+z*z));
      this.sa[s]=a; this.su[s*3]=x/a; this.su[s*3+1]=y/a; this.su[s*3+2]=z/a;
      deg[this.si[s]]++; deg[this.sj[s]]++;
    }
    let m=2; for(let n=0;n<N;n++) if(deg[n]>m) m=deg[n]; this.deg=m;
    let tot=0; for(let s=0;s<S;s++) tot+=this.sa[s]; this.aChar=Math.max(1e-6,tot/S);
    // axial direction at each node = direction of the first spring touching it.
    // Used to give the mallet an oblique component and the mic an axial share,
    // so the longitudinal (squeeze) modes are both excited and audible.
    this.ax3=new Float64Array(N*3); const seen=new Uint8Array(N);
    for(let s=0;s<S;s++){
      for(const nd of [this.si[s],this.sj[s]]){
        if(seen[nd]) continue; seen[nd]=1;
        this.ax3[nd*3]=this.su[s*3]; this.ax3[nd*3+1]=this.su[s*3+1]; this.ax3[nd*3+2]=this.su[s*3+2];
      }
    }
    this.shapeTrim=Math.pow(Math.max(1,this.deg/2),0.55)*Math.pow(Math.max(0.02,this.aChar)/0.056,0.30);
    this.micI=d.mic; this.hitI=d.hit; this.micA=d.axis; this.hitA=d.axis; this.axis=d.axis;
    this.pool.length=0; this.clampHits=0; this.trips=0;
    this.vectors();
    this.refPick={hitI:this.hitI,micI:this.micI,hitVec:this.hitVec.slice(),micVec:this.micVec.slice()}; // S1: tuning reference fixed at build
    this.ok=true;
    if(d.cal) this.applyCal(d.cal); else this.calibrate();   // S1: a table computed off the audio thread rides in with the body
    this.calDirty=false; this.pitch();
    this.report('ready');
  }
''')

swap('buildCoils', r'''
  buildCoils(){
    if(!this.N) return;
    this.coilA=this.coil(this.micI,this.pkAp);
  }
''')

old = swap('vectors', r'''
  vectors(){
    if(!this.ax3) return;
    const OBL=1.9*this.angle, AXM=1.5*this.angle;   // live mallet obliquity / mic axial share
    const mk=(node,axis,amt)=>{
      const v=[0,0,0]; v[axis]=1;
      const a=[this.ax3[node*3],this.ax3[node*3+1],this.ax3[node*3+2]];
      const d=a[0]*v[0]+a[1]*v[1]+a[2]*v[2];
      const p=[a[0]-d*v[0],a[1]-d*v[1],a[2]-d*v[2]];   // axial dir, minus the pure-axis part
      const pl=Math.sqrt(p[0]*p[0]+p[1]*p[1]+p[2]*p[2])||1;
      const o=[v[0]+amt*p[0]/pl, v[1]+amt*p[1]/pl, v[2]+amt*p[2]/pl];
      const ol=Math.sqrt(o[0]*o[0]+o[1]*o[1]+o[2]*o[2])||1;
      return [o[0]/ol,o[1]/ol,o[2]/ol];
    };
    this.hitVec=mk(this.hitI,this.hitA,OBL);
    this.micVec=mk(this.micI,this.micA,AXM);
    this.buildCoils();
  }
''')
if 'this.micVec2=mk(' not in old:
    sys.exit('ABORT: vectors() was not the expected one')

swap('report', r'''
  report(tag){
    this.port.postMessage({t:tag, fRef:this.fRef, os:this.os, springs:this.S, masses:this.N,
      kT:this.kT, kL:this.kL, capped:this.capped, deg:this.deg,
      clampHits:this.clampHits, trips:this.trips, governed:this.governed, voices:this.voices});
  }
''')

swap('worstNl', r'''
  worstNl(){
    return Math.min(6,1+Math.max(0,this.nl)*0.62);
  }
''')
swap('worstRatio', r'''
  worstRatio(){
    return Math.max(0.2,this.ratio);
  }
''')

swap('noteOn', r'''
  noteOn(f,vel){
    const v=this.pickVoice();
    if(this.vMute[v]) this.vMute[v]=0;   // P1: a new note on a muted voice un-mutes it
    this.vf0[v]=f; this.vAge[v]=++this.ageC; this.vOn[v]=1;
    this.f0=f; this.snapNext=true;
    if(this.voices>1){
      // a fresh voice starts from rest; monophonic keeps the ring, as before
      const b=v*this.stride, e=b+this.stride;
      for(let i=b;i<e;i++){ this.pos[i]=this.rest[i]; this.vel[i]=0; }
      this.vLp[v]=0; this.vLpB[v]=0;
    }
    this.pitchVoice(v);
    this.strikeVoice(v,vel);
  }
''')

rep_engine = [
  ('''    let det=0;
    if(this.spread>0&&this.voices>1)
      det=this.spread*(0.35+0.65*this.dPF)*95*((v/(this.voices-1))*2-1);
    const f=this.vf0[v]*Math.pow(2,(this.tune+det)/1200);''',
   '''    const f=this.vf0[v]*Math.pow(2,this.tune/1200);'''),
  ('''    this.pulses=this.vPul[vi]; this.pending=this.vPen[vi];
    if(this.mode===3){ this.pulses.length=0; this.pending.length=0; this.oscStart(vi,vel); return; }   // S3
    this.strike(vel);''',
   '''    this.pulses=this.vPul[vi]; this.pending=this.vPen[vi];
    this.strike(vel);'''),
]
for a, b in rep_engine:
    if W.count(a) != 1: sys.exit(f'ABORT engine edit: {a[:80]!r}')
    W = W.replace(a, b)

swap('strike', r'''
  strike(v){
    this.pulses.length=0; this.pending.length=0;
    let secs=(0.00025+0.007*this.hard*this.hard)*Math.pow(220/Math.max(20,this.f0),0.6);
    secs=Math.min(0.02,Math.max(0.00018,secs));
    const J=1.1*this.drive*v*this.f0*this.aChar*Math.min(1.5,Math.max(0.35,this.specTrim));
    this.push(0,secs,J);
  }
''')

swap('advance', r'''
  advance(dt_scale){
    // A knob turn must not step the force field. Ramp stiffness over ~25 ms so a
    // sustaining note glides instead of exploding into the divergence guard.
    // Only pay for the stiffness ramp while one is actually running, and cache the
    // coefficient rather than calling exp on every substep.
    if(this.slewing){
      if(this.smOs!==this.os){ this.smVal=1-Math.exp(-1/(0.025*sampleRate*this.os)); this.smOs=this.os; }
      const sm=this.smVal; let any=false;
      for(let v=0;v<this.voices;v++){
        if(!this.vkTt[v]) continue;
        if(this.vkT[v]===this.vkTt[v]&&this.vkL[v]===this.vkLt[v]) continue;
        this.vkT[v]+=(this.vkTt[v]-this.vkT[v])*sm; this.vkL[v]+=(this.vkLt[v]-this.vkL[v])*sm;
        if(Math.abs(this.vkTt[v]-this.vkT[v])<this.vkTt[v]*1e-4){ this.vkT[v]=this.vkTt[v]; this.vkL[v]=this.vkLt[v]; }
        else any=true;
      }
      this.slewing=any;
    }
    const N=this.N,S=this.S,pos=this.pos,vel=this.vel,frc=this.frc,rest=this.rest,
          si=this.si,sj=this.sj,sa=this.sa,su=this.su,fixed=this.fixed,
          kT=this.kT,kL=this.kL,sub=this.sub*this.kT,st=this.stride;
    const dt=dt_scale/(sampleRate*this.os);
    this.lossK=this.loss*0.02*Math.pow(220/Math.max(20,this.f0),0.8)
              /Math.sqrt(Math.max(1,this.deg/2));
    const live=this.voices*st;
    frc.fill(0,0,live);   // only the voices that exist
    const dmp=this.decay>0?Math.exp(-(6.91/this.decay)*dt):1;
    // P1: read once per step (same values, same arithmetic as before)
    const nl=this.nl, nlCap=this.nlCap||6, vRest=this.vRest;
    const mk=this.anyMute?Math.exp(-(6.91/0.015)*dt):1;               // a muted voice loses 60 dB in 15 ms
    for(let v=0;v<this.voices;v++){
      const b=v*st;
      if(vRest[v]){   // P1: exactly at rest and nothing pushing it: zero force, so nothing to compute
        if(!this.vPul[v].length&&!this.vPen[v].length) continue;
        vRest[v]=0;
      }
      const kT=this.vkT[v]||this.kT, kL=this.vkL[v]||this.kL;
      const c=this.lossK*Math.sqrt(kT), sub=this.sub*kT;
      const pul=this.vPul[v], pen=this.vPen[v];
      for(let s=0;s<S;s++){
        const i=b+si[s]*3, j=b+sj[s]*3, a=sa[s], s3=s*3;
        let dx=pos[j]-pos[i], dy=pos[j+1]-pos[i+1], dz=pos[j+2]-pos[i+2];
        let L=Math.sqrt(dx*dx+dy*dy+dz*dz);
        if(L<a*0.05){ L=a*0.05; this.clampHits++; }        // D9: counted, not silent
        const ux=dx/L, uy=dy/L, uz=dz/L; const st=(L-a)/a;
        let T=kT*a;
        if(nl>0){
          const bx=ux-su[s3], by=uy-su[s3+1], bz=uz-su[s3+2];
          // Adjacent masses move nearly together, so per-spring angular deviation
          // is small and its square is smaller still. Scaled to make this audible,
          // clamped so the stiffness rise cannot eat the stability margin.
          T*=Math.min(nlCap,1+nl*1600*(bx*bx+by*by+bz*bz));
        }
        const e=kL*(L-a)*(1+nl*st*st);
        const rvx=vel[j]-vel[i], rvy=vel[j+1]-vel[i+1], rvz=vel[j+2]-vel[i+2];
        const gg=e;
        const fx=T*(ux-su[s3])+gg*ux+c*rvx,
              fy=T*(uy-su[s3+1])+gg*uy+c*rvy,
              fz=T*(uz-su[s3+2])+gg*uz+c*rvz;
        frc[i]+=fx; frc[i+1]+=fy; frc[i+2]+=fz; frc[j]-=fx; frc[j+1]-=fy; frc[j+2]-=fz;
      }
      if(pen.length){
        for(let q=pen.length-1;q>=0;q--){
          const e=pen[q]; e.delay-=dt_scale;
          if(e.delay<=0){ pul.push(e.pulse); pen.splice(q,1); }
        }
      }
      if(pul.length){
        let A=0, hv=this.hitVec, hb=b+this.hitI*3;
        for(let q=pul.length-1;q>=0;q--){
          const p=pul[q];
          const t=1-p.left/p.dur, w=Math.sin(Math.PI*t);
          A+=p.amp*w*w;
          p.left-=dt_scale; if(p.left<=0) pul.splice(q,1);
        }
        frc[hb]+=A*hv[0]; frc[hb+1]+=A*hv[1]; frc[hb+2]+=A*hv[2];
      }
      const dmpv=(mk!==1&&this.vMute[v])?dmp*mk:dmp;   // P1: muted voices are damped hard, then sleep
      for(let n=0;n<N;n++){
        if(fixed[n]) continue; const i=b+n*3;
        let vx=vel[i]+(frc[i]-sub*(pos[i]-rest[i]))*dt,
            vy=vel[i+1]+(frc[i+1]-sub*(pos[i+1]-rest[i+1]))*dt,
            vz=vel[i+2]+(frc[i+2]-sub*(pos[i+2]-rest[i+2]))*dt;
        vx*=dmpv;vy*=dmpv;vz*=dmpv; vel[i]=vx;vel[i+1]=vy;vel[i+2]=vz;
        pos[i]+=vx*dt;pos[i+1]+=vy*dt;pos[i+2]+=vz*dt;
      }
    }
  }
''')

rep_engine = [
  ('''    const st=this.stride, V=this.voices, ac=this.aChar||1, pos=this.pos, vel=this.vel, rest=this.rest; let mute=false;
    const gForce=this.windOn||this.fbF!==0||this.bow>0;''',
   '''    const st=this.stride, V=this.voices, ac=this.aChar||1, pos=this.pos, vel=this.vel, rest=this.rest; let mute=false;'''),
  ('''      if(gForce||this.vPul[v].length||this.vPen[v].length||(this.exAny&&this.exF[v]!==0)||this.oscOn[v]){ if(this.vMute[v]) mute=true; continue; }''',
   '''      if(this.vPul[v].length||this.vPen[v].length){ if(this.vMute[v]) mute=true; continue; }'''),
  ('''      if(this.vRest[v]||this.vMute[v]||v===newest||this.oscOn[v]) continue;   // never the newest note or a held key''',
   '''      if(this.vRest[v]||this.vMute[v]||v===newest) continue;   // never the newest note'''),
  ('''    if(this.rv) this.rvClear();   // F: also clear what the Hush fade fed into the reverb
''', ''),
]
for a, b in rep_engine:
    if W.count(a) != 1: sys.exit(f'ABORT engine edit: {a[:80]!r}')
    W = W.replace(a, b)

swap('processInner', r'''
  processInner(inputs, outputs){
    const out=outputs[0]; if(!this.ok){ for(const ch of out) ch.fill(0); return true; }
    const L=out[0], R=out.length>1?out[1]:null, n=L.length;
    const mi=this.micI*3, mv=this.micVec;
    const os=this.os, g=1-Math.exp(-2*Math.PI*Math.min(this.tone,0.45*sampleRate*this.os)/(sampleRate*os));
    const dispK=1/this.aChar, vk=1/(2*Math.PI*this.f0*this.aChar), ak=vk/(2*Math.PI*this.f0);
    this.gateStep=1/Math.max(1,0.010*sampleRate);
    for(let k=0;k<n;k++){
      for(let s=0;s<os;s++){ this.advance(1);
        if(this.voices>1){
          for(let vv=0;vv<this.voices;vv++){
            const vb=vv*this.stride+mi;
            const rv=(this.vel[vb]*mv[0]+this.vel[vb+1]*mv[1]+this.vel[vb+2]*mv[2])
                     /(2*Math.PI*this.vf0[vv]*this.aChar);
            this.vLp[vv]+=g*(rv-this.vLp[vv]); this.vLpB[vv]+=g*(this.vLp[vv]-this.vLpB[vv]);
          }
          continue;
        }
        let raw=0;
        if(this.coilA){
          const A=this.coilA; let a=0;
          for(let c=0;c<A.idx.length;c++){ const q=A.idx[c]*3;
            a+=A.w[c]*(this.vel[q]*mv[0]+this.vel[q+1]*mv[1]+this.vel[q+2]*mv[2]); }
          raw=a*vk;
        } else {
          raw=(this.vel[mi]*mv[0]+this.vel[mi+1]*mv[1]+this.vel[mi+2]*mv[2])*vk;
        }
        this.lp+=g*(raw-this.lp); this.lpB+=g*(this.lp-this.lpB); }
      // FIX3: displacement is normalised by aChar only. The extra *vk made the two
      // blended signals dimensionally incommensurable and drifted the mix with pitch.
      const disp=((this.pos[mi]-this.rest[mi])*mv[0]+(this.pos[mi+1]-this.rest[mi+1])*mv[1]+(this.pos[mi+2]-this.rest[mi+2])*mv[2])*dispK;
      const acc=(this.frc[mi]*mv[0]+this.frc[mi+1]*mv[1]+this.frc[mi+2]*mv[2])*ak;
      let x;
      if(this.voices>1){
        let sv=0, sd=0, sa=0;
        for(let vv=0;vv<this.voices;vv++){
          const vb=vv*this.stride+mi, k=1/(2*Math.PI*this.vf0[vv]*this.aChar);
          sv+=this.vLpB[vv];
          sd+=((this.pos[vb]-this.rest[vb])*mv[0]+(this.pos[vb+1]-this.rest[vb+1])*mv[1]+(this.pos[vb+2]-this.rest[vb+2])*mv[2])*dispK;
          sa+=(this.frc[vb]*mv[0]+this.frc[vb+1]*mv[1]+this.frc[vb+2]*mv[2])*k/(2*Math.PI*this.vf0[vv]);
        }
        const nrm=1/Math.sqrt(this.voices);
        x=((1-this.blend)*sv+this.blend*sd+this.bite*2.6*sa)*nrm;
      } else {
        x=(1-this.blend)*this.lpB+this.blend*disp+this.bite*2.6*acc;
      }
      // FIX1: check the pre-saturation signal.
      if(!isFinite(x)){ this.trips++; this.hardReset(); x=0; }
      // coil inductance + cable capacitance: a resonant low pass with a peak
      {
        const fc=Math.min(this.pkRes,0.45*sampleRate);
        const g=Math.tan(Math.PI*fc/sampleRate), kq=1/Math.max(0.5,this.pkQ);
        const a1=1/(1+g*(g+kq)), a2=g*a1, a3=g*a2;
        const v3=x-this.c2, v1=a1*this.c1+a2*v3, v2=this.c2+a2*this.c1+a3*v3;
        this.c1=2*v1-this.c1; this.c2=2*v2-this.c2;
        const peak=v2+Math.max(0,this.pkQ-1)*3.4*v1;
        x = isFinite(peak) ? peak : (this.c1=0,this.c2=0,0);
      }
      const y=x-this.dcx+0.9985*this.dcy; this.dcx=x; this.dcy=y;
      // FIX7: gate slew instead of instantaneous mute/unmute.
      if(this.gate<this.gateTarget) this.gate=Math.min(this.gateTarget,this.gate+this.gateStep);
      else if(this.gate>this.gateTarget) this.gate=Math.max(this.gateTarget,this.gate-this.gateStep);
      if(this.pendingReset && this.gate<=1e-4){ this.pendingReset=false; this.hardReset(); }
      const st=this.specTrim*(this.shapeTrim||1);
      let o=Math.tanh(y*this.gain*13*(st/Math.min(1.5,Math.max(0.35,st))))*this.gate;
      if(!isFinite(o)) o=0;
      const ao=o<0?-o:o; if(ao>this.peak) this.peak=ao;
      let ll=o, rr=o;
      if(this.lvl!==1){ ll*=this.lvl; rr*=this.lvl; }          // F3: per-shape level calibration
      if(!isFinite(ll)) ll=0; if(!isFinite(rr)) rr=0;
      { // F2: true-peak lookahead limiter, ceiling -1 dBTP. Gain is exactly 1 below the ceiling.
        const B=this.tpL, C=this.tpR, I=this.tpI, D=this.tpD, Cc=this.limC;
        B[I]=ll; C[I]=rr;
        // peak around the sample 8 behind the newest, including the three points between it and the next
        const c0=(I-8)&31; let pk=Math.max(Math.abs(B[c0]),Math.abs(C[c0]));
        let near=0; for(let j=0;j<16;j++){ const q=(I-15+j)&31; const a=Math.max(Math.abs(B[q]),Math.abs(C[q])); if(a>near) near=a; }
        if(near>Cc*0.3){ for(let f=0;f<3;f++){ const K=this.tpK[f]; let xl=0,xr=0;
            for(let j=0;j<16;j++){ const q=(I-15+j)&31; xl+=B[q]*K[j]; xr+=C[q]*K[j]; }
            const a=Math.max(Math.abs(xl),Math.abs(xr)); if(a>pk) pk=a; } }
        this.tpGr[c0]=pk>Cc?Cc/pk:1;
        let need=1; for(let j=0;j<24;j++){ const q=(I-8-j)&31; if(this.tpGr[q]<need) need=this.tpGr[q]; }
        let g=this.limG; if(g<1){ g+=(1-g)*this.limRel; if(g>0.99999) g=1; } if(need<g) g=need;
        this.limG=g; const o=(I-D)&31; let ol=B[o], or=C[o]; if(g<1){ ol*=g; or*=g; }
        this.tpI=(I+1)&31;
        L[k]=ol; if(R) R[k]=or; }
    }
    // FIX1: periodic full-state scan catches Infinity that tanh would have hidden.
    if(this.voices>1){
      this.vscan=(this.vscan||0)+n;
      if(this.vscan>=2048){
        this.vscan=0;
        for(let v=0;v<this.voices;v++){
          if(!this.vOn[v]) continue;
          const b=v*this.stride; let mx=0;
          for(let i=b;i<b+this.stride;i++){ const q=Math.abs(this.vel[i]); if(q>mx) mx=q; }
          if(mx*(1/(2*Math.PI*this.vf0[v]*this.aChar))<0.0015 && !this.vPul[v].length && !this.vPen[v].length)
            this.vOn[v]=0;
        }
      }
    }
    if(this.perfSleep||this.anyMute){   // P1
      this.slScan+=n; if(this.slScan>=1024){ this.slScan=0; this.sleepCheck(this.perfSleep); }
    }
    this.scan+=n;
    if(this.scan>=128){
      this.scan=0;
      const g=this.govern(vk,dispK);
      if(g===2){
        this.trips++;
        // Rewind to the last state that was verifiably sane rather than wiping
        // the note. Only a cold start with nothing banked falls back to reset.
        if(this.haveGood){
          const lv=Math.max(1,this.voices)*this.stride;
          this.pos.set(this.goodPos.subarray(0,lv)); this.vel.set(this.goodVel.subarray(0,lv));
          for(let i=0;i<lv;i++) this.vel[i]*=0.35;
          this.vRest.fill(0);   // P1: a rewind can put any voice back in motion
          this.lp=0; this.lpB=0; this.dcx=0; this.dcy=0;
          this.c1=0; this.c2=0;
        } else this.hardReset();
      }
      else { if(g===1) this.governed++; else { const lv=Math.max(1,this.voices)*this.stride;
        this.goodPos.set(this.pos.subarray(0,lv)); this.goodVel.set(this.vel.subarray(0,lv));
        this.haveGood=true; } }
    }
    this.tick+=n;
    if(this.tick>=1400){
      this.tick=0;
      // Meter only: keep audio physics internal and do not ship body motion to the UI.
      const fr={t:'frame',pk:this.peak};
      fr.cpu=this.cpu; fr.cpuMax=this.cpuMax; fr.aw=this.awakeCount(); fr.cap=Math.min(this.vCap,this.voices); fr.ga=this.govActs; fr.sl=this.sleeps;   // P1
      this.port.postMessage(fr);
      this.peak*=0.55;
    }
    return true;
  }
''')

rep_hard = ('''    this.lp=0; this.lpB=0; this.lp2B=0; this.dcx=0; this.dcy=0;''', '''    this.lp=0; this.lpB=0; this.dcx=0; this.dcy=0;''')
if W.count(rep_hard[0]) != 1: sys.exit('ABORT hardReset')
W = W.replace(*rep_hard)

# the controls the engine accepts
hdr = 'const SR_SOFT=24000;   // a soft catch protects for this many samples\n'
if W.count(hdr) != 1: sys.exit('ABORT header')
W = W.replace(hdr, hdr + "const KEYS=new Set(['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices','osMax']);   // J1\n")

# nothing of the removed layers may remain
for word in ['this.mods', 'this.att', 'this.rv', 'this.fx', 'this.spImg', 'this.spL', 'this.spDist', 'this.xm', 'this.osc', 'this.wind', 'this.bow',
             'this.fbF', 'this.fbAmt', 'this.coup', 'this.regime', 'this.mem', 'this.infer', 'this.micJ', 'this.micVec2',
             'this.pkType', 'this.coilB', 'this.amp', 'this.cab', 'this.bass', 'this.treb', 'this.rec', 'this.width',
             'this.mode', 'this.splash', 'this.exAny', 'this.exF', 'this.fOn', 'this.spec ', 'this.spec=', 'modBase', 'coupBase']:
    mm = re.search(re.escape(word.strip()) + (r'\b' if word.strip()[-1].isalnum() else ''), W)
    if mm:
        i = mm.start(); sys.exit(f'ABORT: leftover {word!r}: ...{W[max(0, i - 80):i + 60]!r}')

s = s[:w0] + W + s[w1:]

# ------------------------------------------------------------------ page
# the unused first Tank definition (the second one always won) and the other seven shapes
a = s.index('const SHAPES = {\n'); b = s.index('\n};', a) + 3
SH = s[a:b]
t1 = SH.index("  Tank:{min:6,max:12,def:8,"); t2 = SH.index("  Tank:{min:5,max:9,def:7,")
t3 = SH.index("  Twins:{")
s = s[:a] + 'const SHAPES = {\n' + SH[t2:t3].rstrip().rstrip(',') + '\n};' + s[b:]

# knobs: only what the page shows
a = s.index('const KNOBS={\n'); b = s.index('\n};', a) + 3
KN = s[a:b]
keep = ['size', 'mag', 'ratio', 'decay', 'loss', 'sub', 'drive', 'hard', 'voices', 'tune', 'hit', 'mic', 'blend', 'gain',
        'tone', 'bite', 'nl', 'angle']
lines = KN.split('\n')
out = [lines[0]]
for ln in lines[1:-1]:
    m = re.match(r'\s*([a-zA-Z0-9]+):\{', ln)
    if not m: sys.exit(f'ABORT knob line: {ln[:60]!r}')
    if m.group(1) in keep: out.append(ln.rstrip(','))
got = [re.match(r'\s*([a-zA-Z0-9]+):', ln).group(1) for ln in out[1:]]
if sorted(got) != sorted(keep): sys.exit(f'ABORT knobs: {got}')
s = s[:a] + out[0] + '\n' + ',\n'.join(out[1:]) + '\n};' + s[b:]

rep("const SHAPE_LVL={String:1.4928,Tine:0.8082,Chime:0.866,Drum:0.9784,Hoop:1.5171,Web:0.7379,Tank:8.8716,Twins:1.8793};",
    "const SHAPE_LVL={Tank:8.8716};")
a = s.index('const RATE=v=>'); b = s.index("const SCALES=")
s = s[:a] + s[b:]

SENDS_OLD = "for(const k of ['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','width','pkAp','pkSpc','pkRes','pkQ','amp','bass','treb','cab','splash','fbAmt','fbTime','voices','coup','regime','rswitch','rphi','mem','memSpan','infer','spread','att','attC','fxCho','fxDly','fxFb','fxWow','fxTrem','fxSat','spImg','spDist','spRefl','spDop','spRot','spElev','bowSpd','bowVc','wind','inGain','rvMix','rvTime','rvTone','rvPre'])send(k);"
SENDS_NEW = "for(const k of SENDS)send(k);"
rep(SENDS_OLD, SENDS_NEW, 2)
rep('''   node.port.postMessage({t:'pk',v:state.pk||0});
   node.port.postMessage({t:'mode',v:state.mode||0});
   node.port.postMessage({t:'spec',v:state.spec||0});sendLvl();}''', '''   sendLvl();}''')
rep('''  node.port.postMessage({t:'pk',v:state.pk||0});
  node.port.postMessage({t:'mode',v:state.mode||0});
  sendLvl();''', '''  sendLvl();''')
rep("function send(k){if(node)node.port.postMessage({t:'p',k,v:val[k]});}",
    "function send(k){if(node)node.port.postMessage({t:'p',k,v:val[k]});}\n"
    "const SENDS=['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices'];   // J1: every control the engine has")
rep("const state={shape:'Tank',n:7,scale:0,root:52,micIdx:0,micIdx2:0,hitIdx:0,pk:0,mode:0,spec:0,axis:1,",
    "const state={shape:'Tank',n:7,scale:0,root:52,micIdx:0,hitIdx:0,axis:1,")
# the second pickup only existed for Stereo
rep('''function placeMicHit(){
 const F=state.free;if(!F.length)return;
 const n=F.length;
 state.micIdx=F[Math.min(n-1,Math.round(val.mic*(n-1)))];
 state.hitIdx=F[Math.min(n-1,Math.round(val.hit*(n-1)))];
 // second pickup sits as far from the first as the body allows
 state.micIdx2=F[(Math.round(val.mic*(n-1))+Math.max(1,Math.floor(n/2)))%n];
 if(node){
   node.port.postMessage({t:'mic',i:state.micIdx,a:state.axis});
   node.port.postMessage({t:'mic2',i:state.micIdx2});
   node.port.postMessage({t:'hit',i:state.hitIdx,a:state.axis});
 }
}''', '''function placeMicHit(){
 const F=state.free;if(!F.length)return;
 const n=F.length;
 state.micIdx=F[Math.min(n-1,Math.round(val.mic*(n-1)))];
 state.hitIdx=F[Math.min(n-1,Math.round(val.hit*(n-1)))];
 if(node){
   node.port.postMessage({t:'mic',i:state.micIdx,a:state.axis});
   node.port.postMessage({t:'hit',i:state.hitIdx,a:state.axis});
 }
}''')
rep('''// H: send the strike and both mics where the page has them (the second mic as the mic tool places it)
function pickSend(){ if(!node) return; const F=state.free, n=F.length; if(!n) return;
  const k=Math.max(0,F.indexOf(state.micIdx)); state.micIdx2=F[(k+Math.max(1,Math.floor(n/2)))%n];
  node.port.postMessage({t:'mic',i:state.micIdx,a:state.axis}); node.port.postMessage({t:'mic2',i:state.micIdx2});
  node.port.postMessage({t:'hit',i:state.hitIdx,a:state.axis}); }''', '''// H: send the strike and the mic where the page has them
function pickSend(){ if(!node) return; if(!state.free.length) return;
  node.port.postMessage({t:'mic',i:state.micIdx,a:state.axis});
  node.port.postMessage({t:'hit',i:state.hitIdx,a:state.axis}); }''')
rep('''    if(node){ node.port.postMessage({t:'mic',i,a:state.axis});
      const F=state.free,nn=F.length; state.micIdx2=F[(Math.max(0,F.indexOf(i))+Math.max(1,Math.floor(nn/2)))%Math.max(1,nn)];
      node.port.postMessage({t:'mic2',i:state.micIdx2}); } }''', '''    if(node) node.port.postMessage({t:'mic',i,a:state.axis}); }''')
rep('''    pk:0,mode:0,spec:0,micIdx:state.micIdx,hitIdx:state.hitIdx,''', '''    pk:0,mode:0,spec:0,micIdx:state.micIdx,hitIdx:state.hitIdx,   // J1: pk/mode/spec kept so the main Resonator reads these presets as before''')
rep('''  state.pk=0; state.mode=0; state.spec=0;   // I: one pickup, the mallet, no specialization: the old defaults
''', '')
rep('''  if(node) node.port.postMessage({t:'spec',v:0});
  buildPads();''', '''  buildPads();''')
rep('''// I: Tank only. The controls that are kept; every other control stays at its old default and is still sent
// to the engine as before, so the Tank sounds exactly as it did. A preset cannot switch a removed one back on.''',
    '''// I: Tank only. The controls that are kept. J1: the engine has no other controls left, so a preset cannot
// switch a removed one back on.''')
rep("  for(const k in KNOBS) if(!KEEP.has(k)) val[k]=KNOBS[k].val;   // I\n", '')

for word in ["t:'mic2'", "t:'pk'", "t:'mode'", "t:'spec'", 'micIdx2', 'fmtRate', 'MDEST']:
    if word in s:
        i = s.index(word); sys.exit(f'ABORT: page leftover {word!r}: ...{s[max(0, i - 80):i + 60]!r}')

open(P, 'w', encoding='utf-8').write(s)
print('patch_j1: ok')
