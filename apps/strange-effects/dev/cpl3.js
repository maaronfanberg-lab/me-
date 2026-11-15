const N=require('/home/claude/se/dsp.js');const R=48000;
function run(a,b,cpl,sec){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=i===a||i===b);Object.assign(D,{swarm:true,gentle:true,nP:4,recv:true,holo:true,cine:false,alive:false,move:.35,hallRT:1.8,hallSize:.7,cpl});
 const A=D.V[a],B=D.V[b];let nA=0,nB=0,nan=0;D.process(R);
 for(let r=0;r<sec*R/480;r++){const sa=[...A.Ps],sb=[...B.Ps],o=D.process(480);for(let i=0;i<o.L.length;i+=11)if(!isFinite(o.L[i]))nan++;for(let q=0;q<4;q++){if(A.Ps[q]!==sa[q]&&A.Ps[q]!==0)nA++;if(B.Ps[q]!==sb[q]&&B.Ps[q]!==0)nB++;}}return{nA,nB,nan};}
const nm=i=>N.ATTR[i].name.slice(0,12);const [lo,hi]=process.argv.slice(2).map(Number);
for(let a=lo;a<hi;a++)for(let b=a+1;b<10;b++)for(const c of[.3,.65,1]){const r0=run(a,b,0,10),r=run(a,b,c,10);console.log(JSON.stringify({a:nm(a),b:nm(b),c,A0:r0.nA,B0:r0.nB,A:r.nA,B:r.nB,nan:r.nan}));}
