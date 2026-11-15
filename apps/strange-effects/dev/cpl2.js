const N=require('/home/claude/se/dsp.js');const R=48000;
function run(a,b,cpl,sec,bShift){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=i===a||i===b);Object.assign(D,{swarm:true,gentle:true,nP:4,recv:true,holo:true,cine:false,alive:false,move:.35,hallRT:1.8,hallSize:.7,cpl});
 const A=D.V[a],B=D.V[b];if(bShift){const dB=B.def;for(let p=0;p<dB.p.length;p++)if(!(dB.fix&&dB.fix.includes(p)))D.setParam(b,p,dB.lo[p]+.85*(dB.hi[p]-dB.lo[p]));}
 let nA=0,nB=0,nan=0,fm=[];D.process(R);
 for(let r=0;r<sec*R/480;r++){const sa=[...A.Ps],sb=[...B.Ps],o=D.process(480);for(let i=0;i<o.L.length;i+=11)if(!isFinite(o.L[i]))nan++;
  for(let q=0;q<4;q++){if(A.Ps[q]!==sa[q]&&A.Ps[q]!==0)nA++;if(B.Ps[q]!==sb[q]&&B.Ps[q]!==0)nB++;}fm.push(A.fmul);}
 const mf=fm.reduce((x,y)=>x+Math.log2(y),0)/fm.length;return{nA,nB,nan,mf};}
const nm=i=>N.ATTR[i].name.slice(0,11);
// causal test: change only B's parameters. Apart: A must not change at all. Tangle: A should change.
for(const[a,b]of[[0,1],[2,7],[4,9],[3,6]])for(const c of[0,1]){const x=run(a,b,c,15,false),y=run(a,b,c,15,true);
 console.log(`${nm(a)} heard while ${nm(b)} is retuned · pull ${c}: A crossings ${x.nA}→${y.nA}, A pitch level ${(1200*(y.mf-x.mf)).toFixed(0)}¢ shift`);}
let bad=0,lo=[];for(let a=0;a<10;a++)for(let b=a+1;b<10;b++){const r0=run(a,b,0,10),r=run(a,b,1,10);const ok=!r.nan&&r.nA+r.nB>=.5*(r0.nA+r0.nB);if(!ok){bad++;lo.push(`${nm(a)}+${nm(b)} ${r0.nA+r0.nB}→${r.nA+r.nB}${r.nan?' NaN':''}`);}}
console.log('pairs at Tangle that lose over half their notes or break:',bad,'of 45');lo.forEach(x=>console.log('  ',x));
