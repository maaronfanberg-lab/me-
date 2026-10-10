import {createEngine} from './deep-earth-core.js';
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const AC=window.AudioContext||window.webkitAudioContext,OC=window.OfflineAudioContext||window.webkitOfflineAudioContext;
const defaults={master:.22,root:43.65,sub:.76,subHarm:.34,warmth:.25,subTone:110,subSwell:.10,lowcut:29,body:.49,bodyDrive:.46,bodyCutoff:740,pad:.48,padBrightness:1120,padDensity:.67,shimmer:.23,motion:.35,width:.76,orbit:.40,dwell:25,glide:2.7,reverb:.37,echo:.24,echoTime:.72,feedback:.32,air:.38};
const groups=[
 ['01 · EARTH FOUNDATION',true,[
 ['master','Output level',0,.5,.01,'','Raise amplifier volume gradually.'],['root','Fundamental note',40,65,.05,' Hz','One phase-stable mono sine source.'],['sub','Subwoofer weight',0,1,.01,'','Deep centered sustained bass.'],['subHarm','Second harmonic',0,1,.01,'','80–130 Hz body from exact octave overtone.'],['warmth','Third harmonic',0,1,.01,'','Gentle upper bass warmth.'],['subTone','Low-frequency crossover',75,145,1,' Hz','Fundamental lowpass roll-off.'],['subSwell','Low-frequency breathing',0,.8,.005,'','Very slow, gentle 27-second waves of volume.'],['lowcut','Sub protection',24,38,1,' Hz','Remove very low unwanted energy.']]],
 ['02 · HARMONIC HORIZON',true,[
 ['body','Guitar-like resonance',0,1,.01,'','Non-percussive harmonic edge.'],['bodyDrive','Saturation',0,1,.01,'','Richer upper-frequency density.'],['bodyCutoff','Growl brightness',220,2400,10,' Hz','Lowpass filter of the distorted body.'],['pad','Ambient layers',0,1,.01,'','Five sustained independent voices.'],['padBrightness','Pad brightness',400,3500,10,' Hz','Air and light around the drone.'],['padDensity','Harmonic density',0,1,.01,'','Amount of outer chord tones.'],['shimmer','Distant harmonics',0,1,.01,'','High, floating sustained partials.']]],
 ['03 · TIME AND SPACE',false,[
 ['motion','Ambient evolution',0,1,.01,'','Intensity of slow movement.'],['width','Stereo travel width',0,1,.01,'','Only the upper voices move.'],['orbit','Around-the-room depth',0,1,.01,'','Slow panorama/3D source positions.'],['dwell','Chord duration',8,70,1,' sec','Time between harmonic transitions.'],['glide','Transition glide',.3,9,.1,' sec','Time constant for chord transitions.']]],
 ['04 · EXPANSIVE DISTANCE',false,[
 ['reverb','Cathedral space',0,1,.01,'','Highpassed generated reverb.'],['echo','Distant reflection amount',0,1,.01,'','Highpassed repeats only.'],['echoTime','Reflection delay',.28,1.18,.01,' sec','Same delay on both channels.'],['feedback','Echo persistence',0,.6,.01,'','Stability-limited feedback amount.'],['air','Air brightness',0,1,.01,'','High shelving color.']]]
];
const P={...defaults};let engine=null,playing=false,mono=false,spatial='speaker',lastFrame=0,visualTime=0,lastMeter=0,lastUpdate=0;
const controlDefs=groups.flatMap(g=>g[2]);
const presets={
 horizon:{...defaults},
 tectonic:{...defaults,root:40,sub:.92,subHarm:.47,body:.62,bodyDrive:.76,pad:.37,bodyCutoff:500,width:.51},
 suspension:{...defaults,root:49,sub:.59,body:.18,pad:.79,shimmer:.50,reverb:.65,width:.92,orbit:.68},
 dusk:{...defaults,root:55,sub:.65,body:.37,pad:.69,reverb:.52,padBrightness:1300,dwell:37},
 deep:{...defaults,root:41.2,sub:.96,subHarm:.48,warmth:.36,body:.61,pad:.29,echo:.14,reverb:.25}};
function format(id){let v=P[id],c=controlDefs.find(x=>x[0]===id);return (Math.round(v*100)/100)+c[5]}
function sync(){for(const def of controlDefs){let id=def[0],x=$('#c-'+id),v=$('#v-'+id);if(x)x.value=P[id];if(v)v.textContent=format(id)}$('#freqRead').innerHTML=P.root.toFixed(2)+' <span>Hz</span>';$('#nowNote').textContent='FUNDAMENTAL · '+P.root.toFixed(2)+' Hz'}
for(const [name,opened,fields] of groups){
 const details=document.createElement('details');details.open=opened;
 const title=document.createElement('summary');title.textContent=name;
 const content=document.createElement('div');content.className='fields';
 for(const [key,label,min,max,step,unit,hint] of fields){
  const box=document.createElement('div');box.className='slider';
  box.innerHTML='<div class="sliderline"><label for="c-'+key+'">'+label+'</label><output id="v-'+key+'"></output></div><div class="hint">'+hint+'</div>';
  const input=document.createElement('input');Object.assign(input,{type:'range',id:'c-'+key,min,max,step,value:P[key]});input.setAttribute('aria-label',label);
  box.insertBefore(input,box.lastChild);content.appendChild(box);
  input.addEventListener('input',()=>{P[key]=Number(input.value);sync();if(engine&&(key!=='master'||playing))engine.apply(key,P[key]);});
 }
 details.append(title,content);$('#controls').appendChild(details);
}
$('#controlCount').textContent=controlDefs.length+' CONNECTED CONTROLS';sync();
function status(text,message){$('#live').textContent=text;$('#engineStatus').textContent=text;$('#activity').textContent=text;if(message)$('#message').textContent=message}
async function play(){
 if(!AC){status('UNAVAILABLE','Web Audio is not supported by this browser.');return;}
 try{if(!engine){const c=new AC({latencyHint:'playback'});engine=createEngine(c,P);c.onstatechange=()=>{if(playing&&c.state!=='running')status('TAP TO RESUME','Audio interrupted. Tap Begin to resume.');};}
 await engine.c.resume();if(engine.c.state!=='running')throw Error('Browser blocked audio; tap again');
 engine.setSpace(spatial);engine.setMono(mono);engine.output(P.master,.8);playing=true;
 $('#power').innerHTML='Ⅱ <span>PAUSE SOUND</span>';$('#power').setAttribute('aria-pressed','true');
 status('SOUND LIVE','Fundamental is centered; only the upper harmonies move through space.');
 }catch(e){status('TAP TO RESUME','Audio could not start: '+String(e.message||e))}
}
function stop(){if(engine)engine.output(0,.025);playing=false;setTimeout(()=>{if(engine&&!playing)engine.c.suspend().catch(()=>{});},180);$('#power').innerHTML='▶ <span>BEGIN THE JOURNEY</span>';$('#power').setAttribute('aria-pressed','false');status('MUTED','Output faded to silence. Tap BEGIN to resume.')}
$('#power').addEventListener('click',()=>playing?stop():play());
$('#panic').addEventListener('click',stop);
$('#spatialMode').addEventListener('change',e=>{spatial=e.target.value;engine?.setSpace(spatial);$('#message').textContent=spatial==='headphone'?'HRTF acts only on independent highpassed voices.':'Speaker mode uses gentle panning of independent higher voices.'});
$('#mono').addEventListener('click',()=>{mono=!mono;engine?.setMono(mono);$('#mono').classList.toggle('on',mono);$('#mono').setAttribute('aria-pressed',String(mono));$('#mono').textContent=mono?'✓ MONO MONITOR':'◉ MONO CHECK';$('#message').textContent=mono?'True L+R fold-down enabled. Bass should remain unchanged.':'Stereo spatial movement restored; bass is still mono.'});
$$('[data-preset]').forEach(b=>b.addEventListener('click',()=>{{const oldMaster=P.master;Object.assign(P,presets[b.dataset.preset]);P.master=oldMaster;}sync();$$('[data-preset]').forEach(x=>x.classList.toggle('selected',x===b));if(engine)for(const [key,value] of Object.entries(P))if(key!=='master'||playing)engine.apply(key,value);$('#message').textContent=b.textContent+' landscape selected.';}));
const canvas=$('#scope'),cx=canvas.getContext('2d'),bins=new Uint8Array(1024);
function frame(now){requestAnimationFrame(frame);if(now-lastFrame<33)return;let delta=Math.min(.06,(now-lastFrame)/1000||.033);lastFrame=now;const dpr=Math.min(devicePixelRatio||1,1.5),w=canvas.clientWidth,h=canvas.clientHeight;if(w<1||h<1)return;
 if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
 const W=canvas.width,H=canvas.height,X=W*.50,Y=H*.58,rad=Math.min(W,H)*.27;
 visualTime+=delta*(playing?.23:.05)*(1+P.motion);let env=playing?.65:.22;
 if(engine&&playing){engine.analyser.getByteFrequencyData(bins);env=Math.max(.25,Math.min(1.1,bins.slice(2,13).reduce((a,b)=>a+b,0)/(11*255)*3.3));}
 cx.clearRect(0,0,W,H);
 for(let layer=0;layer<9;layer++){cx.beginPath();const r=rad*(.72+layer*.085);
  for(let i=0;i<=220;i++){let t=i/220*Math.PI*2,undulate=(Math.sin(7*t+visualTime*1.5+layer*.32)*.024+Math.sin(13*t-visualTime*.6+layer)*.016)*(1+env),rr=r*(1+undulate),px=X+Math.cos(t)*rr,py=Y+Math.sin(t)*rr*.69;if(i)cx.lineTo(px,py);else cx.moveTo(px,py);}
  cx.strokeStyle=layer%2?'rgba(141,225,211,'+(.10+env*.14)+')':'rgba(229,186,136,'+(.06+env*.1)+')';cx.lineWidth=dpr*(layer===4?1.6:1);cx.stroke();
 }
 $('#orb').style.transform='translate(-50%,-50%) rotate('+(visualTime*7)+'deg) scale('+(1+env*.018)+')';
 
 if(engine&&playing&&now-lastMeter>900){let val=engine.lowCorrelation();$('#monoStatus').textContent=mono?'MONO PREVIEW':val===null?'QUIET':val>.9?'COHERENT':'CHECK LOW END';$('#monoStatus').title=val===null?'':('Measured low-frequency L/R correlation '+val.toFixed(3));lastMeter=now;}
}
requestAnimationFrame(frame);
setInterval(()=>{if(engine&&playing&&engine.c.state==='running')engine.update();},350);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&playing&&engine){engine.c.resume().then(()=>status('SOUND LIVE')).catch(()=>status('TAP TO RESUME'))}});
window.__earthlight={getParams:()=>({...P}),getStatus:()=>({playing,mono,spatial,audioState:engine?.c.state||'off',coherence:engine?.lowCorrelation()??null}),setParam:(key,value)=>{const el=$('#c-'+key);if(!el)throw Error('Unknown slider: '+key);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}))},createEngine,async simulate(options={}){if(!OC)throw Error('No OfflineAudioContext');const sec=options.seconds||3,sr=44100,c=new OC(2,Math.round(sec*sr),sr),params={...P};const g=createEngine(c,params,{offline:true});g.setSpace(options.spatial||'speaker');if(options.subOnly){for(const k of ['body','pad','shimmer','echo','reverb','subHarm','warmth'])g.apply(k,0)}g.master.gain.value=params.master;return c.startRendering()}};
