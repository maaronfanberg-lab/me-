// Pure, deterministic selection of contrasting sections from one REAL measured seismogram.
// It never synthesizes or changes a wave sample. No randomness, no padding with generated sound.
function WAVE_WINDOWS(){
 function analyze(x,rate,start=0,opts={}){
  if(!x||x.length<2||!(rate>0))return[];
  const duration=x.length/rate;
  const seconds=Math.min(480,Math.max(24,duration/8));
  const size=Math.min(x.length,Math.max(2,Math.round(seconds*rate)));
  const hop=Math.max(1,Math.round(size*.5)),candidates=[],seen=new Set();
  const limit=Math.max(1,Math.min(10,opts.limit||7));
  function measure(from){
   if(seen.has(from))return;seen.add(from);
   const end=Math.min(x.length,from+size),n=end-from;
   let sum=0,change=0,peak=0,cross=0,last=x[from],lastSign=0;
   const block=Math.max(1,Math.floor(n/8)),parts=new Float64Array(8);
   for(let i=from;i<end;i++){
    const v=x[i],sg=v>=0?1:-1;sum+=v*v;peak=Math.max(peak,Math.abs(v));
    if(i>from){const d=v-last;change+=d*d;if(lastSign&&sg!==lastSign)cross++;}
    lastSign=sg;last=v;
    parts[Math.min(7,Math.floor((i-from)/block))]+=v*v;
   }
   const rms=Math.sqrt(sum/n),diff=Math.sqrt(change/Math.max(1,n-1));
   const blockRms=parts.map((a,i)=>Math.sqrt(a/(i===7?Math.max(1,n-7*block):block)));
   const burst=Math.max(...blockRms)/(rms+1e-12),rough=diff/(rms+1e-12),crest=peak/(rms+1e-12);
   candidates.push({from,end,rms,peak,rough,burst,crest,cross,at:start+from/rate*1000});
  }
  for(let i=0;i+size<=x.length;i+=hop)measure(i);
  if(x.length>size)measure(x.length-size);
  if(!candidates.length)measure(0);
  const maxRms=Math.max(...candidates.map(c=>c.rms));
  if(!(maxRms>1e-12))return[];
  const eligible=candidates.filter(c=>c.rms>=maxRms*.045);
  const feat=c=>[Math.log10(c.rms+1e-12),Math.log10(c.rough+1e-8),Math.log10(c.crest+1e-8),Math.log10(c.burst+1e-8)];
  const f=eligible.map(feat),mins=[0,1,2,3].map(k=>Math.min(...f.map(a=>a[k]))),maxs=[0,1,2,3].map(k=>Math.max(...f.map(a=>a[k])));
  const vector=(c)=>feat(c).map((v,k)=>(v-mins[k])/Math.max(.08,maxs[k]-mins[k]));
  eligible.forEach(c=>{c.vector=vector(c)});
  const picked=[];const best=[...eligible].sort((a,b)=>b.rms-a.rms||a.from-b.from)[0];picked.push(best);
  function distance(a,b){
   const z=a.vector.map((v,k)=>Math.pow((v-b.vector[k])*([.55,1.15,.75,.9][k]),2));
   return Math.sqrt(z.reduce((p,q)=>p+q,0));
  }
  while(picked.length<limit){
   const pool=eligible.filter(c=>!picked.some(p=>Math.abs(c.from-p.from)<size*.8));
   if(!pool.length)break;
   let winner=null,top=-Infinity;
   for(const c of pool){
    const d=Math.min(...picked.map(p=>distance(c,p)));
    const energy=Math.sqrt(c.rms/maxRms);
    const score=d+.18*energy;
    if(score>top){top=score;winner=c;}
   }
   if(!winner)break;picked.push(winner);
  }
  return picked.map((c,i)=>({
   id:i+1,from:c.from,end:c.end,at:c.at,
   duration:(c.end-c.from)/rate,energy:c.rms/maxRms,
   rough:c.rough,burst:c.burst,crest:c.crest,
   // For display only: these numbers are measured properties, NOT sound controls.
   label:'Section '+(i+1)
  }));
 }
 return {analyze};
}
if(typeof module!=='undefined')module.exports=WAVE_WINDOWS;
