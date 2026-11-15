// Morel World engine: the Morel attractor map swings a poplar stick against the dried morel's wall.
// Runs the same in the audio worklet and in node (review). One instance = one stereo output.
function ENGINE(PH){
const TAU=2*Math.PI;
function rng(seed){let x=seed>>>0||1;return()=>{x^=x<<13;x>>>=0;x^=x>>17;x^=x<<5;x>>>=0;return x/4294967296;};}
class Eng{
 constructor(SR){this.SR=SR;this.rand=rng(1711);this.nz=rng(99);this.st=[.2137,1,.5];this.timer=Math.round(.25*SR);this.t=0;this.events=[];
  this.cfg={size:2,stick:1,dry:1,listen:0,pace:0};this.pulses=[];this.dl=new Float32Array(2*SR);this.dr=new Float32Array(2*SR);this.dp=0;
  this.hp=[[0,0,0,0],[0,0,0,0]];this.fade=1;this.strikes=0;this.setCfg(this.cfg);}
 setCfg(c){Object.assign(this.cfg,c);const W=PH.build(this.cfg,this.SR);this.W=W;const n=W.n;
  this.y1=new Float64Array(n);this.y2=new Float64Array(n);this.inp=new Float64Array(n);this.act=new Uint8Array(n);this.al=[];this.pulses=[];this.dl.fill(0);this.dr.fill(0);
  this.gmax=new Float64Array(n);for(let i=0;i<n;i++)this.gmax[i]=Math.max(Math.abs(W.gL[i]),Math.abs(W.gR[i]));
  // 20 Hz high-pass (receiver/sub protection), 2nd-order Butterworth
  const w=Math.tan(Math.PI*20/this.SR),k=1/(1+Math.SQRT2*w+w*w);this.hc=[k,-2*k,k,2*(w*w-1)*k,(1-Math.SQRT2*w+w*w)*k];
  this.calibrate();this.floorInit();this.Ed=[this.Ef[0],this.Ef[1]];this.info=this.describe();}
 // Group gains: each group's reference-strike peak relative to the shell's. Then the whole reference strike peaks at 0.3.
 calibrate(){const W=this.W,SR=this.SR,n=W.n,T=Math.max(2,Math.round(W.T0*SR)),Fm=2*W.J0/W.T0,L=Math.round(.15*SR);
  const peak=new Float64Array(4),pts=[];let q=[.2137,1,.5];for(let k=0;k<10;k++){q=PH.M(q[0],q[1],q[2]);pts.push([q[0],q[1]]);}
  for(const [s,th] of pts){const w=PH.weights(W,s,th,true);for(let g=0;g<4;g++){const oL=new Float64Array(L),oR=new Float64Array(L);
   for(let i=0;i<n;i++){if(W.kind[i]!==g)continue;let a=0,b=0;const wi=w[i]*W.gi[i]*Fm,gl=W.gL[i],gr=W.gR[i];if(!wi)continue;
    for(let t=0;t<L;t++){const x=t<T?.5*(1-Math.cos(TAU*t/T))*wi:0,y=W.b1[i]*a+W.b2[i]*b+x;b=a;a=y;oL[t]+=gl*y;oR[t]+=gr*y;}}
   let m=0;for(let t=0;t<L;t++)m=Math.max(m,Math.abs(oL[t]),Math.abs(oR[t]));peak[g]=Math.max(peak[g],m);}}
  const ref=peak[0]||peak[2]||1,want=[1,W.lis===2?1:.7,W.lis===0?.8:W.lis===1?.15:.35,.3];this.gg=[0,0,0,0];
  for(let g=0;g<4;g++)this.gg[g]=peak[g]>0?want[g]*ref/peak[g]:0;
  const tot=want.reduce((a,b,i)=>a+(peak[i]>0?b:0),0)*ref;this.norm=.3/(tot||1);for(let g=0;g<4;g++)this.gg[g]*=this.norm;
  for(let i=0;i<n;i++){const g=this.gg[W.kind[i]];W.gL[i]*=g;W.gR[i]*=g;this.gmax[i]*=g;}
  this.refPeak=.3;this.click=.15;this.dif=W.fS<.4*SR?.08:0;}
 // Never silent: the seashell effect. Ambient air noise rings the cavity modes (inside) or the lowest shell modes (wind, outside),
 // plus the steady diffuse field above the Schroeder frequency. Target -42 dBFS RMS, set analytically from resonator noise gain.
 floorInit(){const W=this.W,n=W.n,src=this.W.lis===0?2:0,tgt=Math.pow(10,-42/20);this.fl=[];let pw=0;
  for(let i=0;i<n;i++){if(W.kind[i]!==src)continue;if(src===0&&W.md[i].n>2)continue;const R2=-W.b2[i],R=Math.sqrt(R2),c=W.b1[i]/(2*R);
   const v=(1+R2)/((1-R2)*((1+R2)*(1+R2)-4*R2*c*c));pw+=v*(W.gL[i]*W.gL[i]+W.gR[i]*W.gR[i])/2;this.fl.push(i);}
  const share=this.dif?.5:1;this.fg=pw>0?Math.sqrt(share*tgt*tgt/pw):0;this.isFl=new Uint8Array(n);for(const i of this.fl){this.act[i]=1;this.isFl[i]=1;}
  const ef=this.dif?(1-share)*tgt*tgt:0;this.Ef=[ef,ef];this.rebuildActive();}
 rebuildActive(){const a=[];for(let i=0;i<this.W.n;i++)if(this.act[i])a.push(i);this.al=a;}
 describe(){const W=this.W,r=x=>x>=100?Math.round(x):x>=10?+x.toFixed(1):+x.toFixed(2);
  return{size:W.Z.n,H:W.H,stick:W.K.n,dry:W.D.n,listen:PH.LISTEN[W.lis],ring:r(W.ring),low:r(W.low),fc:r(W.fc),panelLo:r(W.panelLo),panelHi:r(W.panelHi),
   cav1:r(W.cav1),RT:r(W.RT),RTh:r(W.RTh),fS:r(W.fS),T0ms:r(W.T0*1e3),stick1:r(W.stick1),stickKg:r(W.sm),counts:[0,1,2,3].map(k=>W.md.filter(q=>q.k===k).length),V:r(W.V)};}
 // One hit of the stick at (s,th). strength ~1. Schedules the contact pulse after the sound's travel time, the direct click
 // (ITD/ILD by path difference), and brittle aftershocks (Omori law in time, power law in size).
 hit(s,th,strength,big){const W=this.W,SR=this.SR,H=W.H,R=PH.wallR(H,s,th),ridge=1-PH.P(th,s);
  const k=W.k0*(1+.6*ridge),T=Math.PI*Math.sqrt(W.meff/k),J=W.J0*strength,Fm=2*J/T,lg=Math.pow(strength,.25)/strength; // loudness: Stevens-compressed
  const p=W.pos(s,th,R),d0=W.dist(p,W.micP[0]),d1=W.dist(p,W.micP[1]),dm=(d0+d1)/2,dly=Math.round(dm/PH.C0*SR);
  const w=PH.weights(W,s,th,true),idx=[],ws=[];for(let i=0;i<W.n;i++)if(w[i]){idx.push(i);ws.push(w[i]*W.gi[i]);}
  const ns=Math.max(2,Math.round(T*SR));this.pulses.push({t0:this.t+dly,n:ns,F:Fm*lg,idx:Int32Array.from(idx),w:Float64Array.from(ws)});
    // direct click: derivative of the contact force, heard first (precedence) with the true path difference
  const ca=this.click*Math.pow(strength,.25)*Math.min(1,W.T0/T)*(W.lis===1?.6:1);
  for(let c=0;c<2;c++){const dd=c?d1:d0,del=Math.round(dd/PH.C0*SR),g=ca*Math.min(1,Math.min(d0,d1)/dd);const buf=c?this.dr:this.dl;
   for(let j=0;j<ns;j++)buf[(this.dp+del+j)%buf.length]+=g*Math.sin(TAU*j/ns);}
  if(this.dif){const a=this.dif*Math.pow(strength,.25);this.Ed[0]+=a*a*(.5+.5*Math.random());this.Ed[1]+=a*a*(.5+.5*Math.random());}
  // aftershocks (dried, brittle tissue cracking)
  const cr=W.D.cr*(big?2:1);if(cr>0){const N=Math.min(48,Math.round(cr*18*Math.sqrt(strength)));
   for(let a=0;a<N;a++){const u=this.rand(),tt=.004*(Math.pow(1-u*.999,-1/.3)-1);if(tt>2.5)continue;const sz=Math.min(30,Math.pow(1-this.rand()*.999,-1/.6))/30;
    const s2=Math.min(.98,Math.max(.02,s+(this.rand()-.5)*.12)),th2=th+(this.rand()-.5)*.9,w2=PH.weights(W,s2,th2,false),i2=[],v2=[];
    for(let i=0;i<W.n;i++)if(w2[i]&&W.kind[i]!==2){i2.push(i);v2.push(w2[i]*W.gi[i]);}
    const n2=Math.max(2,Math.round(8e-5*SR));this.pulses.push({t0:this.t+dly+Math.round(tt*SR),n:n2,F:Fm*lg*.08*sz,idx:Int32Array.from(i2),w:Float64Array.from(v2),cr:sz*ca*.5});}}
  this.strikes++;this.events.push({s,th,r:R,ridge,T,strength,dly:dm/PH.C0,big:!!big});}
 step(){const W=this.W,a=this.st,b=PH.M(a[0],a[1],a[2]),pa=[a[2]*Math.cos(a[1]),PH.PM[1]*a[0],a[2]*Math.sin(a[1])],pb=[b[2]*Math.cos(b[1]),PH.PM[1]*b[0],b[2]*Math.sin(b[1])];
  const dist=Math.hypot(pa[0]-pb[0],pa[1]-pb[1],pa[2]-pb[2]);this.st=b;
  const strength=Math.min(1.6,Math.max(.2,dist/3.2));this.hit(b[0],b[1],strength,false);
  const T=PH.PACE[this.cfg.pace].T;this.timer=Math.round(T*(.45+.55*dist/3.2)*this.SR);} // rhythm: time to swing the map's distance
 bigHit(){const a=this.st,b=PH.M(a[0],a[1],a[2]);this.st=b;this.hit(b[0],b[1],2.2,true);}
 process(L,R,N){const W=this.W,y1=this.y1,y2=this.y2,inp=this.inp,b1=W.b1,b2=W.b2,gL=W.gL,gR=W.gR,nz=this.nz,fg=this.fg,fl=this.fl;
  const SR=this.SR,dec=[Math.exp(-2*6.91/(W.RT*SR)),Math.exp(-2*6.91/(W.RTh*SR))],hc=this.hc;
  for(let j=0;j<N;j++){if(--this.timer<=0)this.step();
   // floor noise
   for(let q=0;q<fl.length;q++)inp[fl[q]]+=fg*(nz()*2-1)*1.732;
   // contact pulses
   for(let p=this.pulses.length-1;p>=0;p--){const P=this.pulses[p],k=this.t-P.t0;if(k<0)continue;if(k>=P.n){this.pulses.splice(p,1);continue;}
    if(P.cr!==undefined&&k===0){for(let c=0;c<2;c++){const buf=c?this.dr:this.dl;for(let m=0;m<P.n;m++)buf[(this.dp+m)%buf.length]+=P.cr*(nz()*2-1);} }
    const F=P.F*.5*(1-Math.cos(TAU*k/P.n)),ix=P.idx,w=P.w;for(let q=0;q<ix.length;q++){inp[ix[q]]+=w[q]*F;}
    if(k===0){for(let q=0;q<ix.length;q++)this.act[ix[q]]=1;this.rebuildActive();}}
   let l=0,r=0;const al=this.al;for(let q=0;q<al.length;q++){const i=al[q],y=b1[i]*y1[i]+b2[i]*y2[i]+inp[i];inp[i]=0;y2[i]=y1[i];y1[i]=y;l+=gL[i]*y;r+=gR[i]*y;}
   // diffuse tail (two bands crudely: decay at the low-band RT; high band handled by the cavity damping split)
   if(this.dif){this.Ed[0]=this.Ef[0]+(this.Ed[0]-this.Ef[0])*dec[0];this.Ed[1]=this.Ef[1]+(this.Ed[1]-this.Ef[1])*dec[0];l+=Math.sqrt(this.Ed[0])*(nz()*2-1)*1.732;r+=Math.sqrt(this.Ed[1])*(nz()*2-1)*1.732;}
   const dp=this.dp;l+=this.dl[dp];r+=this.dr[dp];this.dl[dp]=0;this.dr[dp]=0;this.dp=(dp+1)%this.dl.length;
   // high-pass + gentle safety saturation
   const o=[l,r];for(let c=0;c<2;c++){const s=this.hp[c],x=o[c],y=hc[0]*x+hc[1]*s[0]+hc[2]*s[1]-hc[3]*s[2]-hc[4]*s[3];s[1]=s[0];s[0]=x;s[3]=s[2];s[2]=y;o[c]=Math.abs(y)<.8?y:Math.sign(y)*(.8+.2*Math.tanh((Math.abs(y)-.8)/.2));}
   L[j]=o[0]*this.fade;R[j]=o[1]*this.fade;this.t++;
   if((this.t&127)===0){let ch=false;const al=this.al;for(let q=0;q<al.length;q++){const i=al[q];if(Math.abs(y1[i])*this.gmax[i]<1e-7&&Math.abs(y2[i])*this.gmax[i]<1e-7&&!this.isFl[i]){this.act[i]=0;ch=true;}}if(ch)this.rebuildActive();}}
  }
}
return Eng;}
if(typeof module!=='undefined')module.exports=ENGINE;
