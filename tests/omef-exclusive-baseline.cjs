// OMEF Exclusive historical baseline regression, 2026-11-24.
// Run: node tests/omef-exclusive-baseline.cjs
// The solver is extracted directly from the app, never reimplemented.
// This historical harness deliberately fails if the expected source layout changes.
// It measures spatial histogram total variation, not perceived beauty.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const l = fs.readFileSync(path.join(__dirname,'../apps/omef-exclusive.html'),'utf8').split('\n');
assert(l[92].startsWith('function makeStepper('));
assert(l[93].startsWith('function makeTwinEngine('));
assert(l[124].startsWith('function twinStepper('));
assert(l[152].startsWith('function twinProject('));
const code = [l[80],...l.slice(82,90),...l.slice(92,94),...l.slice(100,123),...l.slice(124,144),...l.slice(152,181)].join('\n');
const o = new Function(code+'\nreturn {allDefs,presetRaw,twinDefaults,twinStepper,twinCombine,makeStepper,makeTwinEngine};')();
const A=o.presetRaw(),B={...A};
const cfg={global:.45,seed:1,mix:.16,interference:.16,projection:5,links:o.twinDefaults};
let orig=o.makeStepper(A),twin=o.makeTwinEngine(A,0),parity=0;
for(let i=0;i<900;i++){let p=orig(),q=twin().xy;parity=Math.max(parity,Math.hypot(p[0]-q[0],p[1]-q[1]));}
assert.equal(parity,0);
let coupled=o.twinStepper(A,B,cfg),isolated=o.twinStepper(A,B,{...cfg,global:0}),drive=0,da=0,db=0;
for(let i=0;i<5000;i++){let p=coupled(),q=isolated();assert([...p.a,...p.b,...q.a,...q.b,p.drive].every(Number.isFinite));assert.equal(q.drive,0);drive+=p.drive;da+=Math.hypot(p.a[0]-q.a[0],p.a[1]-q.a[1]);db+=Math.hypot(p.b[0]-q.b[0],p.b[1]-q.b[1]);}
assert(drive>0&&da>0&&db>0);
function profile(A,B,cfg){
 let next=o.twinStepper(A,B,cfg),p=[];
 for(let i=0;i<1600;i++){let q=o.twinCombine(next(),cfg);if(!q.every(Number.isFinite))return null;if(i>=300)p.push(q);}
 let x=p.map(q=>q[0]),y=p.map(q=>q[1]),minX=Math.min(...x),maxX=Math.max(...x),minY=Math.min(...y),maxY=Math.max(...y),w=maxX-minX,h=maxY-minY;
 if(Math.min(w,h)<.01)return null;
 let hist=new Array(400).fill(0);
 for(let q of p){let x=Math.min(19,Math.floor(20*(q[0]-minX)/w)),y=Math.min(19,Math.floor(20*(q[1]-minY)/h));hist[y*20+x]++;}
 return {hist,occ:hist.filter(x=>x>0).length,dense:[...hist].sort((a,b)=>b-a).slice(0,48).reduce((a,b)=>a+b,0)/p.length,w,h};
}
function diff(a,b){return !a||!b?null:a.hist.reduce((v,x,i)=>v+Math.abs(x-b.hist[i]),0)/2600;}
const baseline=profile(A,B,cfg),rows=[];
assert(baseline);
for(const d of o.allDefs)for(const side of ['A','B']){
 let vals=[d[2],d[3]].map(v=>profile(side==='A'?{...A,[d[0]]:v}:A,side==='B'?{...B,[d[0]]:v}:B,cfg));
 rows.push({id:d[0],side,min:diff(baseline,vals[0]),max:diff(baseline,vals[1]),span:diff(...vals)});
}
assert.equal(rows.length,122);
assert(rows.every(r=>r.span!==null));
console.log(JSON.stringify({parity,meanDrive:drive/5000,meanDifferenceA:da/5000,meanDifferenceB:db/5000,endpointCount:244,weak:rows.filter(r=>r.span<.2).length,strong:rows.filter(r=>r.span>=.8).length,rightStrong:rows.filter(r=>r.max>=.8).length,rows},null,2));
// This baseline is expected to fail the desired high-leverage criterion.
// Never treat a passing finite-state test as a passing visual/UI test.
if(process.argv.includes('--require-high-leverage'))assert(rows.every(r=>r.max>=.8),'At least one right endpoint failed 80% histogram change');
