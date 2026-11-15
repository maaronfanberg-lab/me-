/* ---------------------------------------------------------------------
   CANVAS — the string is drawn as the actual mode sum, same numbers the
   audio engine is running. y(x,t) = Σ aₙ·e^(−t/τₙ)·sin(nπx/L')·sin(2πfₙt)
   --------------------------------------------------------------------- */
const cv=document.getElementById('cv'), g2=cv.getContext('2d');
let W=0,H=0,DPR=1, SPLIT=0;
function sizeCanvas(){
  DPR = Math.min(window.devicePixelRatio||1, 2);
  W = cv.clientWidth; H = Math.round(Math.min(Math.max(W*0.52,180),260));
  cv.style.height = H+'px';
  cv.width=W*DPR; cv.height=H*DPR;
  g2.setTransform(DPR,0,0,DPR,0,0);
  SPLIT = Math.round(H*0.60);
}
window.addEventListener('resize', ()=>{sizeCanvas();});

function draw(){
  requestAnimationFrame(draw);
  if(!W) return;
  g2.clearRect(0,0,W,H);
  const pad=14, span=W-pad*2;
  const P = physics(fOpen());
  const yMid = SPLIT*0.52;
  g2.strokeStyle='#1A2337'; g2.lineWidth=1;
  g2.beginPath(); g2.moveTo(pad,yMid); g2.lineTo(W-pad,yMid); g2.stroke();
  for(let i=0;i<7;i++){
    const p=S.pickups[i], px = pad + span*(p.x/S.L), h = 6 + (p.lv/8)*26;
    g2.strokeStyle = p.lv>0 ? 'rgba(55,194,180,.55)' : '#1E2739';
    g2.lineWidth = p.lv>0 ? 2 : 1;
    g2.beginPath(); g2.moveTo(px, yMid-h); g2.lineTo(px, yMid+h); g2.stroke();
    g2.fillStyle = p.lv>0 ? '#37C2B4' : '#2A3550';
    g2.font='9px "IBM Plex Mono",monospace'; g2.textAlign='center';
    g2.fillText(String(i+1), px, yMid+h+11);
  }
  const ppx = pad+span*(S.pluckX/S.L);
  g2.fillStyle='#8C6BF0'; g2.beginPath(); g2.arc(ppx,yMid-40,3,0,7); g2.fill();
  const now = ctx? ctx.currentTime : 0;
  for(let vi=drawing.length-1; vi>=0; vi--){
    const rec = drawing[vi], t = now-rec.t0;
    const relT = rec.releasing ? (now-rec.releasing) : 0;
    const relG = rec.releasing ? Math.exp(-relT/((S.exc==='sustain')?0.8:(S.relDamp?0.14:6.0))) : 1;
    if(relG<0.003 && rec.releasing){ drawing.splice(vi,1); continue; }
    let alive=false;
    for(const m of rec.live){ if(Math.exp(-t/m.tau)*Math.abs(m.a) > 1e-4) {alive=true;break;} }
    if(!alive && !held.has(rec.semi)){ drawing.splice(vi,1); continue; }
    const clampX = pad+span*(rec.Lp/S.L);
    g2.strokeStyle='rgba(140,107,240,.85)'; g2.lineWidth=2;
    g2.beginPath(); g2.moveTo(clampX,yMid-34); g2.lineTo(clampX,yMid+34); g2.stroke();
    g2.beginPath();
    const NPTS = ENG.mode==='worklet' ? 160 : 96;
    for(let i=0;i<=NPTS;i++){
      const xf=i/NPTS, px=pad + span*(rec.Lp/S.L)*xf; let y=0;
      for(let mi=0; mi<Math.min(rec.live.length,28); mi++){
        const m=rec.live[mi], env=Math.exp(-t/m.tau)*relG;
        if(env<2e-4) continue;
        y += m.a*env*Math.sin(m.n*Math.PI*xf)*Math.sin(2*Math.PI*m.fn*t);
      }
      const py = yMid - y*SPLIT*0.62;
      i?g2.lineTo(px,py):g2.moveTo(px,py);
    }
    g2.strokeStyle='#B9A4FF'; g2.lineWidth=1.6; g2.stroke();
  }
  const ref = drawing.length ? drawing[drawing.length-1] : null;
  const base = SPLIT + (H-SPLIT)*0.5;
  g2.strokeStyle='#182135'; g2.lineWidth=1;
  g2.beginPath(); g2.moveTo(pad,base); g2.lineTo(W-pad,base); g2.stroke();
  if(ref){
    let mx=1e-9; for(const m of ref.modes) mx=Math.max(mx,Math.abs(m.amp));
    const bw = span/ref.modes.length;
    for(let i=0;i<ref.modes.length;i++){
      const m=ref.modes[i], h=(Math.abs(m.amp)/mx)*(H-SPLIT)*0.42, x=pad+i*bw;
      g2.fillStyle = m.amp>=0 ? 'rgba(140,107,240,.9)' : 'rgba(55,194,180,.9)';
      g2.fillRect(x, m.amp>=0?base-h:base, Math.max(bw-1.5,1), h);
    }
    g2.fillStyle='#4A5876'; g2.font='9px "IBM Plex Mono",monospace'; g2.textAlign='left';
    g2.fillText('harmonics 1…'+ref.modes.length+'   violet + / teal −', pad, H-4);
  } else {
    g2.fillStyle='#3B4761'; g2.font='9px "IBM Plex Mono",monospace'; g2.textAlign='left';
    g2.fillText('play a key — harmonic response appears here', pad, base+14);
  }
}
requestAnimationFrame(draw);

function setNoteName(f){
  const semi=Math.round(12*Math.log2(f/16.3516));
  const nm=NOTE_NAMES[((semi%12)+12)%12]+Math.floor(semi/12);
  document.getElementById('noteName').textContent=nm+'  '+f.toFixed(2)+'Hz';
}
function flashSilent(){
  const el=document.getElementById('noteName');el.textContent='ALL PICKUPS DOWN';el.style.color='var(--crimson)';
  setTimeout(()=>{el.style.color='var(--violet)';},900);
}

const NAT=[0,2,4,5,7,9,11,12,14,16,17,19,21,23,24];
const ACC_SLOT=[1,3,null,6,8,10,null,13,15,null,18,20,22,null,null];
const kbNat=document.getElementById('kbNat'),kbAcc=document.getElementById('kbAcc');
function buildKeys(){
  kbNat.innerHTML='';kbAcc.innerHTML='';
  NAT.forEach((s,i)=>{
    const b=document.createElement('button');b.className='key';b.dataset.s=s;b.textContent=NOTE_NAMES[s%12];kbNat.appendChild(b);
    const a=document.createElement('button'),as=ACC_SLOT[i];
    if(as===null||as===undefined)a.className='key blank';else{a.className='key acc';a.dataset.s=as;a.textContent=NOTE_NAMES[as%12];}
    kbAcc.appendChild(a);
  });paintKeys();
}
function paintKeys(){document.querySelectorAll('.key[data-s]').forEach(b=>b.classList.toggle('lit',held.has(+b.dataset.s)));}
function keyFromEvent(e){
  const pt=e.touches&&e.touches.length?e.touches[0]:e.changedTouches&&e.changedTouches.length?e.changedTouches[0]:e;
  const t=document.elementFromPoint(pt.clientX,pt.clientY);
  return t&&t.dataset&&t.dataset.s!==undefined?+t.dataset.s:null;
}
let downKey=null;
function bindKeys(){
  const wrap=document.getElementById('kbwrap');
  const start=e=>{const s=keyFromEvent(e);if(s===null)return;e.preventDefault();downKey=s;noteOn(s);};
  const end=e=>{if(downKey===null)return;e.preventDefault();noteOff(downKey);downKey=null;};
  wrap.addEventListener('touchstart',start,{passive:false});wrap.addEventListener('touchend',end,{passive:false});wrap.addEventListener('touchcancel',end,{passive:false});
  wrap.addEventListener('mousedown',start);window.addEventListener('mouseup',end);
}
const CMAP={z:0,s:1,x:2,d:3,c:4,v:5,g:6,b:7,h:8,n:9,j:10,m:11,k:12,',':13,l:14,'.':15,';':16,'/':17};
window.addEventListener('keydown',e=>{if(e.repeat)return;const s=CMAP[e.key];if(s!==undefined){e.preventDefault();noteOn(s);}});
window.addEventListener('keyup',e=>{const s=CMAP[e.key];if(s!==undefined)noteOff(s);});

function el(h){const d=document.createElement('div');d.innerHTML=h.trim();return d.firstChild;}
function stepper(label,get,set,fmt,step,min,max){
  const r=el(`<div class="row"><span class="lbl">${label}</span><button class="btn sm" data-a="-">−</button><span class="val"></span><button class="btn sm" data-a="+">+</button></div>`),v=r.querySelector('.val');
  const up=()=>{v.textContent=fmt(get());};
  r.querySelectorAll('button').forEach(b=>b.onclick=()=>{const d=b.dataset.a==='+'?step:-step;set(Math.min(max,Math.max(min,+(get()+d).toFixed(6))));up();refreshAll();});
  up();r._up=up;return r;
}
function segrow(label,opts,get,set){
  const r=el(`<div class="row" style="flex-wrap:wrap"><span class="lbl" style="flex:1 0 100%;margin-bottom:6px">${label}</span><span class="seg" style="flex:1"></span></div>`),seg=r.querySelector('.seg');
  const btns=opts.map(o=>{const b=el(`<button class="btn sm">${o.l}</button>`);b.onclick=()=>{set(o.v);up();refreshAll();};seg.appendChild(b);return{b,o};});
  function up(){btns.forEach(({b,o})=>b.classList.toggle('on',get()===o.v));}up();r._up=up;return r;
}
function tapfader(label,get,set,teal){
  const r=el(`<div class="row"><span class="lbl" style="flex:0 0 70px">${label}</span><span class="fader"></span></div>`),f=r.querySelector('.fader');
  for(let i=0;i<=8;i++){const s=document.createElement('span');s.onclick=()=>{set(i);up();refreshAll();};f.appendChild(s);}
  function up(){[...f.children].forEach((s,i)=>{s.className=i<=get()&&get()>0?(teal?'f t':'f'):'';});}up();r._up=up;return r;
}
const ups=[];
function mount(panel,node){document.getElementById(panel).appendChild(node);if(node._up)ups.push(node._up);}

function buildPickups(){
  const p=document.getElementById('p-pu');p.innerHTML='';p.appendChild(el(`<h2 class="sec">Pickup array</h2>`));
  S.pickups.forEach((pu,i)=>{
    const row=el(`<div class="pu"><div class="pu-top"><span class="pu-id">${i+1}</span><button class="btn sm" data-a="-">◀</button><span class="pu-x"></span><button class="btn sm" data-a="+">▶</button><span class="pu-h"></span></div></div>`);
    const xv=row.querySelector('.pu-x'),hv=row.querySelector('.pu-h'),fader=tapfader('LEVEL',()=>pu.lv,v=>{pu.lv=v;},true);fader.querySelector('.lbl').style.flex='0 0 44px';row.appendChild(fader);
    function up(){xv.textContent=(pu.x*100).toFixed(1)+' cm';const frac=pu.x/S.L,nulls=[];for(let n=2;n<=12;n++)if(Math.abs(Math.sin(n*Math.PI*frac))<.06)nulls.push(n);hv.textContent=pu.lv===0?'muted':(nulls.length?'nulls h'+nulls.slice(0,3).join(','):'open response');}
    row.querySelectorAll('[data-a]').forEach(b=>b.onclick=()=>{const d=b.dataset.a==='+'?.01:-.01;pu.x=Math.min(S.L*.95,Math.max(.01,+(pu.x+d).toFixed(3)));up();refreshAll();});
    up();ups.push(up);p.appendChild(row);
  });
  p.appendChild(el(`<h2 class="sec">Array layouts</h2>`));
  const seg=el(`<div class="seg"></div>`),layouts={
    'Log':L=>[.02,.045,.09,.17,.31,.55,.95].map(k=>k*L/2.5*2.5*.4+.02),
    'Even':L=>[1,2,3,4,5,6,7].map(k=>k*L/9),
    'Bridge':L=>[.02,.04,.065,.095,.13,.175,.23].map(k=>k*L/2.5),
    'Harmonic':L=>[1/2,1/3,1/4,1/5,1/6,1/7,1/8].map(k=>k*L),
    'Golden':L=>[1,2,3,4,5,6,7].map(k=>L*Math.pow(.618,k))};
  Object.entries(layouts).forEach(([n,fn])=>{const b=el(`<button class="btn sm">${n}</button>`);b.onclick=()=>{const xs=fn(S.L);S.pickups.forEach((pu,i)=>pu.x=Math.min(S.L*.95,Math.max(.01,+xs[i].toFixed(3))));buildPickups();refreshAll();};seg.appendChild(b);});p.appendChild(seg);
  const seg2=el(`<div class="seg" style="margin-top:8px"></div>`);[['All up',8],['Half',4],['All down',0]].forEach(([n,v])=>{const b=el(`<button class="btn sm">${n}</button>`);b.onclick=()=>{S.pickups.forEach(pu=>pu.lv=v);buildPickups();refreshAll();};seg2.appendChild(b);});p.appendChild(seg2);
  p.appendChild(el(`<p class="note">A pickup at distance x from the bridge senses harmonic n with weight sin(nπx/L′), so its comb changes with every note and pickups past the clamp go silent.</p>`));
}

function buildString(){
  const p=document.getElementById('p-st');p.innerHTML='';p.appendChild(el(`<h2 class="sec">Cable & scale</h2>`));
  mount('p-st',stepper('Scale length',()=>S.L,v=>S.L=v,v=>v.toFixed(2)+' m',.05,.6,12));
  mount('p-st',segrow('Open string pitch',OPEN_OPTS.map((o,i)=>({l:o.n,v:i})),()=>S.openIdx,v=>S.openIdx=v));
  mount('p-st',stepper('String diameter',()=>S.dmm,v=>S.dmm=v,v=>v.toFixed(1)+' mm',.5,1,24));
  mount('p-st',segrow('Construction',[{l:'7×19 cable',v:'cable'},{l:'Solid rod',v:'rod'}],()=>S.form,v=>S.form=v));
  mount('p-st',segrow('Metal',Object.entries(MAT).map(([v,m])=>({l:m.label,v})),()=>S.mat,v=>S.mat=v));
  const mi=el(`<div></div>`);
  function upMaterial(){const M=MAT[S.mat],F=FORM[S.form],cls=M.status==='PHYSICAL'?'ok':M.status==='FANTASY'?'':'hot';mi.innerHTML=`<div class="readout"><span class="k">Reality</span><span class="v ${cls}">${M.status}</span></div><div class="readout"><span class="k">Density</span><span class="v">${M.rho.toLocaleString()} kg/m³</span></div><div class="readout"><span class="k">Young's modulus</span><span class="v">${(M.E/1e9).toFixed(0)} GPa</span></div><div class="readout"><span class="k">Character</span><span class="v">${M.character}</span></div><p class="note">${F.label} changes effective bending stiffness and damping; ${M.label} changes mass, tension, stress, stiffness and material loss.</p>`;}
  upMaterial();ups.push(upMaterial);p.appendChild(mi);
  p.appendChild(el(`<h2 class="sec">Excitation</h2>`));
  mount('p-st',segrow('Actuator',[{l:'Pluck',v:'pluck'},{l:'Hammer',v:'strike'},{l:'Sustainer',v:'sustain'}],()=>S.exc,v=>S.exc=v));
  mount('p-st',stepper('Contact point',()=>S.pluckX,v=>S.pluckX=v,v=>(v*100).toFixed(1)+' cm',.01,.01,2));
  mount('p-st',stepper('Fundamental T60',()=>S.sustainT60,v=>S.sustainT60=v,v=>v.toFixed(1)+' s',.5,.5,30));
  mount('p-st',stepper('Overtone damping',()=>S.damp,v=>S.damp=v,v=>v.toFixed(2)+'×',.1,0,4));
  mount('p-st',segrow('Key release',[{l:'Damps string',v:true},{l:'Rings on',v:false}],()=>S.relDamp,v=>S.relDamp=v));
  p.appendChild(el(`<h2 class="sec">Engine & output</h2>`));
  mount('p-st',segrow('Modes per voice',[16,24,32,48,64].map(v=>({l:String(v),v})),()=>S.nModes,v=>S.nModes=v));
  mount('p-st',tapfader('VOLUME',()=>S.vol,v=>{S.vol=v;applyVol();}));
  p.appendChild(el(`<p class="note">Construction and metal act independently. Copper, titanium, lead, tungsten, uranium and the rest alter the actual modal model, not just EQ.</p>`));
}

function buildRig(){
  const p=document.getElementById('p-rig');p.innerHTML='';const box=el('<div></div>');p.appendChild(box);
  function up(){
    const P=physics(fOpen()),M=P.M,lbf=n=>n*.2248089,pctBreak=P.util*100,cls=pctBreak<20?'ok':pctBreak<33?'hot':'bad';
    const vSafe=Math.sqrt(.20*M.breakPa/P.rho),Lsafe=vSafe/(2*fOpen()),Bnow=physics(fOpen()).B;
    box.innerHTML=`<h2 class="sec">Per cable</h2>
      <div class="readout"><span class="k">Wave speed 2Lf</span><span class="v">${P.v.toFixed(1)} m/s</span></div>
      <div class="readout"><span class="k">Tension</span><span class="v">${(P.T/1000).toFixed(2)} kN · ${Math.round(lbf(P.T))} lbf</span></div>
      <div class="readout"><span class="k">Stress</span><span class="v">${(P.sigma/1e6).toFixed(0)} MPa</span></div>
      <div class="readout"><span class="k">Of breaking (${M.label})</span><span class="v ${cls}">${pctBreak.toFixed(1)} %</span></div>
      <div class="readout"><span class="k">Construction</span><span class="v">${P.F.label}</span></div>
      <div class="readout"><span class="k">Material status</span><span class="v ${M.status==='PHYSICAL'?'ok':M.status==='FANTASY'?'':'hot'}">${M.status}</span></div>
      <div class="readout"><span class="k">Linear density</span><span class="v">${P.mu.toFixed(3)} kg/m</span></div>
      <h2 class="sec">Whole instrument</h2>
      <div class="readout"><span class="k">Frame load (×7)</span><span class="v ${cls}">${(P.frameN/1000).toFixed(1)} kN · ${Math.round(lbf(P.frameN)).toLocaleString()} lbf</span></div>
      <div class="readout"><span class="k">Cable mass (7 × L)</span><span class="v">${(P.mu*S.L*7).toFixed(1)} kg</span></div>
      <div class="readout"><span class="k">Inharmonicity B (open)</span><span class="v">${Bnow.toExponential(2)}</span></div>
      <div class="readout"><span class="k">Partial 10 sharp by</span><span class="v">${(1200*Math.log2(Math.sqrt(1+Bnow*100))).toFixed(0)} cents</span></div>
      <h2 class="sec">Design headroom</h2>
      <div class="readout"><span class="k">Max scale at 5:1 factor</span><span class="v">${Lsafe.toFixed(2)} m</span></div>
      <div class="readout"><span class="k">Wave-speed ceiling</span><span class="v">${vSafe.toFixed(0)} m/s</span></div>
      ${pctBreak>=20?`<div class="warn"><b>Over the 5:1 working limit.</b> Going thicker will not help. LEVIATHAN will still let you play it.</div>`:''}
      <div class="warn"><b>Simulation warning.</b> Some choices are impractical, hazardous, radioactive or fictional. Do not use this screen as engineering approval for a real tensioned structure.</div>`;
  }
  up();ups.push(up);
}
