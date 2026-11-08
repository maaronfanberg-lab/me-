const N=require('/home/claude/se/dsp.js');const R=48000;
for(const hm of[1,2])for(const nP of[4,32]){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=i<2);Object.assign(D,{swarm:true,gentle:true,nP,recv:true,holo:true,hm});D.process(4800);D.spatialOff=true;const P=D.PL;
 let ef=0,ep=0,n=0,iv=[];D.process(4800);
 for(let r=0;r<12000;r++){const pre=P.map(z=>({on:z.on,hm:z.hm,t:z.t,dur:z.dur,f0:z.f0,gt:z.gt&&[...z.gt]}));const h0=D.hmN,p0=D.pings;D.process(32);
  if(D.hmN!==h0+1||D.pings!==p0+1)continue;
  const c=P.find(z=>z.on&&z.hm&&z.t<=32/R+1e-12),k=P.find(z=>z.on&&!z.hm&&z.t<=32/R+1e-12);if(!c||!k)continue;
  // ringing before this block, still ringing (not stolen by the new note or the companion)
  let src=pre.map((p,i)=>({...p,i})).filter(p=>p.on&&!p.hm&&p.t<p.dur&&P[p.i]!==k);
  if(hm===1){src=[src.reduce((a,b)=>b.t<a.t?b:a)];}
  const fs=[k.f0,...src.map(p=>p.f0)],gts=[k.gt,...src.map(p=>p.gt)];
  const H2=hm===1?2*fs[0]*fs[1]/(fs[0]+fs[1]):1/(fs.reduce((a,f)=>a+1/f,0)/fs.length);
  ef=Math.max(ef,Math.abs(c.f0/H2-1));
  for(let q=0;q<5;q++){let e=0;fs.forEach((f,j)=>e+=gts[j][q]*(H2/f)/fs.length);ep=Math.max(ep,Math.abs(e-c.gt[q]));}
  iv.push(1200*Math.log2(c.f0/Math.max(...fs)));n++;}
 iv.sort((a,b)=>a-b);console.log(`hm=${hm} nP=${nP}: ${n} companions checked · worst pitch error ${ef.toExponential(1)} · worst pan error ${ep.toExponential(1)} · below top note median ${iv[iv.length>>1]|0}¢ (range ${iv[0]|0}..${iv[iv.length-1]|0}¢)`);}
