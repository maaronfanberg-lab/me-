import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const resultsPath=path.join(root,'qa-results','playwright-results.json');
const outPath=path.join(root,'qa-results','release-gate.json');
fs.mkdirSync(path.dirname(outPath),{recursive:true});

const report={
  schema:1,
  generatedAt:new Date().toISOString(),
  commit:process.env.GITHUB_SHA||process.env.COMMIT_SHA||'unknown',
  status:'RED',
  suites:{browser:'UNKNOWN',selfTest:'MANUAL_REQUIRED',visualReview:'MANUAL_REQUIRED',targetIPhone:'UNVERIFIED'},
  unresolvedCodes:[],
  notes:[]
};

if(!fs.existsSync(resultsPath)){
  report.unresolvedCodes.push('QA-REL-001');
  report.notes.push('Playwright result file is missing. Automated browser gate was not run.');
}else{
  const r=JSON.parse(fs.readFileSync(resultsPath,'utf8'));
  const failures=[];
  const walk=s=>{for(const spec of s.specs||[]){for(const t of spec.tests||[]){for(const res of t.results||[]){if(res.status==='failed'||res.status==='timedOut')failures.push({title:spec.title,error:res.error?.message||''})}}}for(const child of s.suites||[])walk(child)};
  for(const suite of r.suites||[])walk(suite);
  report.suites.browser=failures.length?'FAIL':'PASS';
  for(const f of failures){
    const m=f.error.match(/QA-[A-Z]+-\d{3}/g)||[];
    report.unresolvedCodes.push(...m);
    report.notes.push(`${f.title}: ${f.error.slice(0,300)}`);
  }
  if(failures.length&&!report.unresolvedCodes.length)report.unresolvedCodes.push('QA-REL-002');
}

report.unresolvedCodes=[...new Set(report.unresolvedCodes)];
report.status=report.suites.browser==='PASS'&&report.unresolvedCodes.length===0?'AMBER':'RED';
report.notes.push('AMBER means automated gate passed but simulator self-test, visual review, and real iPhone verification are still separate required gates.');
fs.writeFileSync(outPath,JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
if(report.suites.browser!=='PASS'||report.unresolvedCodes.length)process.exitCode=1;
