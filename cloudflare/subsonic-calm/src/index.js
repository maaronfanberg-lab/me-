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
<link rel="apple-touch-icon" href="/icon.svg">
<title>Subsonic Calm</title>
<style>
:root{--bg:#07090f;--panel:#101622;--line:#273249;--text:#e1e8f4;--dim:#8491a7;--accent:#8878ff;--accent2:#47d7c4;--warn:#e6bf66}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;min-height:100%}
body{padding:max(18px,env(safe-area-inset-top)) 14px max(30px,env(safe-area-inset-bottom));max-width:760px;margin:auto;overscroll-behavior:none}
h1{font:750 28px/1.05 system-ui,sans-serif;margin:0 0 4px;letter-spacing:.05em}.sub{font-size:11px;color:var(--dim);line-height:1.45;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:15px;margin:10px 0}.hero{text-align:center;padding:19px 15px}
.big{font:780 58px/.95 system-ui,sans-serif;letter-spacing:-.05em}.big small{font-size:16px;color:var(--dim);letter-spacing:0}.mode{margin-top:7px;color:var(--accent2);font-size:11px;letter-spacing:.12em;text-transform:uppercase}
button{font:650 15px system-ui,sans-serif;color:var(--text);background:#141c2a;border:1px solid var(--line);border-radius:13px;min-height:48px;padding:11px 10px}
button:active{transform:translateY(1px)}button.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
#power{width:100%;margin-top:14px;min-height:62px;font-size:18px;letter-spacing:.08em;background:#554ad2;border-color:#948aff;color:white}#power.on{background:#176057;border-color:var(--accent2)}
.modes{display:grid;grid-template-columns:1fr 1fr;gap:8px}.modes button span{display:block;color:var(--dim);font-size:11px;margin-top:2px}
label{display:flex;justify-content:space-between;gap:12px;color:var(--dim);font-size:10px;text-transform:uppercase;letter-spacing:.1em;margin:14px 0 7px}label b{color:var(--text)}
input[type=range]{width:100%;accent-color:var(--accent);height:32px}.status{font-size:11px;color:var(--dim);text-align:center;margin-top:10px;min-height:18px}.status.good{color:var(--accent2)}.status.bad{color:#ff8895}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px}.metric{background:#0b1018;border:1px solid var(--line);border-radius:12px;padding:10px}.metric span{display:block;color:var(--dim);font-size:9px;text-transform:uppercase;letter-spacing:.09em}.metric b{display:block;font:650 18px system-ui,sans-serif;margin-top:3px}
canvas{width:100%;height:100px;display:block;background:#080c13;border-radius:12px}.note{font-size:10.5px;line-height:1.55;color:var(--dim)}.warn{border-left:3px solid var(--warn);padding-left:10px}
@media(max-width:390px){.big{font-size:50px}.modes{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>SUBSONIC CALM</h1>
<div class="sub">Deep-bass instrument for a subwoofer · iPhone-first · instant tap start · Velvet / Abyss / Warm Body / Journey</div>

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
    <button class="preset" type="button" data-mode="journey">JOURNEY<span>moves through all 3</span></button>
  </div>
</div>

<div class="card">
  <div class="metrics">
    <div class="metric"><span>Mode</span><b id="metricMode">Velvet</b></div>
    <div class="metric"><span>Context</span><b id="metricCtx">off</b></div>
    <div class="metric"><span>Breathing</span><b id="metricBreath">2.5%</b></div>
    <div class="metric"><span>Pitch drift</span><b id="metricDrift">±0.16 Hz</b></div>
  </div>
  <label for="vol">Output <b id="volRead">14%</b></label>
  <input id="vol" type="range" min="0" max="100" step="1" value="14">
</div>

<div class="card">
  <canvas id="scope" width="700" height="100"></canvas>
  <p class="note">Live master-bus waveform. The fundamental dominates; the 2nd and 3rd harmonics stay deliberately faint so it feels large without turning buzzy.</p>
</div>

<div class="card note warn"><b>Subwoofer caution:</b> this app cannot measure real SPL or cone excursion. Start with the physical subwoofer gain low. If you hear knocking, port chuffing, or obvious distortion, stop or choose a higher-frequency mode. Abyss at 26 Hz is the most demanding.</div>

<script>
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const PRESETS = {
    velvet:{name:'Velvet',f:32,warm2:.024,warm3:.006,breath:.025,rate:1/15.5,drift:.16},
    abyss:{name:'Abyss',f:26,warm2:.013,warm3:.002,breath:.018,rate:1/19,drift:.10},
    warm:{name:'Warm Body',f:38,warm2:.052,warm3:.012,breath:.033,rate:1/13.5,drift:.18}
  };
  let ctx=null, master=null, comp=null, analyser=null;
  let o1=null,o2=null,o3=null,g1=null,g2=null,g3=null,lfo=null,lfoGain=null;
  let running=false, mode='velvet', wanderTimer=0, journeyTimer=0, journeyIndex=0, wanderPhase=0;

  function preset(){ return mode==='journey' ? PRESETS[['velvet','abyss','warm'][journeyIndex%3]] : PRESETS[mode]; }
  function targetGain(){ const v=+$('vol').value/100; return Math.min(.22,.006+v*.19); }
  function status(text, cls=''){ const s=$('status'); s.textContent=text; s.className='status '+cls; }

  async function ensureAudioFromTap(){
    const AC=window.AudioContext||window.webkitAudioContext;
    if(!AC) throw new Error('Web Audio is unavailable in this browser');
    if(!ctx){
      ctx=new AC({latencyHint:'interactive'});
      master=ctx.createGain(); master.gain.value=0;
      comp=ctx.createDynamicsCompressor(); comp.threshold.value=-22; comp.knee.value=8; comp.ratio.value=14; comp.attack.value=.008; comp.release.value=.30;
      analyser=ctx.createAnalyser(); analyser.fftSize=2048;
      o1=ctx.createOscillator();o2=ctx.createOscillator();o3=ctx.createOscillator();o1.type=o2.type=o3.type='sine';
      g1=ctx.createGain();g2=ctx.createGain();g3=ctx.createGain();
      o1.connect(g1);o2.connect(g2);o3.connect(g3);g1.connect(comp);g2.connect(comp);g3.connect(comp);
      lfo=ctx.createOscillator();lfo.type='sine';lfoGain=ctx.createGain();lfo.connect(lfoGain);lfoGain.connect(master.gain);
      comp.connect(master);master.connect(analyser);analyser.connect(ctx.destination);
      o1.start();o2.start();o3.start();lfo.start();
    }
    if(ctx.state!=='running') await ctx.resume();
    $('metricCtx').textContent=ctx.state;
    return ctx.state==='running';
  }

  function applyPreset(immediate=false){
    if(!ctx) { updateLabels(); return; }
    const p=preset(), t=ctx.currentTime;
    const tc=immediate?.008:.05;
    o1.frequency.setTargetAtTime(p.f,t,tc);o2.frequency.setTargetAtTime(p.f*2,t,tc);o3.frequency.setTargetAtTime(p.f*3,t,tc);
    o1.detune.setTargetAtTime(0,t,tc);o2.detune.setTargetAtTime(0,t,tc);o3.detune.setTargetAtTime(0,t,tc);
    g1.gain.setTargetAtTime(1,t,.03);g2.gain.setTargetAtTime(p.warm2,t,.03);g3.gain.setTargetAtTime(p.warm3,t,.03);
    lfo.frequency.setTargetAtTime(p.rate,t,.08);lfoGain.gain.setTargetAtTime(targetGain()*p.breath*.45,t,.08);
    if(running) master.gain.setTargetAtTime(targetGain(),t,.04);
    updateLabels();
  }

  function beginWander(){
    clearInterval(wanderTimer); wanderPhase=0;
    wanderTimer=setInterval(()=>{
      if(!running||!ctx) return;
      const p=preset(); wanderPhase+=.065;
      const hz=p.drift*(.68*Math.sin(wanderPhase)+.32*Math.sin(wanderPhase*.381+1.7));
      const cents=1200*Math.log2((p.f+hz)/p.f);
      const t=ctx.currentTime;
      o1.detune.setTargetAtTime(cents,t,.35);o2.detune.setTargetAtTime(cents,t,.35);o3.detune.setTargetAtTime(cents,t,.35);
    },400);
  }

  function beginJourney(){
    clearInterval(journeyTimer);
    if(mode!=='journey') return;
    journeyIndex=0; applyPreset(true);
    journeyTimer=setInterval(()=>{ if(!running||mode!=='journey') return; journeyIndex=(journeyIndex+1)%3; applyPreset(false); },30000);
  }

  async function start(){
    status('Starting audio…');
    const ok=await ensureAudioFromTap();
    if(!ok) throw new Error('Audio context did not enter running state');
    running=true;
    const t=ctx.currentTime, target=targetGain();
    master.gain.cancelScheduledValues(t);master.gain.setValueAtTime(0,t);master.gain.linearRampToValueAtTime(target,t+.010);
    applyPreset(true); beginWander(); beginJourney();
    $('power').textContent='STOP BASS';$('power').classList.add('on');
    status('AUDIO ON · context '+ctx.state,'good'); $('metricCtx').textContent=ctx.state;
  }

  function stop(){
    if(!ctx) return;
    running=false;clearInterval(wanderTimer);clearInterval(journeyTimer);
    const t=ctx.currentTime;master.gain.cancelScheduledValues(t);master.gain.setValueAtTime(master.gain.value,t);master.gain.linearRampToValueAtTime(0,t+.025);
    $('power').textContent='START BASS';$('power').classList.remove('on');status('Stopped · tap START BASS');
  }

  function updateLabels(){
    const p=preset(); $('freqRead').textContent=p.f.toFixed(1); $('modeRead').textContent=mode==='journey'?'Journey · '+p.name:p.name;
    $('metricMode').textContent=mode==='journey'?'Journey':p.name; $('metricBreath').textContent=(p.breath*100).toFixed(1)+'%'; $('metricDrift').textContent='±'+p.drift.toFixed(2)+' Hz';
    $('volRead').textContent=$('vol').value+'%';
  }

  $('power').addEventListener('click',async()=>{ try{ running?stop():await start(); }catch(err){ console.error(err); status('AUDIO ERROR · '+err.message,'bad'); $('metricCtx').textContent=ctx?ctx.state:'error'; } });
  document.querySelectorAll('.preset').forEach(btn=>btn.addEventListener('click',()=>{ mode=btn.dataset.mode; document.querySelectorAll('.preset').forEach(b=>b.classList.toggle('active',b===btn)); if(mode==='journey'){journeyIndex=0;beginJourney();}else clearInterval(journeyTimer); applyPreset(true); if(running) beginWander(); }));
  $('vol').addEventListener('input',()=>{ updateLabels(); if(ctx&&running){const t=ctx.currentTime;master.gain.setTargetAtTime(targetGain(),t,.04);lfoGain.gain.setTargetAtTime(targetGain()*preset().breath*.45,t,.08);} });
  document.addEventListener('visibilitychange',()=>{ if(document.hidden&&running) stop(); });

  const c=$('scope'), cg=c.getContext('2d'), wave=new Uint8Array(2048);
  function draw(){ requestAnimationFrame(draw); const w=c.width,h=c.height; cg.clearRect(0,0,w,h); cg.strokeStyle='#273249';cg.lineWidth=1;cg.beginPath();cg.moveTo(0,h/2);cg.lineTo(w,h/2);cg.stroke(); if(!analyser)return; analyser.getByteTimeDomainData(wave);cg.strokeStyle='#8878ff';cg.lineWidth=2;cg.beginPath();for(let i=0;i<wave.length;i++){const x=i/(wave.length-1)*w,y=wave[i]/255*h;i?cg.lineTo(x,y):cg.moveTo(x,y);}cg.stroke(); }
  if('serviceWorker' in navigator){ navigator.serviceWorker.register('/sw.js').catch(()=>{}); }
  updateLabels(); draw();
})();
</script>
</body>
</html>`;

const MANIFEST = JSON.stringify({
  name:'Subsonic Calm',
  short_name:'Subsonic',
  start_url:'/',
  display:'standalone',
  background_color:'#07090f',
  theme_color:'#07090f',
  description:'Deep-bass subwoofer instrument with Velvet, Abyss, Warm Body, and Journey modes.',
  icons:[{src:'/icon.svg',sizes:'any',type:'image/svg+xml',purpose:'any maskable'}]
});

const SW = `const CACHE='subsonic-calm-v1';self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/','/manifest.webmanifest','/icon.svg'])));self.skipWaiting();});self.addEventListener('activate',e=>{e.waitUntil(self.clients.claim());});self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return r;}).catch(()=>caches.match(e.request)));});`;

const ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="112" fill="#07090f"/><circle cx="256" cy="256" r="174" fill="none" stroke="#8878ff" stroke-width="34"/><circle cx="256" cy="256" r="98" fill="none" stroke="#47d7c4" stroke-width="26"/><circle cx="256" cy="256" r="24" fill="#e1e8f4"/></svg>`;

function response(body, contentType, cache='public, max-age=300'){
  return new Response(body,{headers:{'content-type':contentType,'cache-control':cache,'x-content-type-options':'nosniff','referrer-policy':'no-referrer','permissions-policy':'camera=(), microphone=(), geolocation=()'}});
}

export default {
  async fetch(request){
    const url=new URL(request.url);
    if(request.method!=='GET'&&request.method!=='HEAD') return new Response('Method Not Allowed',{status:405,headers:{allow:'GET, HEAD'}});
    if(url.pathname==='/health') return response(JSON.stringify({ok:true,app:'subsonic-calm',version:'1'}),'application/json; charset=utf-8','no-store');
    if(url.pathname==='/manifest.webmanifest') return response(MANIFEST,'application/manifest+json; charset=utf-8','public, max-age=3600');
    if(url.pathname==='/sw.js') return response(SW,'text/javascript; charset=utf-8','no-cache');
    if(url.pathname==='/icon.svg') return response(ICON,'image/svg+xml; charset=utf-8','public, max-age=86400');
    if(url.pathname==='/'||url.pathname==='/index.html') return response(APP_HTML,'text/html; charset=utf-8','no-store');
    return new Response('Not Found',{status:404});
  }
};
