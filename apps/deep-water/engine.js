// Deep Water engine: air bubbles deep in the ocean, heard from underwater.
// Physics: Minnaert resonance  f = (1/2πa)·sqrt(3γP/ρ), P = P0 + ρgh  (Minnaert 1933)
//          a rising bubble expands as the pressure drops: a = a0·(P0'/P)^(1/3), so its pitch slides down
//          rise speed of a large spherical-cap bubble: U = 0.711·sqrt(g·2a)  (Davies & Taylor 1950)
//          damping: radiation δ = ωa/c plus thermal/viscous ≈ 0.03 (Devin 1959, order of magnitude for big bubbles)
//          radiated pressure ∝ a³·(radial acceleration) ≈ a³·ω²·x
// No surface, no splashes, no flowing water: the listener is deep, everything is bubbles plus the faint deep hum.
// Plain function so the page injects it into an AudioWorklet and node can test it.
function DEEP(){
const TAU=2*Math.PI,RHO=1000,GAM=1.4,P0=101325,G=9.81,CW=1480;
const press=h=>P0+RHO*G*Math.max(0,h),omega=(a,h)=>Math.sqrt(3*GAM*press(h)/RHO)/a,minnaert=(a,h)=>omega(a,h)/TAU;
class Eng{
 constructor(SR){this.SR=SR;this.B=[];this.Q=[];this.seed=20261113;this.t=0;this.hum=1;this.humLvl=0;this.rateLvl=0;
  // master: underwater low-pass, 18 Hz high-pass (receiver/sub protection), small 4-line FDN for the open water
  this.lp=[0,0,0,0];this.hpS=[[0,0,0,0],[0,0,0,0]];const w=Math.tan(Math.PI*18/SR),k=1/(1+Math.SQRT2*w+w*w);this.hc=[k,-2*k,k,2*(w*w-1)*k,(1-Math.SQRT2*w+w*w)*k];
  this.fdn=[2399,3119,3793,4447].map(n=>({b:new Float32Array(Math.round(n*SR/48000)),w:0,lp:0}));this.fdnG=Math.pow(10,-3*(3119/48000)/4.5);
  this.brown=0;this.humLP=[0,0];this.sz=null;this.szNext=null;this.szPos=0;this.szRate=800;this.szLvl=0;this.szG=0;this.szEnv=0;this.szHP=[0,0];this.mod=0;this.KD=.25/(Math.pow(.1,3)*.06*Math.pow(omega(.1,0),2));this.vol=.6;}
 // real seismometer trace (already sped up and normalised by the page), looped; swapped in at the loop boundary
 seis(d){if(!d){this.szNext=null;this.sz=null;return;}if(!this.sz){this.sz=d.data;this.szRate=d.rate;this.szPos=0;}else{this.szNext=d.data;this.szRate=d.rate;}}
 rnd(){this.seed=(this.seed*1664525+1013904223)>>>0;return this.seed/4294967296;}
 // one bubble: a radius (m), h depth (m), pan -1..1, dist (m) from the listener, x0 initial wobble
 bubble(a,h,pan,dist,x0,rise,delay){this.Q.push({t:this.t+Math.round((delay||0)*this.SR),a,h,pan,dist,x0,rise});}
 // events from the page (live data). kind: 'single' | 'train' | 'cluster' | 'giant'
 event(e){const r=()=>this.rnd();
  if(e.kind==='giant'){this.bubble(e.a,e.h,e.pan,e.dist,.07,1,0);for(let j=0;j<6;j++)this.bubble(e.a*(.25+.3*r()),e.h+3*r(),e.pan+(r()-.5)*.3,e.dist,.05,1,.15+1.2*r());return;}
  if(e.kind==='train'){const n=e.n||6;for(let j=0;j<n;j++)this.bubble(e.a*(.85+.3*r()),e.h,e.pan+(r()-.5)*.05,e.dist,.05,1,j*(.18+.25*r()));return;}
  if(e.kind==='cluster'){const n=e.n||5;for(let j=0;j<n;j++)this.bubble(e.a*(.3+.7*r()),e.h+2*(r()-.5),e.pan+(r()-.5)*.25,e.dist,.06,1,.6*r());return;}
  this.bubble(e.a,e.h,e.pan,e.dist,.06,1,0);}
 start(q){if(this.B.length>=28){let k=0;for(let i=1;i<this.B.length;i++)if(this.B[i].env<this.B[k].env)k=i;this.B.splice(k,1);}
  const g=1/(1+q.dist/12),cut=Math.min(.9,1-Math.exp(-TAU*Math.max(250,2400/(1+q.dist/15))/this.SR));
  this.B.push({a0:q.a,h0:q.h,a:q.a,h:q.h,x:q.x0,v:0,w:omega(q.a,q.h),be:0,wake:0,rise:q.rise,n:0,age:0,env:1,
   gl:g*Math.sqrt(.5*(1-Math.max(-1,Math.min(1,q.pan)))),gr:g*Math.sqrt(.5*(1+Math.max(-1,Math.min(1,q.pan)))),rv:Math.min(.8,.15+q.dist/60),cut,lp:0,life:Math.round(Math.min(30,8+q.h/3)*this.SR)});}
 process(L,R,N){const SR=this.SR,KD=this.KD,F=this.fdn,hc=this.hc;
  for(let j=0;j<N;j++){
   for(let i=this.Q.length-1;i>=0;i--)if(this.Q[i].t<=this.t){this.start(this.Q[i]);this.Q.splice(i,1);}
   let l=0,r=0,wet=0;const B=this.B;
   for(let i=B.length-1;i>=0;i--){const b=B[i];
    if((b.n++&63)===0){if(b.rise)b.h=Math.max(0,b.h-.711*Math.sqrt(G*2*b.a)*64/SR);b.a=b.a0*Math.cbrt(press(b.h0)/press(b.h));b.w=omega(b.a,b.h);b.be=(b.w*b.a/CW+.03)*b.w/2;b.wake=b.rise?.024*b.w*b.w:0;
     const left=b.life-b.age;b.env=left<SR*3?Math.max(0,left/(SR*3)):1;}
    const acc=-b.w*b.w*b.x-2*b.be*b.v+(b.wake?(this.rnd()*2-1)*b.wake:0);b.v+=acc/SR;b.x+=b.v/SR;
    const y=-KD*b.a*b.a*b.a*b.w*b.w*b.x*b.env;b.lp+=(y-b.lp)*b.cut;l+=b.lp*b.gl;r+=b.lp*b.gr;wet+=b.lp*b.rv;
    if(++b.age>=b.life||b.h<=0)B.splice(i,1);}
   if(this.sz){const n=this.sz.length,p=this.szPos,i=p|0,f=p-i,y0=this.sz[(i-1+n)%n],y1=this.sz[i%n],y2=this.sz[(i+1)%n],y3=this.sz[(i+2)%n];
    const y=y1+.5*f*(y2-y0+f*(2*y0-5*y1+4*y2-y3+f*(3*(y1-y2)+y3-y0)));this.szG+=(this.szLvl-this.szG)*.0005;const g=y*this.szG;l+=g;r+=g;wet+=g*.4;this.szEnv+=(Math.abs(y)-this.szEnv)*.0002;
    this.szPos+=this.szRate/SR;if(this.szPos>=n){this.szPos-=n;if(this.szNext){this.sz=this.szNext;this.szNext=null;this.szPos=0;}}}
   // deep hum: brown noise below ~90 Hz, slowly breathing; its level follows how busy the live data is
   this.brown=(this.brown+(this.rnd()*2-1)*.02)*.998;const hk=1-Math.exp(-TAU*90/SR);this.humLP[0]+=(this.brown-this.humLP[0])*hk;this.humLP[1]+=(this.humLP[0]-this.humLP[1])*hk;
   this.mod+=TAU*.031/SR;this.humLvl+=((this.hum?(.35+.25*this.rateLvl)*(1+.3*Math.sin(this.mod)):0)-this.humLvl)*.00002;const hm=this.humLP[1]*this.humLvl*2.2;l+=hm;r+=hm*.92;
   // open-water reverb: 4-line Householder FDN, darkened
   let s=0;const o=[0,0,0,0];for(let k=0;k<4;k++){const d=F[k];o[k]=d.b[d.w];s+=o[k];}s*=.5;
   for(let k=0;k<4;k++){const d=F[k];let v=(o[k]-s)*this.fdnG+wet*.35;d.lp+=(v-d.lp)*.25;d.b[d.w]=d.lp;d.w=(d.w+1)%d.b.length;}
   l+=(o[0]+o[2])*.5;r+=(o[1]+o[3])*.5;
   const out=[l,r];for(let c=0;c<2;c++){const S=this.hpS[c],x=out[c],y=hc[0]*x+hc[1]*S[0]+hc[2]*S[1]-hc[3]*S[2]-hc[4]*S[3];S[1]=S[0];S[0]=x;S[3]=S[2];S[2]=y;
    const k2=1-Math.exp(-TAU*1800/SR);this.lp[2*c]+=(y-this.lp[2*c])*k2;this.lp[2*c+1]+=(this.lp[2*c]-this.lp[2*c+1])*k2;out[c]=Math.tanh(this.lp[2*c+1]*this.vol*1.6)/1.6*1.3;}
   L[j]=out[0];R[j]=out[1];this.t++;}}
}
return{Eng,minnaert,omega,press};}
if(typeof module!=='undefined')module.exports=DEEP;
