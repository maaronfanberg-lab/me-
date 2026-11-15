import fs from 'node:fs';
import vm from 'node:vm';

const file='apps/live-earth-oracle.html';
const html=fs.readFileSync(file,'utf8');
const fail=m=>{console.error(`Fast Oracle validation failed: ${m}`);process.exit(1)};

for(const token of [
  '<title>The Fast Nonsense Predictor</title>',
  'FAST ORACLE · MK X',
  'RESTORED WIKIMEDIA SIX-FEATURE ENGINE',
  'function wikiOracleFactors()',
  "e.filter(v=>v.bot).length/n",
  "e.filter(v=>v.minor).length/n",
  "e.filter(v=>v.type==='new').length/n",
  "e.filter(v=>v.type==='log').length/n",
  'Math.log10(1+meanBytes)',
  'let seed=17',
  'FIXED_ROOTS=4',
  'for(let i=1n;i<=1000n;i++)',
  "setCard('wiki',rate+' / min','global Wikimedia activity · every event',factor,rate)",
  "quake:{name:'EARTHQUAKES'",
  "kp:{name:'GEOMAGNETIC KP'",
  "hn:{name:'HACKER NEWS'",
  "xrp:{name:'XRP'",
  "id=\"rCorr\"",
  'function renderCorrelations()',
  'setInterval(sampleSignals,5000)',
]) if(!html.includes(token)) fail(`missing: ${token}`);

if(html.includes('50% PHYSICAL WORLD + 50% HUMAN ACTIVITY')) fail('composite R returned');
if(html.includes('function bucketScores()')) fail('composite bucket engine returned');
if(html.includes('TAME_LIMIT')) fail('adaptive R ceiling returned');

const wikiCfg=html.match(/wiki:\{name:'WIKI EDITS'[^}]+\}/)?.[0]||'';
if(!wikiCfg.includes('rInput:true')) fail('Wikimedia not marked as R input');
for(const k of ['quake','kp','hn']){
  const m=html.match(new RegExp(`${k}:\\{[^}]+\\}`))?.[0]||'';
  if(m.includes('rInput:true')) fail(`${k} must remain comparison-only`);
}

const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(m=>m[1]).filter(Boolean);
if(!scripts.length) fail('no JavaScript');
for(const [i,code] of scripts.entries())try{new vm.Script(code,{filename:`${file}#${i+1}`})}catch(e){fail(`JavaScript parse error: ${e.message}`)}
console.log('Fast Oracle validation passed: restored six-feature Wikimedia R, fixed four roots, and current comparison set retained.');
