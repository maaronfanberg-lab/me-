const N=require('/home/claude/se/dsp.js');const R=48000;const ix=n=>N.ATTR.findIndex(a=>a.name.startsWith(n));
function run(a,b,cpl,sec,seed){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=i===a||i===b);Object.assign(D,{swarm:true,gentle:true,nP:4,recv:true,holo:true,move:.35,cpl});
 const A=D.V[a],B=D.V[b];let nA=0,nB=0;D.process(R);for(let r=0;r<sec*100;r++){const sa=[...A.Ps],sb=[...B.Ps];D.process(480);for(let q=0;q<4;q++){if(A.Ps[q]!==sa[q]&&A.Ps[q]!==0)nA++;if(B.Ps[q]!==sb[q]&&B.Ps[q]!==0)nB++;}}return[nA,nB];}
for(const[a,b,c]of[['Hindmarsh','Tumor',.65],['Willam','Nosé',.65],['Hindmarsh','Willam',1]]){const x=run(ix(a),ix(b),0,30),y=run(ix(a),ix(b),c,30);console.log(a,'+',b,'pull',c,'| 30 s notes',x.join(','),'→',y.join(','),'| first kept',(100*y[0]/x[0]).toFixed(0)+'%');}
