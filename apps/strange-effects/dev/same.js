const A=require('/home/claude/se/dsp_old.js'),B=require('/home/claude/se/dsp.js');const R=48000;let bad=0,tot=0;
for(const cfg of[{swarm:true,gentle:true,nP:4,cpl:0},{swarm:false,cine:true,cpl:0},{swarm:true,allT:true,nP:8,cpl:0},{swarm:true,synT:true,nP:4,cpl:0}])
for(const on of[[0],[1,3],[2,4,6],[0,1,2,3,4,5,6,7,8,9]]){const o=[A,B].map(M=>{const D=M.makeDSP(R);D.V.forEach((v,i)=>v.on=on.includes(i));Object.assign(D,cfg);let h=0;for(let r=0;r<200;r++){const x=D.process(480);for(let i=0;i<x.L.length;i++)h=(h*31+Math.round(x.L[i]*1e9)+Math.round(x.R[i]*1e9))%2147483647;}return h;});tot++;if(o[0]!==o[1])bad++;}
console.log(`Apart bit-identical: ${tot-bad}/${tot}`);
