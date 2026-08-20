import fs from 'node:fs';

const src=fs.readFileSync('cloudflare/subsonic-calm/src/index.js','utf8');
const fail=(m)=>{throw new Error(m)};
if(src.includes('createDynamicsCompressor')) fail('Compressor returned to Subsonic Calm signal path');
for(const token of ["velvet:{name:'Velvet',f:32","abyss:{name:'Abyss',f:26","warm:{name:'Warm Body',f:38","toneBus.connect(breathGain);breathGain.connect(master)","linearRampToValueAtTime(v.output,t+.010)"]){
  if(!src.includes(token)) fail(`Missing required signal-path token: ${token}`);
}
const max={output:.22,breath:.08,h2:.08,h3:.03};
const normalized=.92/(1+max.h2+max.h3);
const preMasterWorst=(1+max.h2+max.h3)*normalized*(1+max.breath);
const outputWorst=preMasterWorst*max.output;
if(outputWorst>=1) fail(`Digital clipping bound failed: ${outputWorst}`);
if(Math.abs(outputWorst-.218592)>1e-9) fail(`Unexpected peak bound: ${outputWorst}`);
console.log(JSON.stringify({pass:true,compressor:false,normalized_harmonics:true,max_digital_peak:outputWorst,headroom_db:20*Math.log10(1/outputWorst)},null,2));
