// Strange Effects listening review. Runs the app's own engine (extracted by render/mkengine.py) and measures
// what a listener would notice. Usage: node check.js <shard> <shards>  -> JSON lines on stdout.
const N=require('../render/engine.js');const R=48000,W=960;
const TONES={Gentle:{gentle:true},Gilmour:{gentle:false},Strange:{gentle:false,strange:true},Everything:{gentle:false,allT:true},'Space synth':{gentle:false,synT:true}};
const BASE={swarm:true,nP:4,recv:true,holo:true,cine:false,alive:false,move:.35,hallRT:1.8,hallSize:.7,cpl:0};
const nm=i=>N.ATTR[i].name;
// Audible onsets by spectral flux (Dixon 2006, "Onset detection revisited"): 1024-pt Hann frames, 10 ms hop,
// log-compressed magnitudes; flux = sum of rises in each bin over the previous frame; an onset is a local peak
// (±30 ms) that clears the local mean (±100 ms) by DELTA, in a frame louder than -55 dB, >= 50 ms after the last.
const subShare=(()=>{const M=8192,win=new Float64Array(M).map((_,i)=>.5-.5*Math.cos(2*Math.PI*i/M));
 function spec(x,o){const re=new Float64Array(M),im=new Float64Array(M);for(let i=0;i<M;i++)re[i]=x[o+i]*win[i];for(let i=1,j=0;i<M;i++){let b=M>>1;for(;j&b;b>>=1)j^=b;j|=b;if(i<j){const t=re[i];re[i]=re[j];re[j]=t;}}
  for(let s=2;s<=M;s*=2){const h=s/2,a=-2*Math.PI/s;for(let i=0;i<M;i+=s)for(let k=0;k<h;k++){const c=Math.cos(a*k),d=Math.sin(a*k),xr=re[i+k+h]*c-im[i+k+h]*d,xi=re[i+k+h]*d+im[i+k+h]*c;re[i+k+h]=re[i+k]-xr;im[i+k+h]=im[i+k]-xi;re[i+k]+=xr;im[i+k]+=xi;}}const P=new Float64Array(M/2);for(let k=0;k<M/2;k++)P[k]=re[k]*re[k]+im[k]*im[k];return P;}
 return(L,Rr,rate)=>{const P=new Float64Array(M/2);for(let o=0;o+M<=L.length;o+=M){const a=spec(L,o),b=spec(Rr,o);for(let k=0;k<M/2;k++)P[k]+=a[k]+b[k];}
  const band=(f0,f1)=>{let e=0;for(let k=Math.ceil(f0*M/rate);k<f1*M/rate;k++)e+=P[k];return e;},t=band(20,20000)+1e-30;
  return{sub80:+(10*Math.log10(band(20,80)/t+1e-30)).toFixed(1),rumble:+(10*Math.log10(band(20,40)/t+1e-30)).toFixed(1),punch:+(10*Math.log10(band(40,80)/t+1e-30)).toFixed(1)};};})();
const heardOnsets=(()=>{
const N=1024,HN=N/2,win=new Float64Array(N).map((_,i)=>.5-.5*Math.cos(2*Math.PI*i/N));
const rev=new Uint32Array(N);for(let i=0,b=Math.log2(N);i<N;i++){let r=0;for(let k=0;k<b;k++)r|=((i>>k)&1)<<(b-1-k);rev[i]=r;}
function fft(re,im){for(let i=0;i<N;i++){const j=rev[i];if(j>i){[re[i],re[j]]=[re[j],re[i]];[im[i],im[j]]=[im[j],im[i]];}}
 for(let s=2;s<=N;s*=2){const h=s/2,a=-2*Math.PI/s;for(let i=0;i<N;i+=s)for(let k=0;k<h;k++){const c=Math.cos(a*k),d=Math.sin(a*k),xr=re[i+k+h]*c-im[i+k+h]*d,xi=re[i+k+h]*d+im[i+k+h]*c;re[i+k+h]=re[i+k]-xr;im[i+k+h]=im[i+k]-xi;re[i+k]+=xr;im[i+k]+=xi;}}}
// bands: 1/3 octave from 63 Hz to 12.5 kHz; level in dB with a -80 dB floor; flux = summed rise of each band over the
// louder of the two frames before (SuperFlux-style max filter, Böck & Widmer 2013, which ignores beating flicker)
const TH=7,FL=3;
function heardOnsets(L,R,rate){const H=Math.round(rate*.01),nf=Math.floor((L.length-N)/H);const B=[];{let a=Math.round(100*N/rate);for(let c=100*Math.pow(2,1/3);a<HN;c*=Math.pow(2,1/3)){let b=Math.min(HN,Math.round(c*N/rate));if(b-a<4&&b<HN)continue;B.push([a,b]);a=b;if(c>12500)break;}}
 const re=new Float64Array(N),im=new Float64Array(N),Lv=[],flux=new Float64Array(nf),en=new Float64Array(nf);
 for(let f=0;f<nf;f++){let e=0;for(let i=0;i<N;i++){const x=.5*(L[f*H+i]+R[f*H+i]);re[i]=x*win[i];im[i]=0;e+=x*x;}en[f]=e/N;fft(re,im);
  const lv=B.map(([a,b])=>{let p=0;for(let k=a;k<b;k++)p+=re[k]*re[k]+im[k]*im[k];return 10*Math.log10(p/(N*N/16)+1e-12);});const top=Math.max(...lv);for(let j=0;j<lv.length;j++)lv[j]=Math.max(lv[j],top-40,-70);Lv.push(lv);
  if(f>=3){let fl=0;for(let j=0;j<B.length;j++){const d=lv[j]-Math.max(Lv[f-1][j],Lv[f-2][j],Lv[f-3][j])-FL;if(d>0)fl+=d;}flux[f]=fl;}}
 let c=0,last=-99;for(let f=10;f<nf-10;f++){let pk=true;for(let j=f-3;j<=f+3;j++)if(flux[j]>flux[f]){pk=false;break;}if(!pk)continue;let m=0;for(let j=f-10;j<=f+10;j++)m+=flux[j];m/=21;
  if(flux[f]>=TH&&flux[f]>1.5*m&&en[f]>3.2e-6&&f-last>=5){c++;last=f;}}return c/(nf*.01);}
return heardOnsets;})();
const K=+(process.env.SE_SCALE||1); // SE_SCALE<1 only for quick smoke tests
// set the engine up exactly as the app does: it opens with the swarm routes; a style re-routes the effects
// through the app's useRoutes() mapping, switches the hall like the app, and Cinematic slows Movement
function make(on,cfg){const D=N.makeDSP(R);D.V.forEach((v,i)=>v.on=on.includes(i));Object.assign(D,BASE);
 N.EFFECTS.forEach((e,i)=>D.route[i]=N.SWARM_ROUTES[e.id]);const{style,...rest}=cfg;
 if(style){const k=style,c=k!=='r',wr=k==='w',el=k==='e',rk=k==='k',al=k==='a'||wr||el||rk;Object.assign(D,{cine:c,alive:al,war:wr,elec:el,rank:rk,move:k==='c'?.12:.35});
  if((el||rk)&&D.hallRT>1.8)Object.assign(D,{hallRT:1.8,hallSize:.7});else if(!el&&!rk&&D.hallRT<=1.8)Object.assign(D,{hallRT:4.5,hallSize:1});
  const T=rk?N.RANK_ROUTES:al?N.ALIVE_ROUTES:c?N.CINE_ROUTES:N.DEFAULT_ROUTES,L=[];on.forEach(vi=>{for(let q=0;q<3;q++)L.push(vi*3+q);});if(rk)for(let q=0;q<8;q++)L.push(100+q);
  N.EFFECTS.forEach((e,i)=>{const d=T[e.id];D.route[i]=d===undefined||d<0?-1:d>=100?d:L[d%L.length];});}
 Object.assign(D,rest);return D;}
// listening run: 20 ms windows; silence = below -60 dBFS; notes = particle crossings; clipping = |sample| > .99
function listen(on,cfg,sec){const D=make(on,cfg);D.process(2*R);const hk=Math.exp(-2*Math.PI*300/R);let h1=[0,0],h2=[0,0],hx=[0,0],hy=[0,0],pmn=0; // two one-pole high-passes at 300 Hz
 const dbs=[],AL=new Float32Array(Math.round(sec*R/W)*W),AR=new Float32Array(AL.length);let run=0,longest=0,sil=0,n=0,mn=0,up=0,clip=0,tot=0,nan=0;const notes=on.map(()=>0);
 for(let r=0;r<sec*R/W;r++){const ps=on.map(i=>[...D.V[i].Ps]);const o=D.process(W);AL.set(o.L,r*W);AR.set(o.R,r*W);let e=0,ep=0;
  for(let i=0;i<W;i++){const a=o.L[i],b=o.R[i];if(!(a===a&&b===b))nan++;e+=a*a+b*b;
   for(let ch=0;ch<2;ch++){const x=ch?b:a,y1=hk*(h1[ch]+x-hx[ch]);hx[ch]=x;h1[ch]=y1;const y2=hk*(h2[ch]+y1-hy[ch]);hy[ch]=y1;h2[ch]=y2;ep+=y2*y2;}if(Math.abs(a)>.99||Math.abs(b)>.99)clip++;tot+=2;}
  on.forEach((v,j)=>{const P=D.V[v].Ps,both=D.V[v].def.sec[2];for(let q=0;q<P.length&&q<ps[j].length;q++)if(P[q]!==ps[j][q]&&ps[j][q]!==0&&(P[q]===1||both))notes[j]++;});
  const db=10*Math.log10(e/(2*W)+1e-20);dbs.push(db);pmn=Math.min(pmn,10*Math.log10(ep/(2*W)+1e-20));n++;mn=Math.min(mn,db);if(D.brGate&&D.brGate()>.5)up++;if(db<-60){sil++;run++;longest=Math.max(longest,run);}else run=0;}
 return{longestSilence:+(longest*W/R).toFixed(2),silentPct:+(100*sil/n).toFixed(1),quietestDb:+mn.toFixed(1),phoneQuietestDb:+pmn.toFixed(1),undertowPct:+(100*up/n).toFixed(1),heardPerSec:+heardOnsets(AL,AR,R).toFixed(2),...subShare(AL,AR,R),recv:D.recv,contrastDb:+(()=>{const q=dbs.slice().sort((x,y)=>x-y);return q[Math.floor(.9*q.length)]-q[Math.floor(.1*q.length)];})().toFixed(1),move:D.move,clipPct:+(100*clip/tot).toFixed(3),nan:nan+(D.bad||0),notesPerSec:notes.map(x=>+(x/sec).toFixed(2))};}
const jobs=[];
for(const t in TONES){for(let a=0;a<N.ATTR.length;a++)jobs.push({kind:'listen',tone:t,on:[a],cpl:0});
 for(const c of[0,1])for(const p of[[3,1],[4,8],[2,4],[0,7]])jobs.push({kind:'listen',tone:t,on:p,cpl:c});jobs.push({kind:'listen',tone:t,on:N.ATTR.map((_,i)=>i),cpl:1});}
const SET={'Slow':{move:.06},'Fast':{move:1.6},'1 particle':{nP:1},'32 particles':{nP:32},'128 particles':{nP:128},'Hall':{hallRT:4.5,hallSize:1},'Cathedral':{hallRT:9,hallSize:1.5},'Stereo':{recv:false},'Mono':{recv:false,mono:true},
 /* styles (Rank, Electric, War, Alive, Cinematic, Raw) are hidden in the app and never switched on, so they are not tested */'Pair harmonic':{hm:1},'Swarm harmonic':{hm:2}};
for(const s in SET)for(const on of[[0],[4,8],N.ATTR.map((_,i)=>i)])jobs.push({kind:'listen',tone:'Gentle',setting:s,on,cpl:on.length>2?1:0});
for(let a=0;a<N.ATTR.length;a++)for(let b=a+1;b<N.ATTR.length;b++)jobs.push({kind:'pull',on:[a,b]});
jobs.push({kind:'determinism'});
const[sh,shs]=process.argv.slice(2).map(Number);
jobs.forEach((j,i)=>{if(i%shs!==sh)return;let r;
 if(j.kind==='listen')r=listen(j.on,{...TONES[j.tone],cpl:j.cpl,...(j.setting?SET[j.setting]:{})},45*K);
 else if(j.kind==='pull'){const base=listen(j.on,{gentle:true,cpl:0},10*K);r={apart:base.notesPerSec};for(const[c,k]of[[.3,'nudge'],[.65,'pull'],[1,'tangle']])r[k]=listen(j.on,{gentle:true,cpl:c},10*K).notesPerSec;}
 else{const h=()=>{const D=make([0,3,6],{gentle:false,cpl:.65});let x=0;for(let k=0;k<300;k++){const o=D.process(480);for(let i=0;i<480;i++)x=(x*31+Math.round(o.L[i]*1e9)+Math.round(o.R[i]*1e9))%2147483647;}return x;};r={same:h()===h()};}
 console.log(JSON.stringify({...j,names:j.on?j.on.map(nm):undefined,...r}));});
