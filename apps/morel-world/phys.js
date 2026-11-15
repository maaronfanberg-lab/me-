// Morel World physics. Everything here is derived from Alex's Morel attractor map (MGS-1 shape F, twist Ω, hex pits P)
// plus textbook mechanics: Donnell shell modes, clamped-plate pit panels, Webster-horn cavity, Sabine reverb,
// Euler–Bernoulli poplar stick, raised-cosine contact (van den Doel), Omori-law brittle crackle.
// Plain function so the page can inject it into the audio worklet (PHYS.toString()) and node can test it.
function PHYS(){
const TAU=2*Math.PI,MK=28/Math.sqrt(3),PM=[3,6,.6],NU=.3,C0=343,RHO0=1.2;
const F=s=>Math.pow(Math.max(0,Math.sin(Math.PI*(.18+.82*s))),.7)*(1-.1*s);
const Om=(th,s)=>.025*Math.sin(3*th+2*Math.PI*s)+.015*Math.sin(7*th-5*Math.PI*s);
function P(th,s){const u=((th/TAU)%1+1)%1;let d1=1e9,d2=1e9;const j0=Math.max(0,Math.floor(s*14)-2),j1=Math.min(13,Math.floor(s*14)+2);
 for(let j=j0;j<=j1;j++){const ds=MK*(s-(j+.5)/14),ds2=ds*ds;for(let i=0;i<12;i++){let dl=((u-(i+.5*(j%2))/12+.5)%1+1)%1-.5;const d=Math.sqrt(144*dl*dl+ds2);if(d<d1){d2=d1;d1=d;}else if(d<d2)d2=d;}}
 return 1-Math.exp(-8*Math.pow((d2-d1)/(d2+.01),2));}
function M(s,th,r){let s1=4*s*(1-s);if(!(s1>1e-12&&s1<1-1e-12))s1=.2137+((th*7.31)%.01);const th1=(((2*th+.3+Om(th,s))%TAU)+TAU)%TAU;
 return[s1,th1,.15*r+.85*PM[0]*F(s1)*(1+Om(th1,s1))*(1-PM[2]*P(th1,s1))];}
const SIZES=[{n:'Hand',H:.1},{n:'House',H:5},{n:'Silo',H:20},{n:'Giant',H:60}];
const STICKS=[{n:'Twig',r:.004,L:.3,v:8},{n:'Stick',r:.015,L:1,v:10},{n:'Branch',r:.05,L:3,v:7},{n:'Log',r:.25,L:6,v:3}];
// dried-mushroom values are estimates (fresh tissue ~MPa; drying stiffens and lightens it, lowers loss); alpha = wall absorption
const DRY=[{n:'Fresh',E:3e6,rho:900,eta:.12,cr:0,e:.15,al:.3},{n:'Dry',E:40e6,rho:250,eta:.04,cr:.5,e:.3,al:.15},{n:'Bone dry',E:90e6,rho:180,eta:.022,cr:1,e:.35,al:.1}];
const POP={E:9.4e9,rho:400,eta:.012}; // Populus deltoides, USDA FPL Wood Handbook (12% MC)
const LISTEN=['Inside','Outside','Ear to wall'],PACE=[{n:'Calm',T:1.6},{n:'Medium',T:.8},{n:'Busy',T:.4}];
const Rm=(H,s)=>H/PM[1]*PM[0]*F(Math.min(1,Math.max(0,s)));
const wallR=(H,s,th)=>Rm(H,s)*(1+Om(th,s))*(1-PM[2]*P(th,s));
const thick=(th,s)=>(1.6-.9*P(th,s))*(1+Om(th,s)); // ridges thicker than pit floors
const erbn=f=>21.4*Math.log10(4.37e-3*f+1);
const sig=(f,fc)=>1/Math.sqrt(1+Math.pow(fc/f,2)); // radiation efficiency, ~f/fc below coincidence, 1 above
function Jn(n,x){let s=0,t=Math.pow(x/2,n);for(let k=1;k<=n;k++)t/=k;for(let k=0;k<40;k++){s+=t;t*=-(x*x/4)/((k+1)*(k+1+n));if(Math.abs(t)<1e-14)break;}return s;}
// zeros of J_n' (rigid-wall transverse modes of a circular duct): [n, j'_nq]
const JP=[[1,1.8412],[2,3.0542],[0,3.8317],[3,4.2012],[4,5.3176],[1,5.3314],[5,6.4156],[2,6.7061],[0,7.0156],[6,7.5013],[3,8.0152],[1,8.5363],[7,8.5778],[4,9.2824],[8,9.6474],[2,9.9695],[0,10.1735]];
// Webster horn A(x) along the hollow, rigid ends. Finite volumes -> symmetric tridiagonal, Sturm bisection + inverse iteration.
function horn(H,nl,N){N=N||240;const dx=H/N,A=new Float64Array(N),Af=new Float64Array(N+1),Rx=H/2;
 for(let i=0;i<N;i++){const R=Math.max(Rm(H,(i+.5)/N),.03*Rx);A[i]=Math.PI*R*R;}for(let i=1;i<N;i++)Af[i]=(A[i-1]+A[i])/2;
 const d=new Float64Array(N),e=new Float64Array(N);for(let i=0;i<N;i++){d[i]=(Af[i]+Af[i+1])/(dx*dx*A[i]);if(i)e[i]=-Af[i]/(dx*dx*Math.sqrt(A[i-1]*A[i]));}
 const cnt=x=>{let c=0,q=1;for(let i=0;i<N;i++){q=d[i]-x-(i?e[i]*e[i]/q:0);if(q===0)q=-1e-300;if(q<0)c++;}return c;};
 let hi=0;for(let i=0;i<N;i++)hi=Math.max(hi,d[i]+Math.abs(e[i])+(i<N-1?Math.abs(e[i+1]):0));
 const out=[];for(let k=1;k<=nl&&k<N;k++){let lo=0,up=hi;for(let it=0;it<80;it++){const m=(lo+up)/2;if(cnt(m)>k)up=m;else lo=m;}const lam=(lo+up)/2;
  // inverse iteration (Thomas) for the shape
  let x=new Float64Array(N).fill(1);const sh=lam*(1+1e-9)+1e-12;for(let it=0;it<3;it++){const c=new Float64Array(N),y=new Float64Array(N);let b=d[0]-sh;c[0]=e[1]/b;y[0]=x[0]/b;
   for(let i=1;i<N;i++){const bb=d[i]-sh-e[i]*c[i-1];c[i]=i<N-1?e[i+1]/bb:0;y[i]=(x[i]-e[i]*y[i-1])/bb;}for(let i=N-2;i>=0;i--)y[i]-=c[i]*y[i+1];let m=0;for(let i=0;i<N;i++)m=Math.max(m,Math.abs(y[i]));for(let i=0;i<N;i++)y[i]/=m;x=y;}
  const psi=new Float32Array(N);let m=0;for(let i=0;i<N;i++){psi[i]=x[i]/Math.sqrt(A[i]);m=Math.max(m,Math.abs(psi[i]));}for(let i=0;i<N;i++)psi[i]/=m;
  out.push({f:C0*Math.sqrt(lam)/TAU,psi});}
 let V=0,S=Math.PI*Math.pow(Rm(H,0),2);for(let i=0;i<N;i++){V+=A[i]*dx;const R0=Rm(H,i/N),R1=Rm(H,(i+1)/N);S+=Math.PI*(R0+R1)*Math.hypot(dx,R1-R0);}
 return{modes:out,V,S,N};}
const at=(psi,s)=>psi[Math.min(psi.length-1,Math.max(0,Math.floor(s*psi.length)))];

// Build every resonator for one world. Returns flat arrays the engine runs, plus the numbers the page explains.
function build(cfg,SR){
 const Z=SIZES[cfg.size],K=STICKS[cfg.stick],D=DRY[cfg.dry],H=Z.H,lis=cfg.listen,fmax=Math.min(.45*SR,9000);
 const h=.012*H,cL=Math.sqrt(D.E/(D.rho*(1-NU*NU)));
 let Rb=0;for(let i=0;i<200;i++)Rb+=Rm(H,(i+.5)/200)/200;const Rx=H/2*Math.max(...Array.from({length:101},(_,i)=>F(i/100)));
 // mean thickness factor around the widest ring and its Fourier content (hex lattice -> splits n=6,12,... pairs)
 // averaged over the whole height: alternate rows are offset half a cell, so the 12-around part largely cancels
 const NR=512,NSR=28,ring=new Float64Array(NR);let gbar=0;for(let a=0;a<NSR;a++){const sa=.05+.9*(a+.5)/NSR;for(let i=0;i<NR;i++){const v=thick(TAU*i/NR,sa)/NSR;ring[i]+=v;gbar+=v/NR;}}
 const cF=k=>{let re=0,im=0;for(let i=0;i<NR;i++){re+=ring[i]*Math.cos(k*TAU*i/NR);im-=ring[i]*Math.sin(k*TAU*i/NR);}return{a:Math.hypot(re,im)/NR/gbar,p:Math.atan2(im,re)};};
 const he=h*gbar,w0=cL/Rb,bend=he*he/(12*Rb*Rb),fc=C0*C0*Math.sqrt(12*D.rho*(1-NU*NU)/D.E)/(TAU*he);
 // Mic positions (s, theta, radius from axis) for left/right
 const Rl=x=>Rm(H,x);let mic;
 if(lis===0)mic=[[.05,.6,.35*Rl(.05)],[.05,-.6,.35*Rl(.05)]];else if(lis===1)mic=[[.3,.25,3*Rx],[.3,-.25,3*Rx]];else mic=[[.3,0,Rl(.3)],[.3,.12,Rl(.3)]];
 const pos=(s,th,r)=>[r*Math.cos(th),s*H,r*Math.sin(th)],dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
 const micP=mic.map(m=>pos(m[0],m[1],m[2]));
 const md=[];// modes: {k:kind,f,d,M,gL,gR, shape params}
 // ---- shell (Donnell), ERB-thinned: at most KB per half-ERB bin, energy kept by sqrt(N/kept)
 const fsh=n=>m=>{const lam=m*Math.PI*Rb/H,a=lam*lam,b=n*n;return w0*Math.sqrt(a*a/((a+b)*(a+b))+bend*(a+b)*(a+b))/TAU;};
 const B0=erbn(16),NB=Math.ceil((erbn(fmax)-B0)/.5)+1,KB=4,cnt=new Int32Array(NB),run=new Int32Array(NB);
 const each=cb=>{for(let m=1;m<400;m++){let prev=1e99,any=false;for(let n=0;n<2000;n++){const f=fsh(n)(m);if(f>fmax&&f>prev)break;prev=f;if(f<16||f>fmax)continue;any=true;cb(m,n,f,0);if(n)cb(m,n,f,1);}
   const lam=m*Math.PI*Rb/H;if(w0*Math.sqrt(bend)*lam*lam/TAU>fmax&&!any)break;}};
 // a pair (cos, sin) is chosen together so split pairs can beat; bins count modes, pairs count twice
 each((m,n,f,o)=>{if(!o)cnt[Math.floor((erbn(f)-B0)/.5)]+=n?2:1;});
 each((m,n,f,o)=>{if(o)return;const b=Math.floor((erbn(f)-B0)/.5),N=cnt[b],j=run[b];run[b]+=n?2:1;const kept=Math.min(KB,N);
  let hit=false;for(let c=0;c<kept;c++){const t=Math.floor((c+.5)*N/kept);if(t>=j&&t<j+(n?2:1))hit=true;}if(!hit)return;
  const wt=Math.sqrt(N/kept),Mm=D.rho*he*TAU*Rb*H*(n?.25:.5);
  if(!n){md.push({k:0,m,n,o:0,ph:0,f,M:Mm,wt});return;}const q=cF(2*n);
  for(let oo=0;oo<2;oo++)md.push({k:0,m,n,o:oo,ph:q.p/(2*n),f:f*(1+(oo?-1:1)*1.5*q.a),M:Mm,wt});});
 // ---- 168 pit panels (clamped circular plate, pit floor 0.7 h): 10.2158, 21.26, 34.88
 const hp=.7*h,Dp=D.E*hp*hp*hp/(12*(1-NU*NU)),fcp=C0*C0*Math.sqrt(12*D.rho*(1-NU*NU)/D.E)/(TAU*hp);
 for(let j=0;j<14;j++)for(let i=0;i<12;i++){const s=(j+.5)/14,th=TAU*(i+.5*(j%2))/12,R=Rl(s),a=.45*Math.min(TAU*R/12,H/14);if(a<=0)continue;
  const f1=10.2158/(TAU*a*a)*Math.sqrt(Dp/(D.rho*hp));[[1,1],[2.0815,.6],[3.4136,.4]].forEach(([r,w])=>{const f=f1*r;if(f>16&&f<fmax)md.push({k:1,s,th,a,f,M:.18*D.rho*hp*Math.PI*a*a,wt:w,R});});}
 // ---- cavity: Webster longitudinal x circular-duct transverse (separable approximation at the widest radius)
 const hn=horn(H,48),RT=.161*hn.V/(hn.S*D.al),RTh=.161*hn.V/(hn.S*D.al+4*.006*hn.V),fS=2000*Math.sqrt(RT/hn.V),fmc=Math.min(.45*SR,Math.max(3*fS,1));
 const dc=6.91/RT,lmodes=[{f:0,psi:null}].concat(hn.modes);let nc=0;
 for(const tr of [[0,0]].concat(JP)){const ft=tr[1]*C0/(TAU*Rx);if(ft>fmc)continue;for(const lm of lmodes){const f=Math.hypot(lm.f,ft);if(f<16||f>fmc||nc>=96)continue;
   for(let o=0;o<(tr[0]?2:1);o++){md.push({k:2,f,n:tr[0],o,jp:tr[1],psi:lm.psi});nc++;}}}
 // ---- poplar stick, free-free Euler–Bernoulli; held in a hand (extra 6/s loss)
 const sm=POP.rho*Math.PI*K.r*K.r*K.L,sc=K.r/2*Math.sqrt(POP.E/POP.rho);
 [4.7300,7.8532,10.9956,14.1372].forEach(b=>{const f=b*b/(TAU*K.L*K.L)*sc;if(f<fmax)md.push({k:3,f,M:sm});});
 // ---- contact (raised cosine): Hertz-like local stiffness 2E*r of the softer body (the dried morel)
 const meff=sm/3,k0=2*D.E/(1-NU*NU)*K.r,J0=meff*K.v*(1+D.e),T0=Math.PI*Math.sqrt(meff/k0);
 // ---- per-mode damping and listener gains (velocity, radiation efficiency, distance)
 const n=md.length,f=new Float64Array(n),b1=new Float64Array(n),b2=new Float64Array(n),gi=new Float64Array(n),gL=new Float64Array(n),gR=new Float64Array(n),kind=new Uint8Array(n);
 const dShell=x=>Math.PI*x*D.eta+RHO0*C0*sig(x,fc)/(2*D.rho*he);
 for(let i=0;i<n;i++){const q=md[i],w=TAU*q.f;let d,g=[0,0];kind[i]=q.k;f[i]=q.f;
  if(q.k===0){d=dShell(q.f);const amp=w*q.wt*Math.sqrt(sig(q.f,fc));
   g=mic.map(([ms,mt,mr])=>{const ang=q.n?(q.o?Math.sin:Math.cos)(q.n*(mt-q.ph)):1;
    if(lis===0)return amp*ang*Math.pow(mr/Rl(ms),q.n)*.5;if(lis===1)return amp*ang*Math.pow(.7,Math.min(q.n,30))/3;return w*q.wt*ang*Math.sin(q.m*Math.PI*ms);});}
  else if(q.k===1){d=Math.PI*q.f*D.eta+RHO0*C0*sig(q.f,fcp)/(2*D.rho*hp);const pp=pos(q.s,q.th,q.R);
   g=micP.map((mp,c)=>{const r=Math.max(dist(pp,mp),.05*H);let a=w*q.wt*Math.sqrt(sig(q.f,fcp))*H/r;
    if(lis===1){const cth=Math.cos(q.th-mic[c][1]);a*=cth>=0?.4+.6*cth:.4/Math.sqrt(1+Math.pow(q.f*-cth*TAU*Rx/C0,2));}
    if(lis===2)a=w*q.wt*Math.exp(-Math.pow(r/(2*q.a),2))*.8+a*.05;return a;});}
  else if(q.k===2){d=dc*(q.f>2000?RT/RTh:1);const wl=lis===0?1:lis===1?.12:.35;
   g=mic.map(([ms,mt,mr])=>{const ang=q.n?(q.o?Math.sin:Math.cos)(q.n*mt):1,rad=q.jp?Jn(q.n,q.jp*Math.min(1,mr/Rx))/Jn(q.n,q.jp):1;return wl*(q.psi?at(q.psi,ms):1)*ang*(lis===0?rad:1);});}
  else{d=Math.PI*q.f*POP.eta+6;const kr=w/C0*K.r,sg=kr*kr/(1+kr*kr);g=[w*Math.sqrt(sg),w*Math.sqrt(sg)];}
  const R=Math.exp(-d/SR),th=w/SR;b1[i]=2*R*Math.cos(th);b2[i]=-R*R;gi[i]=R*Math.sin(th)/(w*SR);gL[i]=g[0];gR[i]=g[1];q.d=d;}
 return{md,n,f,b1,b2,gi,gL,gR,kind,H,Rx,Rb,h:he,fc,fcp,cL,w0,RT,RTh,fS,V:hn.V,S:hn.S,meff,k0,J0,T0,sm,K,D,Z,lis,mic,micP,pos,dist,
  ring:w0/TAU,low:Math.min(...Array.from(f)),panelLo:Math.min(...md.filter(q=>q.k===1).map(q=>q.f)),panelHi:Math.max(...md.filter(q=>q.k===1).map(q=>q.f)),
  cav1:hn.modes[0]?hn.modes[0].f:0,stick1:md.filter(q=>q.k===3).map(q=>q.f)[0]||0,horn:hn};}
// Excitation weights of every mode for a hit at (s,th): shape value / modal mass. ridge in [0,1] (1 = on a ridge)
function weights(W,s,th,withStick){const w=new Float64Array(W.n),H=W.H,R=Rm(H,s);
 for(let i=0;i<W.n;i++){const q=W.md[i];
  if(q.k===0)w[i]=Math.sin(q.m*Math.PI*s)*(q.n?(q.o?Math.sin:Math.cos)(q.n*(th-q.ph)):1)/q.M;
  else if(q.k===1){const ds=(s-q.s)*H,dth=((th-q.th+Math.PI)%TAU+TAU)%TAU-Math.PI,dl=dth*(R+q.R)/2,r2=(ds*ds+dl*dl)/(q.a*q.a);w[i]=r2<9?q.wt*Math.exp(-r2)/q.M:0;}
  else if(q.k===2)w[i]=(q.psi?at(q.psi,s):1)*(q.n?(q.o?Math.sin:Math.cos)(q.n*th):1);
  else w[i]=withStick?2/q.M:0;}
 return w;}
return{TAU,PM,NU,C0,F,Om,P,M,SIZES,STICKS,DRY,POP,LISTEN,PACE,Rm,wallR,thick,erbn,sig,Jn,horn,at,build,weights};
}
if(typeof module!=='undefined')module.exports=PHYS;
