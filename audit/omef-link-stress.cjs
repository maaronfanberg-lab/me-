'use strict';
const fs=require('fs'),assert=require('assert');
const html=fs.readFileSync('apps/omef-exclusive.html','utf8');
const beginning=html.indexOf("const macros=[",html.indexOf("<script>(function(){'use strict';"));
const end=html.indexOf("let evolutionOn=true",beginning);
assert(beginning>0&&end>beginning,'Cannot identify production coupled mathematical engine');
assert(!html.includes('switch(info.mode)'),'Canned shape-switch code must not return');
const model=new Function("const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));const $=()=>null;"+html.slice(beginning,end)+
  ";return {twinStepper,twinCombine,twinDefaults,presetRaw,makeStepper,makeTwinEngine,allDefs};")();
const A=model.presetRaw('A'),B=model.presetRaw('B');
const cfg={global:.4,mix:.7,seed:1,interference:.16,projection:5,
 links:model.twinDefaults.map(x=>({...x})),focus:null};
const report={date:new Date().toISOString(),source:process.env.GITHUB_SHA,default:null,strong:null,zero:null,identity:null,sliders:[],originalParity:null};
assert(model.allDefs.length===61);
assert(Object.keys(A).filter(k=>Math.abs(A[k]-B[k])>1e-8).length>=8,'A/B genomes must differ');
const iso=model.makeTwinEngine(A,0),orig=model.makeStepper(A);
let parity=0;
for(let i=0;i<900;i++){const a=orig(),b=iso().xy;parity=Math.max(parity,Math.abs(a[0]-b[0]),Math.abs(a[1]-b[1]));}
report.originalParity=parity;
assert(parity<1e-10,'Independent Original solver parity failed');
function stress(c,n) {
 const next=model.twinStepper(A,B,c);
 let bad=0,drive=0,maxRadius=0,count=0,mx=0,my=0,mxx=0,myy=0,mxy=0,maxStep=0,px=0,py=0;
 for(let i=0;i<n+300;i++){
  const t=next(),q=model.twinCombine(t,c),x=q[0],y=q[1];
  if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(t.drive)){bad++;continue;}
  if(i<300)continue;
  count++;drive+=t.drive;
  const dx=x-mx,dy=y-my;
  mx+=dx/count;my+=dy/count;
  mxx+=dx*(x-mx);myy+=dy*(y-my);mxy+=dx*(y-my);
  maxRadius=Math.max(maxRadius,Math.hypot(x,y));
  if(count>1)maxStep=Math.max(maxStep,Math.hypot(x-px,y-py));
  px=x;py=y;
 }
 const tr=mxx+myy,disc=Math.sqrt((mxx-myy)**2+4*mxy*mxy);
 return {steps:n,actual:count,nonFinite:bad,meanTransmittedDrive:drive/n,
  minorMajorCovarianceRatio:(tr-disc)/Math.max(1e-12,tr+disc),maxRadius,maxStep};
}
console.log('Stress-testing one million default coupled steps...');
report.default=stress(cfg,1000000);
console.log('Stress-testing 400k maximum-coupling steps...');
report.strong=stress({...cfg,global:4,interference:3},400000);
console.log('Verifying no coupling when global gain is zero...');
report.zero=stress({...cfg,global:0},40000);
for(const x of [report.default,report.strong,report.zero]){
 assert(x.actual===x.steps&&x.nonFinite===0,'Nonfinite equation state or lost steps');
 assert(x.maxRadius<80,'Output escaped stable state-space bounds');
}
assert(report.default.minorMajorCovarianceRatio>.25,'Default folded structure collapsed into a line');
assert(report.strong.minorMajorCovarianceRatio>.15,'Strong-coupling phase space collapsed');
assert(report.zero.meanTransmittedDrive===0,'Global zero must eliminate all directed coupling');
function raster(c,n=14000,rawA=A,rawB=B) {
 const step=model.twinStepper(rawA,rawB,c),points=[];
 for(let i=0;i<n+350;i++){
  const p=model.twinCombine(step(),c);
  assert(p.every(Number.isFinite),'Nonfinite value in endpoint sweep');
  if(i>=350)points.push(p);
 }
 const xs=points.map(v=>v[0]).sort((a,b)=>a-b),ys=points.map(v=>v[1]).sort((a,b)=>a-b),
   loX=xs[Math.floor(.025*n)],hiX=xs[Math.floor(.975*n)],
   loY=ys[Math.floor(.025*n)],hiY=ys[Math.floor(.975*n)];
 const hist=new Float64Array(1024);let total=0;
 for(const [x,y] of points){
  const i=Math.floor(32*(x-loX)/(hiX-loX+1e-9)),j=Math.floor(32*(y-loY)/(hiY-loY+1e-9));
  if(i>=0&&i<32&&j>=0&&j<32){hist[32*j+i]++;total++;}
 }
 for(let i=0;i<hist.length;i++)hist[i]/=total;
 return hist;
}
const baseline=raster(cfg);
function difference(x,y){let shared=0;for(let i=0;i<x.length;i++)shared+=Math.min(x[i],y[i]);return Math.max(0,100*(1-shared));}
report.identity=difference(baseline,raster(cfg));
assert(report.identity<1e-8,'Unequal frame count or nondeterministic image comparison');
for(let i=0;i<8;i++){
 const right={...cfg,links:cfg.links.map(x=>({...x}))},delayed={...cfg,links:cfg.links.map(x=>({...x}))};
 right.links[i].strength=2;delayed.links[i].lag=144;
 const strengthRight=difference(baseline,raster(right)),delayRight=difference(baseline,raster(delayed));
 report.sliders.push({link:i,source:cfg.links[i].source,from:cfg.links[i].from,to:cfg.links[i].to,
  strengthRight,delayRight});
 assert(strengthRight>=48,'Coupling link '+i+' still too weak at far right: '+strengthRight);
 assert(delayRight>=42,'Delay link '+i+' still ineffective at 144 steps: '+delayRight);
}

const fullScalars=[
 ['global',4],['mix',0],['seed',3],['interference',3],['projection',0]
];
report.globalEndpoints=[];
for(const [id,target] of fullScalars){
 const config={...cfg,[id]:target,links:cfg.links.map(x=>({...x}))};
 const changed=difference(baseline,raster(config,14000));
 report.globalEndpoints.push({id,target,percentChanged:changed});
 assert(changed>=25,'Coupled global '+id+' endpoint is visually silent: '+changed);
}
// Every original A/B coefficient also has an independently measurable
// endpoint effect in the genuine coupled equations and state-space observer.
const genomeReference=raster(cfg,3600);
report.genomeEndpoints=[];
for(const def of model.allDefs){
 const [key,,lo,hi]=def;
 for(const side of ['A','B']){
  const baselineRaw=side==='A'?A:B;
  const endpoint=Math.abs(baselineRaw[key]-lo)>Math.abs(baselineRaw[key]-hi)?lo:hi;
  const altered={...baselineRaw,[key]:endpoint};
  const result=raster({...cfg,links:cfg.links.map(l=>({...l}))},3600,
    side==='A'?altered:A,side==='B'?altered:B);
  const percentChanged=difference(genomeReference,result);
  report.genomeEndpoints.push({side,key,endpoint,percentChanged});
  assert(percentChanged>=50,'Formula '+side+'.'+key+' endpoint too weak: '+percentChanged.toFixed(2)+'%');
 }
}
const sortedGenome=report.genomeEndpoints.map(x=>x.percentChanged).sort((a,b)=>a-b);
report.genomeSummary={count:sortedGenome.length,min:sortedGenome[0],
 median:sortedGenome[Math.floor(sortedGenome.length/2)],max:sortedGenome[sortedGenome.length-1]};
assert(report.genomeSummary.count===122,'Did not check every A/B formula slider');
console.log('GENOME_ENDPOINT_AUDIT '+JSON.stringify(report.genomeSummary));
fs.mkdirSync('audit-artifacts',{recursive:true});
fs.writeFileSync('audit-artifacts/coupled-solver-stress.json',JSON.stringify(report,null,2));
console.log('NUMERICAL_AUDIT '+JSON.stringify(report));
