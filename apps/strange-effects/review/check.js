// Strange Effects listening review. Runs the app's own engine (extracted by render/mkengine.py) and measures
// what a listener would notice. Usage: node check.js <shard> <shards>  -> JSON lines on stdout.
const N=require('../render/engine.js');const R=48000,W=960;
const TONES={Gentle:{gentle:true},Gilmour:{gentle:false},Strange:{gentle:false,strange:true},Everything:{gentle:false,allT:true},'Space synth':{gentle:false,synT:true}};
const BASE={swarm:true,nP:4,recv:true,holo:true,cine:false,alive:false,move:.35,hallRT:1.8,hallSize:.7,cpl:0};
const nm=i=>N.ATTR[i].name;const K=+(process.env.SE_SCALE||1); // SE_SCALE<1 only for quick smoke tests
function make(on,cfg){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=on.includes(i));Object.assign(D,BASE,cfg);return D;}
// listening run: 20 ms windows; silence = below -60 dBFS; notes = particle crossings; clipping = |sample| > .99
function listen(on,cfg,sec){const D=make(on,cfg);D.process(2*R);let run=0,longest=0,sil=0,n=0,mn=0,up=0,clip=0,tot=0,nan=0;const notes=on.map(()=>0);
 for(let r=0;r<sec*R/W;r++){const ps=on.map(i=>[...D.V[i].Ps]);const o=D.process(W);let e=0;
  for(let i=0;i<W;i++){const a=o.L[i],b=o.R[i];if(!(a===a&&b===b))nan++;e+=a*a+b*b;if(Math.abs(a)>.99||Math.abs(b)>.99)clip++;tot+=2;}
  on.forEach((v,j)=>{const P=D.V[v].Ps;for(let q=0;q<P.length&&q<ps[j].length;q++)if(P[q]!==ps[j][q]&&P[q]!==0)notes[j]++;});
  const db=10*Math.log10(e/(2*W)+1e-20);n++;mn=Math.min(mn,db);if(D.brGate&&D.brGate()>.5)up++;if(db<-60){sil++;run++;longest=Math.max(longest,run);}else run=0;}
 return{longestSilence:+(longest*W/R).toFixed(2),silentPct:+(100*sil/n).toFixed(1),quietestDb:+mn.toFixed(1),undertowPct:+(100*up/n).toFixed(1),clipPct:+(100*clip/tot).toFixed(3),nan:nan+(D.bad||0),notesPerSec:notes.map(x=>+(x/sec).toFixed(2))};}
const jobs=[];
for(const t in TONES){for(let a=0;a<N.ATTR.length;a++)jobs.push({kind:'listen',tone:t,on:[a],cpl:0});
 for(const c of[0,1])for(const p of[[3,1],[4,8],[2,4],[0,7]])jobs.push({kind:'listen',tone:t,on:p,cpl:c});jobs.push({kind:'listen',tone:t,on:N.ATTR.map((_,i)=>i),cpl:1});}
for(let a=0;a<N.ATTR.length;a++)for(let b=a+1;b<N.ATTR.length;b++)jobs.push({kind:'pull',on:[a,b]});
jobs.push({kind:'determinism'});
const[sh,shs]=process.argv.slice(2).map(Number);
jobs.forEach((j,i)=>{if(i%shs!==sh)return;let r;
 if(j.kind==='listen')r=listen(j.on,{...TONES[j.tone],cpl:j.cpl},45*K);
 else if(j.kind==='pull'){const base=listen(j.on,{gentle:true,cpl:0},10*K);r={apart:base.notesPerSec};for(const[c,k]of[[.3,'nudge'],[.65,'pull'],[1,'tangle']])r[k]=listen(j.on,{gentle:true,cpl:c},10*K).notesPerSec;}
 else{const h=()=>{const D=make([0,3,6],{gentle:false,cpl:.65});let x=0;for(let k=0;k<300;k++){const o=D.process(480);for(let i=0;i<480;i++)x=(x*31+Math.round(o.L[i]*1e9)+Math.round(o.R[i]*1e9))%2147483647;}return x;};r={same:h()===h()};}
 console.log(JSON.stringify({...j,names:j.on?j.on.map(nm):undefined,...r}));});
