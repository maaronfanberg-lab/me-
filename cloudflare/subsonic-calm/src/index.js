const APP_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<meta name="theme-color" content="#07090f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Subsonic Calm">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<title>Subsonic Calm</title>
<style>
:root{--bg:#07090f;--panel:#101622;--line:#28344a;--text:#e8edf7;--dim:#8d99ad;--accent:#8d7cff;--accent2:#4bd8c5;--warn:#e3bd68;--bad:#ff8b98}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;min-height:100%}
body{padding:max(18px,env(safe-area-inset-top)) 14px max(30px,env(safe-area-inset-bottom));max-width:760px;margin:auto;overscroll-behavior:none}
h1{font:760 28px/1.05 system-ui,sans-serif;margin:0 0 4px;letter-spacing:.045em}
.sub{font-size:11px;color:var(--dim);line-height:1.45;margin-bottom:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:15px;margin:10px 0}
.hero{text-align:center;padding:18px 15px}
.big{font:780 58px/.95 system-ui,sans-serif;letter-spacing:-.05em}
.big small{font-size:16px;color:var(--dim);letter-spacing:0}
.mode{margin-top:7px;color:var(--accent2);font-size:11px;letter-spacing:.12em;text-transform:uppercase}
button{font:650 15px system-ui,sans-serif;color:var(--text);background:#141c2a;border:1px solid var(--line);border-radius:13px;min-height:48px;padding:11px 10px}
button:active{transform:translateY(1px)}
button.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
#power{width:100%;margin-top:14px;min-height:62px;font-size:18px;letter-spacing:.08em;background:#554ad2;border-color:#948aff;color:#fff}
#power.on{background:#176057;border-color:var(--accent2)}
.modes{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.modes button span{display:block;color:var(--dim);font-size:11px;margin-top:2px}
.status{font-size:11px;color:var(--dim);text-align:center;margin-top:10px;min-height:18px}
.status.good{color:var(--accent2)} .status.bad{color:var(--bad)}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.metric{background:#0b1018;border:1px solid var(--line);border-radius:12px;padding:10px}
.metric span{display:block;color:var(--dim);font-size:9px;text-transform:uppercase;letter-spacing:.09em}
.metric b{display:block;font:650 16px system-ui,sans-serif;margin-top:3px}
.ctrl{margin:13px 0 3px}
.ctrl label{display:flex;justify-content:space-between;gap:12px;color:var(--dim);font-size:10px;text-transform:uppercase;letter-spacing:.09em;margin-bottom:4px}
.ctrl label b{color:var(--text);font-size:12px;letter-spacing:0;text-transform:none}
input[type=range]{width:100%;accent-color:var(--accent);height:30px}
.row{display:flex;gap:8px}.row button{flex:1}
.note{font-size:10.5px;line-height:1.55;color:var(--dim)}
.warn{border-left:3px solid var(--warn);padding-left:10px}
canvas{width:100%;height:100px;display:block;background:#080c13;border-radius:12px}
@media(max-width:460px){.big{font-size:50px}.modes{grid-template-columns:1fr}.metrics{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<h1>SUBSONIC CALM</h1>
<div class="sub">Deep-bass instrument · rebuilt signal path · no compressor · full manual control</div>
<div class="card hero">
  <div class="big"><span id="freqRead">32.0</span><small> Hz</small></div>
  <div class="mode" id="modeRead">Velvet</div>
  <button id="power" type="button">START BASS</button>
  <div class="status" id="status" aria-live="polite">Ready — tap START BASS</div>
</div>
<div class="card">
  <div class="modes">
    <button class="preset active" type="button" data-mode="velvet">VELVET<span>32 Hz · smooth</span></button>
    <button class="preset" type="button" data-mode="abyss">ABYSS<span>26 Hz · deepest</span></button>
    <button class="preset" type="button" data-mode="warm">WARM BODY<span>38 Hz · tactile</span></button>
    <button class="preset" type="button" data-mode="journey">JOURNEY<span>30 s per stage</span></button>
  </div>
</div>
<div class="card">
  <div class="metrics">
    <div class="metric"><span>Context</span><b id="metricCtx">off</b></div>
    <div class="metric"><span>Peak ceiling</span><b id="metricPeak">11.9%</b></div>
    <div class="metric"><span>Signal path</span><b>clean</b></div>
  </div>
  <div class="ctrl"><label for="freq">Fundamental <b id="freqVal">32.0 Hz</b></label><input id="freq" type="range" min="20" max="48" step="0.1" value="32"></div>
  <div class="ctrl"><label for="h2">2nd harmonic <b id="h2Val">2.4%</b></label><input id="h2" type="range" min="0" max="8" step="0.1" value="2.4"></div>
  <div class="ctrl"><label for="h3">3rd harmonic <b id="h3Val">0.6%</b></label><input id="h3" type="range" min="0" max="3" step="0.1" value="0.6"></div>
  <div class="ctrl"><label for="breath">Breathing depth <b id="breathVal">2.5%</b></label><input id="breath" type="range" min="0" max="8" step="0.1" value="2.5"></div>
  <div class="ctrl"><label for="period">Breathing period <b id="periodVal">15.5 s</b></label><input id="period" type="range" min="8" max="40" step="0.5" value="15.5"></div>
  <div class="ctrl"><label for="drift">Pitch drift <b id="driftVal">±0.16 Hz</b></label><input id="drift" type="range" min="0" max="0.30" step="0.01" value="0.16"></div>
  <div class="ctrl"><label for="output">Digital output <b id="outputVal">12%</b></label><input id="output" type="range" min="0" max="22" step="1" value="12"></div>
  <div class="row"><button id="reset" type="button">RESET MODE</button><button id="motionOff" type="button">MOTION OFF</button></div>
  <p class="note">Touching a manual control exits Journey so it cannot fight you. Settings are remembered on this device.</p>
</div>
<div class="card"><canvas id="scope" width="700" height="100"></canvas><p class="note">The three oscillators are normalized before the master output, so changing harmonics does not create a hidden level jump.</p></div>
<div class="card note warn"><b>Subwoofer caution:</b> digital output is not SPL. Start with the physical subwoofer gain low. Stop if you hear knocking, port chuffing, or obvious distortion. 26 Hz can require much more cone travel than 38 Hz.</div>
<script>
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const BASE={
    velvet:{name:'Velvet',f:32,h2:2.4,h3:.6,breath:2.5,period:15.5,drift:.16,output:12},
    abyss:{name:'Abyss',f:26,h2:1.3,h3:.2,breath:1.8,period:19,drift:.10,output:10},
    warm:{name:'Warm Body',f:38,h2:5.2,h3:1.2,breath:3.3,period:13.5,drift:.18,output:12}
  };
  const STAGES=['velvet','abyss','warm'],ids=['freq','h2','h3','breath','period','drift','output'];
  let ctx=null,master=null,toneBus=null,breathGain=null,analyser=null,o1=null,o2=null,o3=null,g1=null,g2=null,g3=null,lfo=null,lfoDepth=null;
  let running=false,mode='velvet',edited=false,journeyIndex=0,journeyTimer=0,wanderTimer=0,wanderPhase=0;
  function values(){return{f:+$('freq').value,h2:+$('h2').value/100,h3:+$('h3').value/100,breath:+$('breath').value/100,period:+$('period').value,drift:+$('drift').value,output:+$('output').value/100};}
  function status(text,cls=''){const s=$('status');s.textContent=text;s.className='status '+cls;}
  function hold(param,t){if(param.cancelAndHoldAtTime)param.cancelAndHoldAtTime(t);else{const v=param.value;param.cancelScheduledValues(t);param.setValueAtTime(v,t);}}
  function setTarget(param,value,t,tc){hold(param,t);param.setTargetAtTime(value,t,tc);}
  function normalize(v){return .92/(1+v.h2+v.h3);}
  function peakCeiling(v){return 100*.92*v.output*(1+v.breath);}
  function save(){try{localStorage.setItem('subsonic-calm-v2',JSON.stringify({mode,edited,vals:Object.fromEntries(ids.map(id=>[id,$(id).value]))}));}catch(_){}}
  function load(){try{const s=JSON.parse(localStorage.getItem('subsonic-calm-v2')||'null');if(!s||!s.vals)return false;for(const id of ids)if(s.vals[id]!=null)$(id).value=s.vals[id];mode=BASE[s.mode]?s.mode:'velvet';edited=!!s.edited;return true;}catch(_){return false;}}
  function setControls(p){$('freq').value=p.f;$('h2').value=p.h2;$('h3').value=p.h3;$('breath').value=p.breath;$('period').value=p.period;$('drift').value=p.drift;$('output').value=p.output;}
  function activeName(){if(mode==='journey')return'Journey · '+BASE[STAGES[journeyIndex]].name;return BASE[mode].name+(edited?' · edited':'');}
  function updateUI(){const v=values();$('freqRead').textContent=v.f.toFixed(1);$('freqVal').textContent=v.f.toFixed(1)+' Hz';$('h2Val').textContent=(v.h2*100).toFixed(1)+'%';$('h3Val').textContent=(v.h3*100).toFixed(1)+'%';$('breathVal').textContent=(v.breath*100).toFixed(1)+'%';$('periodVal').textContent=v.period.toFixed(1)+' s';$('driftVal').textContent='±'+v.drift.toFixed(2)+' Hz';$('outputVal').textContent=Math.round(v.output*100)+'%';$('metricPeak').textContent=peakCeiling(v).toFixed(1)+'%';$('modeRead').textContent=activeName();document.querySelectorAll('.preset').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));}
  async function ensureAudioFromTap(){const AC=window.AudioContext||window.webkitAudioContext;if(!AC)throw new Error('Web Audio is unavailable in this browser');if(!ctx){ctx=new AC({latencyHint:'interactive'});master=ctx.createGain();master.gain.value=0;toneBus=ctx.createGain();toneBus.gain.value=.92;breathGain=ctx.createGain();breathGain.gain.value=1;analyser=ctx.createAnalyser();analyser.fftSize=2048;o1=ctx.createOscillator();o2=ctx.createOscillator();o3=ctx.createOscillator();o1.type=o2.type=o3.type='sine';g1=ctx.createGain();g2=ctx.createGain();g3=ctx.createGain();o1.connect(g1);o2.connect(g2);o3.connect(g3);g1.connect(toneBus);g2.connect(toneBus);g3.connect(toneBus);toneBus.connect(breathGain);breathGain.connect(master);master.connect(analyser);analyser.connect(ctx.destination);lfo=ctx.createOscillator();lfo.type='sine';lfoDepth=ctx.createGain();lfoDepth.gain.value=0;lfo.connect(lfoDepth);lfoDepth.connect(breathGain.gain);o1.start();o2.start();o3.start();lfo.start();}if(ctx.state!=='running')await ctx.resume();$('metricCtx').textContent=ctx.state;return ctx.state==='running';}
  function applyAudio(immediate=false){updateUI();save();if(!ctx)return;const v=values(),t=ctx.currentTime,tc=immediate?.008:.045;setTarget(o1.frequency,v.f,t,tc);setTarget(o2.frequency,v.f*2,t,tc);setTarget(o3.frequency,v.f*3,t,tc);setTarget(g1.gain,1,t,.025);setTarget(g2.gain,v.h2,t,.025);setTarget(g3.gain,v.h3,t,.025);setTarget(toneBus.gain,normalize(v),t,.025);setTarget(lfo.frequency,1/Math.max(1,v.period),t,.08);setTarget(lfoDepth.gain,v.breath,t,.08);if(running)setTarget(master.gain,v.output,t,.035);}
  function beginWander(){clearInterval(wanderTimer);wanderPhase=0;wanderTimer=setInterval(()=>{if(!running||!ctx)return;const v=values();wanderPhase+=.065;const hz=v.drift*(.68*Math.sin(wanderPhase)+.32*Math.sin(wanderPhase*.381+1.7));const cents=1200*Math.log2((v.f+hz)/v.f),t=ctx.currentTime;setTarget(o1.detune,cents,t,.35);setTarget(o2.detune,cents,t,.35);setTarget(o3.detune,cents,t,.35);},400);}
  function useStage(name,isJourney=false){const p=BASE[name];setControls(p);if(isJourney){mode='journey';edited=false;}else{mode=name;edited=false;}applyAudio(true);}
  function beginJourney(){clearInterval(journeyTimer);if(mode!=='journey')return;journeyIndex=0;useStage(STAGES[0],true);journeyTimer=setInterval(()=>{if(!running||mode!=='journey')return;journeyIndex=(journeyIndex+1)%STAGES.length;useStage(STAGES[journeyIndex],true);beginWander();},30000);}
  async function start(){status('Starting audio…');const ok=await ensureAudioFromTap();if(!ok)throw new Error('Audio context did not enter running state');running=true;applyAudio(true);const t=ctx.currentTime,v=values();hold(master.gain,t);master.gain.setValueAtTime(0,t);master.gain.linearRampToValueAtTime(v.output,t+.010);beginWander();if(mode==='journey')beginJourney();$('power').textContent='STOP BASS';$('power').classList.add('on');status('AUDIO ON · context '+ctx.state,'good');$('metricCtx').textContent=ctx.state;}
  function stop(){if(!ctx)return;running=false;clearInterval(wanderTimer);clearInterval(journeyTimer);const t=ctx.currentTime;hold(master.gain,t);master.gain.linearRampToValueAtTime(0,t+.025);$('power').textContent='START BASS';$('power').classList.remove('on');status('Stopped · tap START BASS');$('metricCtx').textContent=ctx.state;}
  $('power').addEventListener('click',async()=>{try{running?stop():await start();}catch(err){console.error(err);status('AUDIO ERROR · '+err.message,'bad');$('metricCtx').textContent=ctx?ctx.state:'error';}});
  document.querySelectorAll('.preset').forEach(btn=>btn.addEventListener('click',()=>{clearInterval(journeyTimer);const m=btn.dataset.mode;if(m==='journey'){mode='journey';edited=false;journeyIndex=0;useStage('velvet',true);if(running)beginJourney();}else useStage(m,false);if(running)beginWander();}));
  ids.forEach(id=>$(id).addEventListener('input',()=>{if(mode==='journey'){mode=STAGES[journeyIndex];clearInterval(journeyTimer);}edited=true;applyAudio(false);if(running)beginWander();}));
  $('reset').addEventListener('click',()=>{clearInterval(journeyTimer);if(mode==='journey')mode=STAGES[journeyIndex];useStage(mode,false);if(running)beginWander();});
  $('motionOff').addEventListener('click',()=>{if(mode==='journey'){mode=STAGES[journeyIndex];clearInterval(journeyTimer);}$('breath').value=0;$('drift').value=0;edited=true;applyAudio(false);if(running)beginWander();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&running)stop();});
  const c=$('scope'),cg=c.getContext('2d'),wave=new Uint8Array(2048);function draw(){requestAnimationFrame(draw);const w=c.width,h=c.height;cg.clearRect(0,0,w,h);cg.strokeStyle='#28344a';cg.lineWidth=1;cg.beginPath();cg.moveTo(0,h/2);cg.lineTo(w,h/2);cg.stroke();if(!analyser)return;analyser.getByteTimeDomainData(wave);cg.strokeStyle='#8d7cff';cg.lineWidth=2;cg.beginPath();for(let i=0;i<wave.length;i++){const x=i/(wave.length-1)*w,y=wave[i]/255*h;i?cg.lineTo(x,y):cg.moveTo(x,y);}cg.stroke();}
  if(!load())setControls(BASE.velvet);updateUI();draw();if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
})();
</script>
</body>
</html>`;

const MANIFEST=JSON.stringify({name:'Subsonic Calm',short_name:'Subsonic',start_url:'/',display:'standalone',background_color:'#07090f',theme_color:'#07090f',description:'Deep-bass subwoofer instrument with full manual control.',icons:[{src:'/icon.svg',sizes:'any',type:'image/svg+xml',purpose:'any maskable'}]});
const SW=`const CACHE='subsonic-calm-v2';self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/','/manifest.webmanifest','/icon.svg'])));self.skipWaiting();});self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();e.waitUntil(caches.open(CACHE).then(c=>c.put(e.request,copy)));return r;}).catch(()=>caches.match(e.request)));});`;
const ICON=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="108" fill="#07090f"/><circle cx="256" cy="256" r="155" fill="#101622" stroke="#8d7cff" stroke-width="18"/><circle cx="256" cy="256" r="88" fill="none" stroke="#4bd8c5" stroke-width="18"/><circle cx="256" cy="256" r="24" fill="#8d7cff"/></svg>`;
function response(body,contentType,cache='public, max-age=300'){return new Response(body,{headers:{'content-type':contentType,'cache-control':cache,'x-content-type-options':'nosniff','referrer-policy':'no-referrer','permissions-policy':'camera=(), microphone=(), geolocation=()'}});}
export default{async fetch(request){const url=new URL(request.url);if(request.method!=='GET'&&request.method!=='HEAD')return new Response('Method Not Allowed',{status:405,headers:{allow:'GET, HEAD'}});if(url.pathname==='/health')return response(JSON.stringify({ok:true,app:'subsonic-calm',version:'2',signal_path:'normalized-clean'}),'application/json; charset=utf-8','no-store');if(url.pathname==='/manifest.webmanifest')return response(MANIFEST,'application/manifest+json; charset=utf-8','public, max-age=3600');if(url.pathname==='/sw.js')return response(SW,'text/javascript; charset=utf-8','no-cache');if(url.pathname==='/icon.svg')return response(ICON,'image/svg+xml; charset=utf-8','public, max-age=86400');if(url.pathname==='/'||url.pathname==='/index.html')return response(APP_HTML,'text/html; charset=utf-8','no-cache');return new Response('Not Found',{status:404});}};
