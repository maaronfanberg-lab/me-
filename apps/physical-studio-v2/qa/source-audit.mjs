import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const required=['index.html','app.css','app.js','physics-worklet.js','simulator.html','simulator-selftest.html','dev-browser.html','qa/error-codes.json'];
const failures=[];
const fail=(code,msg,observed,expected)=>failures.push({code,msg,observed,expected});
for(const f of required){if(!fs.existsSync(path.join(root,f)))fail('QA-BOOT-010','Required project file missing',f,'file exists');}

const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
const worklet=fs.readFileSync(path.join(root,'physics-worklet.js'),'utf8');

if(!html.includes('three@0.180.0'))fail('QA-BOOT-011','Three.js version is not pinned',html.match(/three@[^/\"]+/)?.[0]||'none','three@0.180.0');
if(!app.includes("OrbitControls } from 'three/addons/controls/OrbitControls.js'"))fail('QA-CAM-010','OrbitControls import missing','missing','present in app.js');
if(!app.includes('THREE.TOUCH.ROTATE'))fail('QA-CAM-011','One-finger touch orbit mapping missing','missing','THREE.TOUCH.ROTATE');
if(!app.includes('THREE.TOUCH.DOLLY_PAN'))fail('QA-CAM-012','Two-finger dolly/pan mapping missing','missing','THREE.TOUCH.DOLLY_PAN');
if(!app.includes("audioWorklet.addModule('./physics-worklet.js"))fail('QA-AUD-010','App does not load expected physics worklet','missing','physics-worklet.js');
if(!worklet.includes("registerProcessor('physical-graph'"))fail('QA-AUD-011','Expected AudioWorklet processor registration missing','missing','physical-graph');
if(/resonator\.html|wake it up/i.test(html+app))fail('QA-REG-010','Forbidden legacy Resonator dependency/text leaked into new app','found','absent');
if(!html.includes('viewport-fit=cover'))fail('QA-UI-010','Mobile safe-area viewport configuration missing','missing','viewport-fit=cover');

const out={status:failures.length?'FAIL':'PASS',timestamp:new Date().toISOString(),failures};
fs.mkdirSync(path.join(root,'qa-results'),{recursive:true});
fs.writeFileSync(path.join(root,'qa-results/source-audit.json'),JSON.stringify(out,null,2));
console.log(JSON.stringify(out,null,2));
if(failures.length)process.exit(1);
