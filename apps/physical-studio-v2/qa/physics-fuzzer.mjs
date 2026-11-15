import fs from 'node:fs';

const seeds=Number(process.env.QA_FUZZ_SEEDS||250);
const steps=Number(process.env.QA_FUZZ_STEPS||2400);
const failures=[];
function rng(seed){let x=seed|0;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return((x>>>0)/4294967296)}}
function finiteBody(b){return Number.isFinite(b.x)&&Number.isFinite(b.v)&&Number.isFinite(b.m)&&Number.isFinite(b.d)}

for(let seed=1;seed<=seeds;seed++){
  const r=rng(seed);const n=4+Math.floor(r()*24);
  const bodies=Array.from({length:n},(_,i)=>({x:(r()-.5)*2,v:(r()-.5)*.2,m:.05+r()*7.95,d:r()*1.5,anchor:i===0||r()<.12,rest:0}));
  bodies.forEach(b=>b.rest=b.x);
  const springs=[];
  for(let i=0;i<n-1;i++)springs.push({a:i,b:i+1,k:10+r()*1790,d:r()*20,rest:bodies[i+1].x-bodies[i].x});
  for(let i=0;i<n;i++)if(r()<.35){let j=Math.floor(r()*n);if(j!==i&&!springs.some(s=>(s.a===i&&s.b===j)||(s.a===j&&s.b===i)))springs.push({a:i,b:j,k:10+r()*1790,d:r()*20,rest:bodies[j].x-bodies[i].x})}
  const dt=1/180,substeps=3;let maxEnergy=0,failed=null;
  for(let step=0;step<steps&&!failed;step++){
    if(step%137===0){const i=1+Math.floor(r()*(n-1));if(!bodies[i].anchor)bodies[i].v+=(r()-.5)*8}
    for(let sub=0;sub<substeps&&!failed;sub++){
      const f=new Float64Array(n);
      for(const s of springs){
        if(!bodies[s.a]||!bodies[s.b]){failed={code:'QA-PHY-003',step,why:'invalid spring index'};break}
        const a=bodies[s.a],b=bodies[s.b],rel=(b.x-a.x)-s.rest,rv=b.v-a.v,force=s.k*rel+s.d*rv;
        f[s.a]+=force;f[s.b]-=force;
      }
      if(failed)break;
      for(let i=0;i<n;i++){
        const b=bodies[i];if(b.anchor){b.v=0;b.x=b.rest;continue}
        b.v+=f[i]/Math.max(.05,b.m)*dt;b.v*=Math.exp(-b.d*dt);b.x+=b.v*dt;
        if(!finiteBody(b)){failed={code:'QA-PHY-001',step,index:i,why:'non-finite body'};break}
        if(Math.abs(b.x)>1e6||Math.abs(b.v)>1e8){failed={code:'QA-PHY-004',step,index:i,why:'runaway state'};break}
      }
    }
    let e=0;for(const b of bodies)if(!b.anchor)e+=.5*b.m*b.v*b.v;for(const s of springs){const q=(bodies[s.b].x-bodies[s.a].x)-s.rest;e+=.5*s.k*q*q}
    if(!Number.isFinite(e)){failed={code:'QA-PHY-001',step,why:'non-finite energy'};break}
    maxEnergy=Math.max(maxEnergy,e);
    if(e>1e12){failed={code:'QA-PHY-004',step,why:'energy runaway',energy:e};break}
  }
  if(failed)failures.push({seed,n,springs:springs.length,maxEnergy,...failed});
}

fs.mkdirSync('qa-results',{recursive:true});
const report={generatedAt:new Date().toISOString(),seeds,steps,failures,status:failures.length?'FAIL':'PASS'};
fs.writeFileSync('qa-results/physics-fuzz.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({status:report.status,seeds,steps,failures:failures.slice(0,5)},null,2));
if(failures.length)process.exitCode=1;
