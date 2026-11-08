const N=require('/home/claude/se/dsp.js'),O=require(process.argv[2]);const R=48000;
function mk(B,o){const D=B.makeDSP(R);D.V.forEach((v,i)=>v.on=i<2);Object.assign(D,{swarm:true,gentle:true,nP:4,recv:true,holo:true,move:.35,hallRT:1.8,hallSize:.7},o);return D;}
// 1. additive: hm=0 is bit-identical to the previous engine
for(const tone of[{},{gentle:false},{gentle:false,strange:true}]){const a=mk(N,{hm:0,...tone}),b=mk(O,tone);let diff=0,tot=0;for(let r=0;r<10;r++){const x=a.process(48000),y=b.process(48000);for(const k of['L','R'])for(let i=0;i<x[k].length;i++){tot++;if(x[k][i]!==y[k][i])diff++;}}console.log('off vs old',JSON.stringify(tone),diff+'/'+tot);}
// 2. math, derived a second way: pair -> 2ab/(a+b); swarm -> 1/mean(1/f). Recompute from voices just before each companion.
for(const hm of[1,2]){const D=mk(N,{hm});const S=D;let worst=0,wpan=0,n=0,ratios=[];const P=D.PL;const ping0=D.ping;
 // wrap: snapshot ringing voices before every new note
 let snap=null;D.process(4800);
 for(let r=0;r<200;r++){const before=P.map(z=>({on:z.on,hm:z.hm,t:z.t,dur:z.dur,f0:z.f0,gt:z.gt?[...z.gt]:null,ref:z}));const h0=D.hmN;D.process(480);
  if(D.hmN===h0+1){const c=P.find(z=>z.hm&&z.t<480/R+1e-9&&z.on);if(!c)continue;}}
 console.log('hm',hm,'companions',D.hmN,'notes',D.pings);}
