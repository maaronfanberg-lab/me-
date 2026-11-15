function runChecks(){
  const R=[];
  const rel=(a,b)=>Math.abs(a-b)/Math.max(Math.abs(a),1e-30);
  {
    const P=physics(fOpen()*1.5);
    R.push([rel(P.Braw,P.B2)<1e-9,'Inharmonicity derived twice',`B1 ${P.Braw.toExponential(4)} · B2 ${P.B2.toExponential(4)}`]);
  }
  {
    const P=physics(fOpen());
    R.push([rel(P.T/P.A,P.sigma)<1e-12,'Stress identity',`T/A ${(P.T/P.A/1e6).toFixed(3)} MPa · ρv² ${(P.sigma/1e6).toFixed(3)} MPa`]);
  }
  {
    let ok=true;
    for(const mat of Object.keys(MAT)){
      const old=S.mat; S.mat=mat;
      const x=buildModes(fOpen()*1.25,{nModes:12}).modes;
      if(!x.length||!x.every(m=>Number.isFinite(m.fn)&&Number.isFinite(m.amp)&&m.fn>0)) ok=false;
      S.mat=old;
    }
    R.push([ok,'All materials generate finite modes',Object.keys(MAT).join(' · ')]);
  }
  {
    const old=S.form; const a=buildModes(fOpen()*1.3,{nModes:12}).modes.map(m=>m.fn);
    S.form=old==='cable'?'rod':'cable'; const b=buildModes(fOpen()*1.3,{nModes:12}).modes.map(m=>m.fn); S.form=old;
    R.push([a.some((v,i)=>b[i]&&Math.abs(v-b[i])>1e-7),'Cable and rod differ physically','construction changes inharmonicity']);
  }
  {
    const f=fOpen()*1.2, wide=S.pickups.map(p=>({x:p.x,lv:8})), half=S.pickups.map(p=>({x:p.x,lv:4}));
    const lw=voiceLevel(f,wide),lh=voiceLevel(f,half);
    R.push([rel(lw,REF_GAIN)<1e-9&&rel(lh,REF_GAIN/2)<1e-9,'Pickup level changes loudness',`full ${lw.toFixed(3)} · half ${lh.toFixed(3)}`]);
  }
  const p=document.getElementById('p-ck');p.innerHTML='';
  const n=R.filter(r=>r[0]).length;
  p.appendChild(el(`<h2 class="sec">Verification — ${n}/${R.length} passing</h2>`));
  R.forEach(([ok,title,detail])=>p.appendChild(el(`<div class="test"><span class="st ${ok?'pass':'fail'}">${ok?'PASS':'FAIL'}</span><span class="tx">${title}<em>${detail}</em></span></div>`)));
  const b=el(`<button class="btn wide" style="margin-top:12px;width:100%">RUN AGAIN</button>`);b.onclick=runChecks;p.appendChild(b);
}

function refreshHeader(){
  const P=physics(fOpen()),pct=P.util*100,f=document.getElementById('gfill');
  f.style.width=Math.min(100,pct)+'%';
  f.style.background=pct<20?'linear-gradient(90deg,#1F7970,#37C2B4)':pct<33?'linear-gradient(90deg,#37C2B4,#E8C24A)':'linear-gradient(90deg,#E8C24A,#E0455F)';
  const g=document.getElementById('gpct');g.textContent=pct.toFixed(1)+'%';g.className=pct<20?'ok':pct<33?'hot':'bad';
  document.getElementById('gframe').textContent=Math.round(P.frameN*.2248089).toLocaleString()+' lbf';
}
function refreshAll(){
  ups.forEach(u=>{try{u();}catch(e){console.warn(e);}});refreshHeader();
  document.querySelectorAll('.key[data-s]').forEach(b=>b.classList.toggle('over',physics(fOpen()).util>.20));
}

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
  t.classList.add('on');document.getElementById('p-'+t.dataset.p).classList.add('on');
  if(t.dataset.p==='ck')runChecks();
});
document.getElementById('octUp').onclick=()=>{S.octave=Math.min(2,S.octave+1);panic();};
document.getElementById('octDn').onclick=()=>{S.octave=Math.max(0,S.octave-1);panic();};
document.getElementById('panic').onclick=panic;

document.getElementById('power').onclick=async function(){
  if(this.dataset.busy==='1')return;
  this.dataset.busy='1';this.textContent='STARTING…';
  try{
    await boot();
    if(ctx.state==='suspended')await ctx.resume();
    document.getElementById('kbwrap').style.display='block';
    this.remove();sizeCanvas();
  }catch(err){
    console.error(err);this.dataset.busy='0';this.textContent='AUDIO BLOCKED — TAP AGAIN';
  }
};

try{
  buildKeys();bindKeys();buildPickups();buildString();buildRig();sizeCanvas();refreshAll();
}catch(err){
  console.error('LEVIATHAN startup failed',err);
  const p=document.getElementById('p-pu');
  if(p)p.innerHTML=`<div class="warn"><b>Startup error:</b> ${String(err&&err.message||err)}</div>`;
}
