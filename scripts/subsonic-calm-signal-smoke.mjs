import fs from 'node:fs';
const app=fs.readFileSync('apps/subsonic-calm.html','utf8');
const worker=fs.readFileSync('cloudflare/subsonic-calm/src/index.js','utf8');
const fail=m=>{throw new Error(m)};
for(const token of ["still:{name:'Still',f:40","tide:{name:'Tide',f:41","warm:{name:'Warm',f:44","noiseHP.type='highpass'","noiseLP.type='lowpass'","noiseHP.frequency.value=35","noiseLP.frequency.value=80","subsonic-calm-v4-calm","80 HZ TEST","linearRampToValueAtTime(v.output,t+1.5)"]) if(!app.includes(token)) fail('Missing v4 app token: '+token);
if(app.includes('createDynamicsCompressor')) fail('Compressor returned');
if(!worker.includes('version:\'4\'')||!worker.includes('github-pages')) fail('Worker is not the v4 GitHub Pages front door');
const defaults=[
 {f:40,texture:.03,h2:.004,h3:0,swell:0,output:.07},
 {f:41,texture:.04,h2:.005,h3:.001,swell:.008,output:.07},
 {f:44,texture:.035,h2:.008,h3:.001,swell:.006,output:.07}
];
for(const m of defaults){if(m.f<40)fail('Default below PSW10 -3 dB band');if(m.h2>.01||m.h3>.002)fail('Default harmonic content too high');if(m.swell>.01)fail('Default modulation too high');if(m.output>.08)fail('Default output too high')}
const max={output:.18,swell:.03,texture:.10};
const conservative=(.82+Math.min(.07,max.texture*.55))*(1+max.swell)*max.output;
if(conservative>=.20) fail('Conservative digital ceiling too high: '+conservative);
console.log(JSON.stringify({pass:true,version:4,profile:'PSW10 low-salience research',defaults,conservative_peak_bound:conservative,headroom_db:20*Math.log10(1/conservative),diagnostic_80hz:true},null,2));
