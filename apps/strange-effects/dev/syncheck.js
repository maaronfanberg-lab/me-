const N=require('/home/claude/se/dsp.js');const R=48000;let bad=0;
for(const tone of[{synT:true,gentle:false},{allT:true,gentle:false}])for(const nP of[1,4,32])for(const [a,b] of[[0,1],[2,5],[7,9]]){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=i===a||i===b);Object.assign(D,{swarm:true,nP,recv:true,holo:true,cine:false,alive:false,move:.35,hallRT:1.8,hallSize:.7,...tone});
 let nan=0,pk=0,e=0,n=0;for(let r=0;r<20;r++){const o=D.process(R);for(let i=0;i<o.L.length;i++){const x=o.L[i],y=o.R[i];if(!isFinite(x)||!isFinite(y))nan++;else{pk=Math.max(pk,Math.abs(x),Math.abs(y));e+=x*x+y*y;n+=2;}}}
 const used=D.tech.map((c,i)=>c?i+':'+c:'').filter(Boolean).join(' ');const lv=10*Math.log10(e/n);if(nan||pk>4||lv<-45)bad++;
 console.log(Object.keys(tone)[0],'nP',nP,'sys',a,b,'| NaN',nan,'peak',pk.toFixed(2),'level',lv.toFixed(1),'dB | techniques',used);}
console.log('problems:',bad);
