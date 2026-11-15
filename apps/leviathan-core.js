
/* =====================================================================
   LEVIATHAN — a giant cable/rod bass + impossible-material laboratory
   Physics is modelled, not faked. Every number below is derived, and the
   CHECK tab re-derives the load-bearing ones a second, independent way.
   ===================================================================== */

const LN1000 = Math.log(1000);

// Construction and metal are separate on purpose.  Construction changes
// bending stiffness + loss; the selected metal supplies density, modulus,
// strength and its baseline internal damping character.
const FORM = {
  cable: { label:'7×19 cable', stiffScale:0.09, dampMul:5.714, dampPAdd:0.30 },
  rod:   { label:'solid rod',  stiffScale:1.00, dampMul:1.000, dampPAdd:0.00 }
};

// Engineering properties are representative values, not certification data.
// Strength varies enormously with alloy, temper, purity and fabrication.
// dampK/dampP are deliberately musical loss-model parameters rather than
// handbook material constants; they make each virtual string audibly distinct.
const MAT = {
  steel:      {label:'Steel',      rho:7850,  E:200e9, breakPa:980e6, dampK:0.0035, dampP:1.30, status:'PHYSICAL',     character:'familiar, hard, balanced'},
  aluminum:   {label:'Aluminum',   rho:2700,  E:69e9,  breakPa:310e6, dampK:0.0060, dampP:1.35, status:'PHYSICAL',     character:'light, bright, quick'},
  copper:     {label:'Copper',     rho:8960,  E:110e9, breakPa:220e6, dampK:0.0085, dampP:1.30, status:'IMPRACTICAL',  character:'heavy, warm, gong-like'},
  titanium:   {label:'Titanium',   rho:4500,  E:116e9, breakPa:900e6, dampK:0.0025, dampP:1.25, status:'PHYSICAL',     character:'strong, clear, long-lived'},
  lead:       {label:'Lead',       rho:11340, E:16e9,  breakPa:18e6,  dampK:0.0300, dampP:1.15, status:'IMPRACTICAL',  character:'massive, soft, rapidly dark'},
  uranium:    {label:'Uranium',    rho:19050, E:208e9, breakPa:390e6, dampK:0.0045, dampP:1.25, status:'VIRTUAL ONLY', character:'extremely dense, metallic'},
  tungsten:   {label:'Tungsten',   rho:19300, E:411e9, breakPa:550e6, dampK:0.0018, dampP:1.25, status:'IMPRACTICAL',  character:'colossal, stiff, glassy'},
  magnesium:  {label:'Magnesium',  rho:1740,  E:45e9,  breakPa:230e6, dampK:0.0100, dampP:1.35, status:'IMPRACTICAL',  character:'feather-light, fast, papery'},
  bronze:     {label:'Bronze',     rho:8800,  E:100e9, breakPa:350e6, dampK:0.0055, dampP:1.30, status:'PHYSICAL',     character:'bell-like, warm, complex'},
  silver:     {label:'Silver',     rho:10490, E:83e9,  breakPa:170e6, dampK:0.0070, dampP:1.25, status:'IMPRACTICAL',  character:'dense, smooth, chiming'},
  gold:       {label:'Gold',       rho:19300, E:79e9,  breakPa:120e6, dampK:0.0120, dampP:1.20, status:'IMPRACTICAL',  character:'very heavy, soft, dark'},
  unobtainium:{label:'Unobtainium',rho:12000, E:500e9, breakPa:5.0e9, dampK:0.0012, dampP:1.10, status:'FANTASY',      character:'impossibly strong, crystalline'}
};

const NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const OPEN_OPTS = [
  {n:'E0',  f:20.602}, {n:'G0', f:24.500}, {n:'B0', f:30.868},
  {n:'D1',  f:36.708}, {n:'E1', f:41.203}, {n:'A1', f:55.000}
];

const S = {
  L: 2.50, openIdx: 2, dmm: 6, mat: 'steel', form: 'cable', pluckX: 0.14,
  exc: 'pluck', sustainT60: 6.0, damp: 1.0, nModes: 48, relDamp: true,
  octave: 0, vol: 6,
  pickups: [
    {x:0.05, lv:7}, {x:0.11, lv:5}, {x:0.19, lv:4}, {x:0.31, lv:5},
    {x:0.50, lv:4}, {x:0.79, lv:3}, {x:1.24, lv:2}
  ]
};

const fOpen = () => OPEN_OPTS[S.openIdx].f;

function physics(f){
  const d=S.dmm/1000, A=Math.PI*d*d/4, M=MAT[S.mat], F=FORM[S.form];
  const rho=M.rho, E=M.E, mu=rho*A, v=2*S.L*fOpen(), T=mu*v*v;
  const sigma=rho*v*v, Lp=S.L*fOpen()/f;
  const B1=Math.pow(Math.PI,3)*E*Math.pow(d,4)/(64*T*Lp*Lp);
  const B2=Math.pow(Math.PI,2)*E*d*d/(64*rho*S.L*S.L*fOpen()*fOpen()*Lp*Lp);
  return {d,A,mu,v,T,sigma,Lp,M,F,rho,E,Braw:B1,B2,B:B1*F.stiffScale,
          util:sigma/M.breakPa,frameN:T*7};
}

function buildModes(f, over){
  const o=over||{}, P=physics(f);
  const excExp=(o.exc||S.exc)==='pluck'?2:(o.exc||S.exc)==='strike'?1:0.6;
  const pus=o.pickups||S.pickups;
  const pluckX=Math.min(o.pluckX!==undefined?o.pluckX:S.pluckX,P.Lp*0.999);
  const out=[], nMax=o.nModes||S.nModes;
  for(let n=1;n<=nMax;n++){
    const fn=n*f*Math.sqrt(1+P.B*n*n); if(fn>20000) break;
    const exc=Math.sin(n*Math.PI*pluckX/P.Lp)/Math.pow(n,excExp);
    let pk=0;
    for(const p of pus){
      if(p.lv<=0||p.x>=P.Lp) continue;
      pk+=(p.lv/8)*Math.sin(n*Math.PI*p.x/P.Lp);
    }
    const vel=fn/f;
    out.push({n,fn,amp:exc*pk*vel,disp:exc*pk});
  }
  return {P,modes:out};
}

const REF_GAIN=1.4;
function refSum(f){
  const wide=S.pickups.map(p=>({x:p.x,lv:8}));
  let s=0; for(const m of buildModes(f,{pickups:wide}).modes) s+=Math.abs(m.amp);
  return Math.max(s,1e-12);
}
function voiceLevel(f,pus){
  let s=0; for(const m of buildModes(f,{pickups:pus}).modes) s+=Math.abs(m.amp);
  return s*REF_GAIN/refSum(f);
}

const WORKLET_SRC=`
class ModalBank extends AudioWorkletProcessor{
  constructor(){
    super();this.v=new Map();
    this.port.onmessage=(e)=>{
      const m=e.data;
      if(m.t==='on'){
        this.v.set(m.id,{cr:m.cr,sr:m.sr,g:m.g,n:m.cr.length,
          x:new Float64Array(m.cr.length).fill(1),y:new Float64Array(m.cr.length),
          env:m.atk>0?0:1,rate:m.atk>0?1/(m.atk*sampleRate):0,rel:false,relC:0,quiet:0});
      }else if(m.t==='off'){
        const v=this.v.get(m.id);if(v){v.rel=true;v.relC=Math.exp(-1/(Math.max(0.005,m.rt)*sampleRate));}
      }else if(m.t==='panic'){this.v.clear();}
    };
  }
  process(_,outs){
    const out=outs[0][0];out.fill(0);const N=out.length;
    for(const [id,v] of this.v){
      const cr=v.cr,sr=v.sr,g=v.g,x=v.x,y=v.y,n=v.n;let env=v.env,peak=0;
      for(let i=0;i<N;i++){
        if(v.rel) env*=v.relC; else if(env<1){env+=v.rate;if(env>1)env=1;}
        let s=0;
        for(let k=0;k<n;k++){
          const xr=x[k],yr=y[k];x[k]=cr[k]*xr-sr[k]*yr;y[k]=sr[k]*xr+cr[k]*yr;s+=y[k]*g[k];
        }
        const o=s*env;out[i]+=o;const a=o<0?-o:o;if(a>peak)peak=a;
      }
      v.env=env;if(peak<2e-5){v.quiet++;if(v.quiet>24)this.v.delete(id);}else v.quiet=0;
    }
    return true;
  }
}
registerProcessor('modal-bank',ModalBank);`;

let ctx=null,node=null,master=null,comp=null,analyser=null,ready=false,voiceId=0;
const held=new Map(),drawing=[];
const ENG={mode:'none',v:new Map()};

function engHandle(m){
  if(m.t==='on'){
    ENG.v.set(m.id,{cr:m.cr,sr:m.sr,g:m.g,n:m.cr.length,
      x:new Float64Array(m.cr.length).fill(1),y:new Float64Array(m.cr.length),
      env:m.atk>0?0:1,rate:m.atk>0?1/(m.atk*ctx.sampleRate):0,rel:false,relC:0,quiet:0});
  }else if(m.t==='off'){
    const v=ENG.v.get(m.id);if(v){v.rel=true;v.relC=Math.exp(-1/(Math.max(0.005,m.rt)*ctx.sampleRate));}
  }else if(m.t==='panic') ENG.v.clear();
}

function engRender(out){
  out.fill(0);const N=out.length;
  for(const [id,v] of ENG.v){
    const cr=v.cr,sr=v.sr,g=v.g,x=v.x,y=v.y,n=v.n;let env=v.env,peak=0;
    for(let i=0;i<N;i++){
      if(v.rel)env*=v.relC;else if(env<1){env+=v.rate;if(env>1)env=1;}
      let s=0;
      for(let k=0;k<n;k++){
        const xr=x[k],yr=y[k];x[k]=cr[k]*xr-sr[k]*yr;y[k]=sr[k]*xr+cr[k]*yr;s+=y[k]*g[k];
      }
      const o=s*env;out[i]+=o;const a=o<0?-o:o;if(a>peak)peak=a;
    }
    v.env=env;if(peak<2e-5){v.quiet++;if(v.quiet>24)ENG.v.delete(id);}else v.quiet=0;
  }
}

function send(msg){if(ENG.mode==='worklet')node.port.postMessage(msg);else engHandle(msg);}

async function boot(){
  if(ready){if(ctx&&ctx.state==='suspended')await ctx.resume();return;}
  ctx=new(window.AudioContext||window.webkitAudioContext)({latencyHint:'interactive'});
  if(ctx.state==='suspended') await ctx.resume();
  if(ctx.audioWorklet){
    const attempts=[
      ['blob',()=>URL.createObjectURL(new Blob([WORKLET_SRC],{type:'application/javascript'}))],
      ['data',()=>'data:application/javascript;charset=utf-8,'+encodeURIComponent(WORKLET_SRC)]
    ];
    for(const [name,mk] of attempts){
      try{await ctx.audioWorklet.addModule(mk());node=new AudioWorkletNode(ctx,'modal-bank',{outputChannelCount:[1]});ENG.mode='worklet';ENG.via=name;break;}
      catch(err){console.warn('worklet via '+name+' blocked:',err.message||err);}
    }
  }
  if(ENG.mode!=='worklet'){
    node=ctx.createScriptProcessor(1024,1,1);
    node.onaudioprocess=e=>engRender(e.outputBuffer.getChannelData(0));
    ENG.mode='scriptprocessor';ENG.via='main thread';if(S.nModes>32)S.nModes=32;
  }
  comp=ctx.createDynamicsCompressor();comp.threshold.value=-14;comp.knee.value=8;comp.ratio.value=8;comp.attack.value=.004;comp.release.value=.18;
  master=ctx.createGain();analyser=ctx.createAnalyser();analyser.fftSize=2048;
  node.connect(comp);comp.connect(master);master.connect(analyser);master.connect(ctx.destination);
  applyVol();ready=true;
  const tag=document.getElementById('engTag');if(tag)tag.textContent=(ENG.mode==='worklet'?'worklet · '+ENG.via:'fallback · '+ENG.via)+' · '+ctx.sampleRate/1000+'k';
}
function applyVol(){if(master)master.gain.value=Math.pow(S.vol/8,1.7)*1.6;}

function noteOn(semi){
  if(!ready||held.has(semi))return;
  const f=fOpen()*Math.pow(2,(semi+S.octave*12)/12),built=buildModes(f),P=built.P,modes=built.modes;
  if(!modes.length)return;
  let sumAbs=0;for(const m of modes)sumAbs+=Math.abs(m.amp);if(sumAbs<1e-12){flashSilent();return;}
  const norm=REF_GAIN/refSum(f),sr=ctx.sampleRate,K=P.M.dampK*P.F.dampMul*S.damp,Pw=P.M.dampP+P.F.dampPAdd;
  const t60base=S.exc==='sustain'?45:S.sustainT60;
  const cr=new Float64Array(modes.length),si=new Float64Array(modes.length),g=new Float64Array(modes.length),live=[];
  for(let i=0;i<modes.length;i++){
    const m=modes[i],t60=t60base/(1+K*Math.pow(m.n,Pw)),tau=t60/6.907755,r=Math.exp(-1/(tau*sr)),w=2*Math.PI*m.fn/sr;
    cr[i]=r*Math.cos(w);si[i]=r*Math.sin(w);g[i]=m.amp*norm;live.push({fn:m.fn,a:m.amp*norm,tau,n:m.n});
  }
  const id=++voiceId;send({t:'on',id,cr,sr:si,g,atk:S.exc==='sustain'?.35:0});
  const rec={id,semi,live,t0:ctx.currentTime,Lp:P.Lp,f,modes};held.set(semi,rec);drawing.push(rec);
  if(S.exc==='strike')contactClick();paintKeys();setNoteName(f);
}
function noteOff(semi){
  const rec=held.get(semi);if(!rec)return;held.delete(semi);
  const rt=S.exc==='sustain'?.8:(S.relDamp?.14:6);send({t:'off',id:rec.id,rt});rec.releasing=ctx.currentTime;paintKeys();
}
function panic(){for(const k of [...held.keys()])noteOff(k);if(node)send({t:'panic'});drawing.length=0;held.clear();paintKeys();}
function contactClick(){
  const n=Math.floor(ctx.sampleRate*.014),b=ctx.createBuffer(1,n,ctx.sampleRate),d=b.getChannelData(0);
  for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,3);
  const s=ctx.createBufferSource();s.buffer=b;const bp=ctx.createBiquadFilter();bp.type='bandpass';bp.frequency.value=1400;bp.Q.value=.9;
  const gg=ctx.createGain();gg.gain.value=.09;s.connect(bp);bp.connect(gg);gg.connect(comp);s.start();
}
