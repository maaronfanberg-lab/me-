# Stage T1 (preview): the water tower. docs/research/resonator-tower-T1-2026-10-12.md
#  Engine (all additive; the Tank's sound is bit-identical, t1_verify.mjs):
#   - a body may carry a probe (a displacement pattern); the tuning reference is then the mode that overlaps it
#     most, instead of the loudest one. The tower's probe is the bowl swelling outward (the breathing mode, the
#     one that changes its volume), which a finite-element model of the oblate bowl puts at 129 Hz for any
#     wall from 10 to 25 mm (tower_fe.py). So the keys tune the breathing mode, and the boom lies below it.
#   - the padded mallet: Padding (leather, wool, Styrofoam, rubber) simulates a 200 kg head hitting through its
#     pad with the same force laws as tower_acoustics.py, at real size, and strikes the body with that force
#     history, its duration scaled with the tower (a smaller tower is hit by a proportionally smaller mallet).
#  Page: the Tower body (Size = nodes round the bowl), shape chips (Tank | Tower), Padding chips, Real size and
#  Phone size, the tower's height for the keys, presets for both bodies.
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

# ================================ engine ================================
rep("const KEYS=new Set(['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices','osMax']);   // J1",
    "const KEYS=new Set(['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices','osMax','pad','padRef']);   // J1, T1: pad, padRef")
rep("""    this.specTrim=2.6;   // J1: the level trim of the old 'even' specialization, which the Tank always used
""", """    this.specTrim=2.6;   // J1: the level trim of the old 'even' specialization, which the Tank always used
    this.pad=0; this.padRef=52; this.probe=null; this.padLast=null;   // T1: padded mallet (0 = the ordinary mallet), tuning probe
""")
rep("""    this.fixed=Uint8Array.from(d.fixed); this.si=Int32Array.from(d.si); this.sj=Int32Array.from(d.sj);
    this.sa=new Float64Array(S); this.su=new Float64Array(S*3);
    const deg=new Int32Array(N);""", """    this.fixed=Uint8Array.from(d.fixed); this.si=Int32Array.from(d.si); this.sj=Int32Array.from(d.sj);
    this.probe=(d.probe&&d.probe.length===N*3)?Float64Array.from(d.probe):null;   // T1
    this.sa=new Float64Array(S); this.su=new Float64Array(S*3);
    const deg=new Int32Array(N);""")
rep("""      cmp+=h*h/lam[m];   // S3: static compliance at the strike point
      out.push({f:w/(2*Math.PI), amp:Math.abs(h*c)/w});""", """      cmp+=h*h/lam[m];   // S3: static compliance at the strike point
      const o={f:w/(2*Math.PI), amp:Math.abs(h*c)/w};
      if(this.probe){   // T1: how much of this mode is the probe's shape (normalised overlap, 0..1)
        const pr=this.probe; let dot=0, pp=0;
        for(let q=0;q<this.N;q++){ const dq=this.map[q]; if(dq<0) continue;
          for(let a=0;a<3;a++){ const u=pr[q*3+a]; dot+=V[(3*dq+a)*n+m]*u; pp+=u*u; } }
        o.ov=(tot>0&&pp>0)?dot*dot/(tot*pp):0;
      }
      out.push(o);""")
rep("""    let bi=0; for(let i=1;i<sp0.length;i++) if(sp0[i].amp>sp0[bi].amp) bi=i;""",
    """    let bi=0; for(let i=1;i<sp0.length;i++) if(sp0[i].amp>sp0[bi].amp) bi=i;
    if(this.probe){ let bo=-1, bv=-1; for(let i=0;i<sp0.length;i++) if((sp0[i].ov||0)>bv){ bv=sp0[i].ov||0; bo=i; } if(bo>=0) bi=bo; this.probeOv=bv; }   // T1""")
rep("""  strike(v){
    this.pulses.length=0; this.pending.length=0;
    let secs=""", """  strike(v){
    this.pulses.length=0; this.pending.length=0;
    if(this.pad>0){ this.padStrike(v); return; }   // T1
    let secs=""")
rep("""  advance(dt_scale){""", r"""  // T1: the padded mallet. A 200 kg head swung at 5 m/s x key strength x Drive (strength 0.8 = 4 m/s) hits a
  // rigid wall through 8 cm of padding over a 0.6 m face; the force law is the padding's (tower_acoustics.py):
  //   1 thick leather over a hard core: linear, E ~ 30 MPa over 2 cm, 15% hysteresis
  //   2 thick wool: hardening, F = K x^2.5 (Russell 1997, p 2-3.5), 30% hysteresis
  //   3 tightly compressed Styrofoam (EPS 48 kg/m3): elastic to its crush stress (414 kPa, AFM data), then a plateau
  //     while it crushes; it unloads from its dented shape (a fresh pad each strike)
  //   4 rubber: Hertz-like, F ~ x^1.5, E ~ 4 MPa, 10% hysteresis
  // Integrated at 2 us, real size. The force history becomes the strike's shape; its length is scaled by
  // padRef / pitch, so at real size (the reference mode at padRef Hz) the contact lasts as long as it really
  // would, and on a smaller tower (higher keys) the mallet shrinks with it. The impulse follows the rebound:
  // m v0 (1 + e), relative to the ordinary mallet's.
  padForce(law,x,u,st){
    if(x<=0) return 0;
    const A=Math.PI*0.09, s=u>=0?1:-1;
    if(law===1) return 30e6*A/0.02*x*(1+0.15*s);
    if(law===2) return 4.0e8*Math.pow(x,2.5)*(1+0.3*s);
    if(law===3){ const t=0.08, sc=414e3, ys=sc/6e6;
      if(x<=st.xp) return 0;
      if(u>0&&(x-st.xp)/t>=ys){ st.xp=x-ys*t; return sc*A; }
      return 6e6*A*(x-st.xp)/t; }
    return 4e6*A/0.08*Math.pow(x,1.5)/Math.sqrt(0.02)*(1+0.1*s);
  }
  padContact(law,v0){
    const mH=200, dt=2e-6, st={xp:0}, H=[]; let x=0, u=v0, n=0;
    while(n<200000){
      const F=this.padForce(law,x,u,st); u-=F/mH*dt; x+=u*dt; n++;
      if((n&3)===0) H.push(F>0?F:0);
      if(x<=st.xp&&u<0&&n>10) break;
    }
    const tau=n*dt, K=96, tab=new Float64Array(K); let mx=0;
    for(let i=0;i<H.length;i++) if(H[i]>mx) mx=H[i];
    for(let k=0;k<K;k++){ const p=k/(K-1)*(H.length-1), i=Math.floor(p), f=p-i; const a=H[i]||0, b=H[Math.min(H.length-1,i+1)]||0; tab[k]=mx>0?(a+(b-a)*f)/mx:0; }
    let mean=0; for(let k=0;k<K-1;k++) mean+=0.5*(tab[k]+tab[k+1]); mean/=(K-1);
    return {tau, e:Math.max(0,-u/v0), tab, mean:mean||0.5, peak:mx, dent:st.xp};
  }
  padStrike(v){
    const law=Math.max(1,Math.min(4,this.pad|0)), v0=5*v*this.drive;
    const c=this.padContact(law,v0);
    const sr=sampleRate, os=this.os;
    const secs=c.tau*this.padRef/Math.max(20,this.f0);
    const dur=Math.max(2,secs*sr*os);
    const J=1.1*this.drive*v*this.f0*this.aChar*1.5*(1+c.e)/1.75;
    this.pulses.push({left:dur,dur,amp:J*sr*os/(dur*c.mean),tab:c.tab});
    this.padLast={tau:c.tau,e:c.e,secs,peak:c.peak,dent:c.dent};
  }
  advance(dt_scale){""")
rep("""          const p=pul[q];
          const t=1-p.left/p.dur, w=Math.sin(Math.PI*t);
          A+=p.amp*w*w;""", """          const p=pul[q];
          if(p.tab){   // T1: the padded mallet's own force history
            const T=p.tab, x=(1-p.left/p.dur)*(T.length-1), i=x|0, f=x-i;
            A+=p.amp*(i>=T.length-1?T[T.length-1]:T[i]+(T[i+1]-T[i])*f);
          } else {
          const t=1-p.left/p.dur, w=Math.sin(Math.PI*t);
          A+=p.amp*w*w;
          }""")
rep("""      kT:this.kT, kL:this.kL, capped:this.capped, deg:this.deg,""", """      kT:this.kT, kL:this.kL, capped:this.capped, deg:this.deg, probeOv:this.probe?this.probeOv:undefined,""")

# ================================ the tower body ================================
TOWER = r"""  Tower:{min:10,max:18,def:14,ratio:14,decay:1.6,root:64,
    note:'The water tower in Superior, Wisconsin, empty: a steel spheroid 23 m across and 17.5 m tall on a column 5 m across, 35 m to the roof. Its bowl is a shell whose modes crowd together, so it booms rather than rings a note. A key tunes the breathing mode, the whole bowl swelling and shrinking; the boom of the many lobed modes lies below it, about an octave down. At real size the breathing mode is 129 Hz, about C3.',
    make(E){
      // Dimensions in metres (docs/research/resonator-water-tower-2026-10-12.md), drawn 0.74 units tall standing at y0. The bowl is meshed by arc length with rings whose node counts follow their circumference,
      // stitched into near-equilateral triangles (a membrane shell needs that, or it shears). The bowl is clamped where
      // it meets the cone neck; the column below is its own shell, clamped at the neck and at the ground.
      const s=0.74/35, y0=0.40, a=11.5, b=8.75, yc=35-b, rc=2.5, rb=5, thN=156*Math.PI/180;
      const P=[],F=[],S=[],tag=[],rings=[],BR=[];
      const add=(x,y,z,k,f)=>{P.push([x*s,y0-y*s,z*s]);F.push(f?1:0);tag.push(k);return P.length-1;};
      const ring=(y,r,n,k,f,ph)=>{const ids=[];for(let j=0;j<n;j++){const t=2*Math.PI*(j+ph)/n;ids.push(add(r*Math.cos(t),y,r*Math.sin(t),k,f));}rings.push(ids);return ids;};
      const arc=th=>{let L=0;for(let i=0;i<400;i++){const t=(i+0.5)*th/400;L+=Math.hypot(a*Math.cos(t),b*Math.sin(t))*th/400;}return L;};
      const Lt=arc(thN), h=(2*Math.PI*a/E)*Math.sqrt(3)/2, nR=Math.max(2,Math.round(Lt/h));
      const thAt=L=>{let lo=0,hi=thN;for(let i=0;i<40;i++){const m=(lo+hi)/2;if(arc(m)<L)lo=m;else hi=m;}return (lo+hi)/2;};
      BR.push([add(0,yc+b,0,'bowl',false)]);
      for(let k=1;k<nR;k++){const th=thAt(Lt*k/nR),r=a*Math.sin(th);BR.push(ring(yc+b*Math.cos(th),r,Math.max(3,Math.round(E*r/a)),'bowl',false,k*0.5));}
      const neck=ring(yc+b*Math.cos(thN),a*Math.sin(thN),Math.max(3,Math.round(E*Math.sin(thN))),'neck',true,nR*0.5);BR.push(neck);
      const link=(i,j)=>{if(!(F[i]&&F[j]))S.push([i,j]);};
      const ang=i=>Math.atan2(P[i][2],P[i][0]), norm=x=>((x%(2*Math.PI))+2*Math.PI)%(2*Math.PI);
      const zip=(A,B)=>{   // triangulate the band between two rings (either may be a single pole)
        if(A.length===1||B.length===1){const p=A.length===1?A[0]:B[0],R=A.length===1?B:A;for(const q of R)link(p,q);return;}
        const first=R=>{let k=0,best=9;R.forEach((q,i)=>{const d=norm(ang(q));if(d<best){best=d;k=i;}});return k;};
        const i=first(A),j=first(B),nA=A.length,nB=B.length,base=norm(Math.min(norm(ang(A[i])),norm(ang(B[j])))-1e-9),rel=q=>norm(ang(q)-base);
        let ai=0,bj=0;link(A[i],B[j]);
        while(ai<nA||bj<nB){
          const na=ai<nA?(ai+1<nA?rel(A[(i+ai+1)%nA]):2*Math.PI+rel(A[i])):Infinity;
          const nb=bj<nB?(bj+1<nB?rel(B[(j+bj+1)%nB]):2*Math.PI+rel(B[j])):Infinity;
          if(na<=nb)ai++;else bj++;
          if(ai===nA&&bj===nB)break;
          link(A[(i+ai)%nA],B[(j+bj)%nB]);
        }};
      for(const R of rings)if(R.length>2)for(let j=0;j<R.length;j++)link(R[j],R[(j+1)%R.length]);
      for(let k=0;k<BR.length-1;k++)zip(BR[k],BR[k+1]);
      const nc=Math.max(4,Math.round(E*rc/a*1.6)),yN=yc+b*Math.cos(thN);let prev=neck;
      [[yN-3,rc*1.15,'column'],[16,rc,'column'],[9,rc,'column'],[3.2,rb*0.62,'base']].forEach(([y,r,k],i,all)=>{const R=ring(y,r,i===all.length-1?Math.round(nc*1.3):nc,k,false,i*0.5);zip(prev,R);prev=R;});
      zip(prev,ring(0,rb,Math.round(nc*1.6),'ground',true,0.25));
      // strike and mic on the bowl's widest ring, opposite sides, both square on (Mic axis X)
      let eq=BR[1];for(const R of BR)if(R.length>1&&Math.hypot(P[R[0]][0],P[R[0]][2])>Math.hypot(P[eq[0]][0],P[eq[0]][2]))eq=R;
      const near=t=>{let k=eq[0],best=9;for(const q of eq){const d=Math.abs(norm(ang(q)-t+Math.PI)-Math.PI);if(d<best){best=d;k=q;}}return k;};
      // tuning probe: the whole bowl swelling outward along its normal (the breathing mode, which changes its volume)
      const probe=new Float32Array(P.length*3);
      for(let i=0;i<P.length;i++){if(tag[i]!=='bowl'||F[i])continue;
        const x=P[i][0]/s/a,yy=((y0-P[i][1])/s-yc)/b,z=P[i][2]/s/a;
        let nx=x/a,ny=-yy/b,nz=z/a;const nl=Math.hypot(nx,ny,nz)||1;   // y is drawn downward
        probe[i*3]=nx/nl;probe[i*3+1]=ny/nl;probe[i*3+2]=nz/nl;}
      return {P,F,S,axis:0,mic:near(Math.PI),hit:near(0),needSub:0,probe,tag,bowlRings:BR,dims:{s,a,b,yc,y0}};}}"""
rep("""    return {P,F,S,axis:1,mic:mid[0],hit:rings[K][Math.floor(C/2)],needSub:0.0004};}}
};""", """    return {P,F,S,axis:1,mic:mid[0],hit:rings[K][Math.floor(C/2)],needSub:0.0004};}},
""" + TOWER + """
};""")
rep("const SHAPE_LVL={Tank:8.8716};", "const SHAPE_LVL={Tank:8.8716,Tower:4.45};")
rep("const state={shape:'Tank',n:7,scale:0,root:52,micIdx:0,hitIdx:0,axis:1,",
    "const state={shape:'Tank',n:7,scale:0,root:52,micIdx:0,hitIdx:0,axis:1,pad:2,")
# body defaults (the knobs a body asks for), shape and padding chips, real size
rep("""const SENDS=['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices'];   // J1: every control the engine has""",
    """const SENDS=['ratio','decay','loss','sub','drive','hard','blend','gain','tune','tone','bite','nl','angle','voices'];   // J1: every control the engine has
// T1: the padded mallet (the Tower only) and the tower's true size. padRef: the breathing mode at real size (Hz),
// from the finite-element model (qa-resonator/tower_fe.py); the mallet's contact time scales with padRef / pitch.
const PADS=['Leather','Wool','Styrofoam','Rubber'], TOWER_REF=129.0, TOWER_H=35;
function sendPad(){ if(!node) return; node.port.postMessage({t:'p',k:'pad',v:state.shape==='Tower'?state.pad:0}); node.port.postMessage({t:'p',k:'padRef',v:TOWER_REF}); }""")
rep("""postStruct({t:'struct',n:g.P.length,pos,fixed:Uint8Array.from(g.F),si:Int32Array.from(g.S.map(s=>s[0])),sj:Int32Array.from(g.S.map(s=>s[1])),mic:state.micIdx,hit:state.hitIdx,axis:g.axis});for(const k of SENDS)send(k);
   sendLvl();}""", """const sm={t:'struct',n:g.P.length,pos,fixed:Uint8Array.from(g.F),si:Int32Array.from(g.S.map(s=>s[0])),sj:Int32Array.from(g.S.map(s=>s[1])),mic:state.micIdx,hit:state.hitIdx,axis:g.axis};if(g.probe)sm.probe=Float32Array.from(g.probe);postStruct(sm);for(const k of SENDS)send(k);
   sendPad();sendLvl();}""")
rep(""" document.getElementById('bodytext').textContent=S.note;state.geo.note=S.note;[...axesEl.children].forEach((c,j)=>c.setAttribute('aria-pressed',j===state.axis));state.disp=new Float32Array(g.P.length*3);state.spd=new Float32Array(g.P.length);drawInfo();
}""", """ document.getElementById('bodytext').textContent=S.note;state.geo.note=S.note;[...axesEl.children].forEach((c,j)=>c.setAttribute('aria-pressed',j===state.axis));state.disp=new Float32Array(g.P.length*3);state.spd=new Float32Array(g.P.length);syncBody();drawInfo();
}
// T1: what changes with the body: the label, the shape chips, the mallet (Mallet knob or Padding), the size row
function syncBody(){
 const tw=state.shape==='Tower', br=document.getElementById('brand'); if(br) br.textContent='RESONATOR · '+state.shape.toUpperCase();
 document.querySelectorAll('[data-shape]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.shape===state.shape)));
 const hk=document.querySelector('.knob[data-k="hard"]'); if(hk) hk.hidden=tw;
 const tp=document.getElementById('towerbits'); if(tp) tp.hidden=!tw;
 document.querySelectorAll('[data-pad]').forEach(x=>x.setAttribute('aria-pressed',String(+x.dataset.pad===state.pad)));
 sizeNote();
}
// the height of the tower the lowest key plays: the breathing mode is 129 Hz at 35 m and scales inversely with size
function towerHeight(midi){ return TOWER_H*TOWER_REF/(440*Math.pow(2,(midi-69)/12)*Math.pow(2,(val.tune||0)/1200)); }
function sizeNote(){ const el=document.getElementById('sizenote'); if(!el) return;
 if(state.shape!=='Tower'){ el.textContent=''; return; }
 const hm=towerHeight(state.root), lo=NAMES[state.root%12]+(Math.floor(state.root/12)-1);
 el.textContent='The lowest key ('+lo+') plays a tower '+(hm>=10?hm.toFixed(0):hm.toFixed(1))+' m tall'+(Math.abs(hm/TOWER_H-1)<0.03?' — real size. Its boom is mostly below what a phone speaker can play; use headphones or a speaker.':hm>TOWER_H?', bigger than the real one.':', '+(TOWER_H/hm).toFixed(1)+'× smaller than the real one.');
}
// switching bodies: the new body's own defaults for Size, Stiffness, Sustain and Substrate
function setShape(nm){
 if(!SHAPES[nm]||nm===state.shape) return;
 const S=SHAPES[nm]; state.shape=nm; state.n=S.def; val.size=(S.def-S.min)/(S.max-S.min); syncKnob('size');
 state.root=S.root||52; buildPads();
 if(S.ratio!=null){val.ratio=S.ratio;syncKnob('ratio');} else {val.ratio=KNOBS.ratio.val;syncKnob('ratio');}
 if(S.decay!=null){val.decay=S.decay;syncKnob('decay');} else {val.decay=KNOBS.decay.val;syncKnob('decay');}
 val.sub=KNOBS.sub.val; syncKnob('sub');
 buildShape(true); say(nm==='Tower'?'The water tower. Tap a key, or move the strike circle round the bowl or down the column.':'The tank.');
}""")
rep("""function rebuild(){
  const g=state.geo; if(!g||!node) return;
  state.free=g.P.map((_,i)=>i).filter(i=>!g.F[i]);
  const pos=new Float32Array(g.P.length*3);
  g.P.forEach((p,i)=>{pos[i*3]=p[0];pos[i*3+1]=p[1];pos[i*3+2]=p[2];});
  postStruct({t:'struct',n:g.P.length,pos,fixed:Uint8Array.from(g.F),
    si:Int32Array.from(g.S.map(s=>s[0])),sj:Int32Array.from(g.S.map(s=>s[1])),
    mic:state.micIdx,hit:state.hitIdx,axis:state.axis});
  for(const k of SENDS)send(k);
  sendLvl();""", """function rebuild(){
  const g=state.geo; if(!g||!node) return;
  state.free=g.P.map((_,i)=>i).filter(i=>!g.F[i]);
  const pos=new Float32Array(g.P.length*3);
  g.P.forEach((p,i)=>{pos[i*3]=p[0];pos[i*3+1]=p[1];pos[i*3+2]=p[2];});
  const sm={t:'struct',n:g.P.length,pos,fixed:Uint8Array.from(g.F),
    si:Int32Array.from(g.S.map(s=>s[0])),sj:Int32Array.from(g.S.map(s=>s[1])),
    mic:state.micIdx,hit:state.hitIdx,axis:state.axis};
  if(g.probe) sm.probe=Float32Array.from(g.probe);   // T1
  postStruct(sm);
  for(const k of SENDS)send(k);
  sendPad(); sendLvl();""")
# presets: both bodies
rep("""const tankPreset=o=>!!(o&&o.P&&(o.shape||'Tank')==='Tank');""",
    """const tankPreset=o=>!!(o&&o.P&&SHAPES[o.shape||'Tank']);   // T1: a body this version has (Tank or Tower)""")
rep("""  if(!tankPreset(o)) return false;
  state.shape='Tank'; state.n=o.n||state.n;""", """  if(!tankPreset(o)) return false;
  state.shape=o.shape||'Tank'; state.n=o.n||state.n;
  if(state.shape==='Tower') state.pad=(o.pad>=1&&o.pad<=4)?o.pad:2;   // T1""")
rep("""  state.geo={P:o.P.map(p=>p.slice()),F:Uint8Array.from(o.F),S:o.S.map(s=>s.slice()),
             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:'',shape:state.shape,n:state.n};   // S2""",
    """  state.geo={P:o.P.map(p=>p.slice()),F:Uint8Array.from(o.F),S:o.S.map(s=>s.slice()),
             axis:state.axis,mic:o.micIdx,hit:o.hitIdx,note:'',shape:state.shape,n:state.n};   // S2
  if(state.shape==='Tower'){ const g0=SHAPES.Tower.make(state.n); if(g0.P.length===state.geo.P.length) state.geo.probe=g0.probe; }   // T1: the tuning probe is not stored""")
rep("""  rebuild();
  state.micIdx=want.m; state.hitIdx=want.h; state.axis=want.a; pickSend();
  buildPads();
  return true;""", """  rebuild();
  state.micIdx=want.m; state.hitIdx=want.h; state.axis=want.a; pickSend();
  { const S=SHAPES[state.shape]; val.size=Math.max(0,Math.min(1,(state.n-S.min)/(S.max-S.min))); syncKnob('size'); }   // T1
  syncBody(); buildPads();
  return true;""")
rep("""    pk:0,mode:0,spec:0,micIdx:state.micIdx,hitIdx:state.hitIdx,""", """    pk:0,mode:0,spec:0,pad:state.shape==='Tower'?state.pad:0,micIdx:state.micIdx,hitIdx:state.hitIdx,""")
rep("""  // I: only Tank presets are listed; presets of the removed shapes stay in storage for the main Resonator
  const tanks=names.filter(nm=>tankPreset(all[nm]));""", """  // I: only presets for the bodies this version has are listed; the others stay in storage for the main Resonator
  const tanks=names.filter(nm=>tankPreset(all[nm]));""")
rep("""say('Press the mic or strike circle and slide it along the tank.');   // I""", """say('Press the mic or strike circle and slide it along the body.');   // I""")
# readout: the tower's size for the lowest key
rep("""function drawInfo(){
 const i=state.info,g=state.geo,el=document.getElementById('readout');
 if(!g){el.innerHTML='';return;}
 let s=`<b>${g.P.length}</b> masses &nbsp; <b>${g.S.length}</b> springs<br>`;""", """function drawInfo(){
 const i=state.info,g=state.geo,el=document.getElementById('readout');
 if(!g){el.innerHTML='';return;}
 let s=`<b>${g.P.length}</b> masses &nbsp; <b>${g.S.length}</b> springs<br>`;
 if(state.shape==='Tower'){ const hm=towerHeight(state.root); s+=`lowest key: a <b>${hm>=10?hm.toFixed(0):hm.toFixed(1)} m</b> tower<br>`; }""")
# scale chips and keys: the size note follows the keys
rep("""for(const b of document.querySelectorAll('[data-scale]'))b.onclick=()=>{state.scale=+b.dataset.scale;document.querySelectorAll('[data-scale]').forEach(x=>x.setAttribute('aria-pressed',x===b));buildPads();};""",
    """for(const b of document.querySelectorAll('[data-scale]'))b.onclick=()=>{state.scale=+b.dataset.scale;document.querySelectorAll('[data-scale]').forEach(x=>x.setAttribute('aria-pressed',x===b));buildPads();};
// T1: bodies, padding, real size
document.querySelectorAll('[data-shape]').forEach(b=>b.onclick=()=>setShape(b.dataset.shape));
const padRow=document.getElementById('padrow');
PADS.forEach((nm,i)=>{const b=document.createElement('button');b.className='chip';b.textContent=nm;b.dataset.pad=String(i+1);b.setAttribute('aria-pressed',String(i+1===state.pad));
 b.onclick=()=>{state.pad=i+1;syncBody();sendPad();say(['Thick leather over a hard core: a short, hard contact — a clang on top of the boom.','Thick wool: soft and dark; swing harder and it gets brighter.','Tightly compressed Styrofoam: a dull, dead thud — it crushes instead of bouncing.','Rubber: bouncy and round.'][i]);};padRow.appendChild(b);});
const setRoot=r=>{state.root=r;buildPads();sizeNote();drawInfo();};
document.getElementById('realsize').onclick=()=>{setRoot(48);say('Real size: the lowest key is C3, the breathing mode of the 35 m tower; its boom lies an octave below. Headphones or a speaker — a phone speaker plays little of it.');};
document.getElementById('phonesize').onclick=()=>{setRoot(64);say('Phone size: the lowest key is E4, a tower about 14 m tall, so a phone speaker can carry the boom.');};""")
rep("""      <p id="bodytext"></p>""", """      <p id="bodytext"></p>""")
rep("""      <div class="secttl">Mallet</div>
      <div class="knob" data-k="drive"></div>
      <div class="knob" data-k="hard"></div>""", """      <div class="secttl">Mallet</div>
      <div id="towerbits" hidden>
        <div class="secttl">Padding</div>
        <div class="row" id="padrow"></div>
        <div class="secttl">Size</div>
        <div class="row"><button class="chip" id="realsize">Real size</button><button class="chip" id="phonesize">Phone size</button></div>
        <p id="sizenote" class="note"></p>
      </div>
      <div class="knob" data-k="drive"></div>
      <div class="knob" data-k="hard"></div>""")
rep("""#bodytext{""", """.note{color:var(--dim);font-size:11.5px;margin:0 0 12px}
#bodytext{""")
rep("""    <section class="page on" id="page-body">
""", """    <section class="page on" id="page-body">
      <div class="secttl">Body</div>
      <div class="row"><button class="chip" data-shape="Tank" aria-pressed="true">Tank</button><button class="chip" data-shape="Tower" aria-pressed="false">Water tower</button></div>
""")
open(P, 'w', encoding='utf-8').write(s)
print('patch_t1: ok')
