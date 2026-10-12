# Stage G (preview): record video with sound, the 3D view plus what you hear, and save it to the phone.
# MediaRecorder: Safari since iOS 14.3 records MP4 (H.264 video, AAC audio) from any MediaStreamTrack,
# including canvas and Web Audio tracks (WebKit blog, "MediaRecorder API", 2020-11-23). The canvas
# stream comes from captureStream(); the sound from a MediaStreamAudioDestinationNode fed by the same
# master gain as the speakers. Saving uses the share sheet (Web Share with files; "Save Video" on
# iOS), falling back to a download link. Edits apps/resonator-next.html in place; aborts on mismatch.
import sys
P = sys.argv[1]
s = open(P, encoding='utf-8').read()

def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f'ABORT: expected {count} match(es), found {n}: {old[:90]!r}')
    s = s.replace(old, new)

rep("""        <button class="chip" id="recbtn" aria-pressed="false">Record</button>
        <a class="chip rec" id="reclink" href="#">Save</a>
      </div>
""", """        <button class="chip" id="recbtn" aria-pressed="false">Record</button>
        <a class="chip rec" id="reclink" href="#">Save</a>
      </div>
      <div class="row">
        <button class="chip" id="vrecbtn" aria-pressed="false">Record video</button>
        <a class="chip rec" id="vreclink" href="#">Save video</a>
      </div>
      <div class="vrecnote" id="vrecnote"></div>
""")
rep("document.getElementById('recbtn').onclick=()=>{ REC.on?stopRec():startRec(); };\n",
    """document.getElementById('recbtn').onclick=()=>{ REC.on?stopRec():startRec(); };
// G: video with sound. The 3D view (canvas.captureStream) plus everything you hear (a stream tap on
// the master gain), recorded by MediaRecorder: MP4 (H.264 + AAC) on iPhone, WebM elsewhere.
const VREC={on:false,rec:null,chunks:[],t0:0,blob:null,dest:null,timer:null,mime:'',done:false,max:60};
function vrecMime(){ const c=['video/mp4;codecs=avc1,mp4a.40.2','video/mp4','video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'];
  for(const m of c){ try{ if(MediaRecorder.isTypeSupported(m)) return m; }catch(e){} } return ''; }
function vrecWhyNot(){ if(typeof MediaRecorder==='undefined') return 'This browser cannot record video (no MediaRecorder).';
  if(!cv.captureStream) return 'This browser cannot record the 3D view (no canvas capture).';
  if(!ctx||!ctx.createMediaStreamDestination) return 'This browser cannot record the sound into a video.'; return ''; }
function vrecNote(t,warn){ const n=document.getElementById('vrecnote'); n.textContent=t; n.className='vrecnote'+(warn?' warn':''); }
function vrecLabel(){ const s=Math.floor((performance.now()-VREC.t0)/1000);
  document.getElementById('vrecbtn').textContent='Stop video · '+Math.floor(s/60)+':'+String(s%60).padStart(2,'0');
  if(s>=VREC.max) vrecStop(); }
function vrecStart(){
  if(!node||!ctx) return; const why=vrecWhyNot(); if(why){ vrecNote(why,true); return; }
  if(REC.on) stopRec();
  try{
    if(!VREC.dest) VREC.dest=ctx.createMediaStreamDestination();
    master.connect(VREC.dest);
    const vs=cv.captureStream(30);
    const stream=new MediaStream([...vs.getVideoTracks(),...VREC.dest.stream.getAudioTracks()]);
    VREC.mime=vrecMime();
    const opt={videoBitsPerSecond:2500000,audioBitsPerSecond:192000}; if(VREC.mime) opt.mimeType=VREC.mime;
    VREC.rec=new MediaRecorder(stream,opt);
  }catch(e){ try{ master.disconnect(VREC.dest); }catch(_){} vrecNote('Video recording could not start: '+(e.message||e),true); return; }
  VREC.chunks=[]; VREC.blob=null; VREC.done=false;
  VREC.rec.ondataavailable=e=>{ if(e.data&&e.data.size) VREC.chunks.push(e.data); };
  VREC.rec.onstop=()=>vrecFinish();
  VREC.rec.start(1000);
  VREC.on=true; VREC.t0=performance.now();
  document.getElementById('vreclink').classList.remove('on');
  const b=document.getElementById('vrecbtn'); b.setAttribute('aria-pressed','true'); vrecLabel();
  VREC.timer=setInterval(vrecLabel,250);
  vrecNote('Recording the view and the sound (up to '+VREC.max+' s). Play now.');
}
function vrecStop(){
  if(!VREC.on) return; VREC.on=false; clearInterval(VREC.timer);
  const b=document.getElementById('vrecbtn'); b.setAttribute('aria-pressed','false'); b.textContent='Record video';
  try{ if(VREC.rec.state!=='inactive'){ VREC.rec.requestData(); VREC.rec.stop(); } }catch(e){}
  setTimeout(()=>{ if(!VREC.done) vrecFinish(); },2000);   // iOS 15 could fail to fire onstop
}
function vrecFinish(){
  if(VREC.done) return; VREC.done=true;
  try{ master.disconnect(VREC.dest); }catch(e){}
  const type=(VREC.rec&&VREC.rec.mimeType)||VREC.mime||'video/mp4';
  VREC.blob=new Blob(VREC.chunks,{type:type.split(';')[0]});
  if(VREC.blob.size<2048){ vrecNote('Nothing captured. Play something while it records.',true); return; }
  const secs=Math.max(1,Math.round((performance.now()-VREC.t0)/1000));
  const a=document.getElementById('vreclink'); a.textContent='Save video · '+(VREC.blob.size/1048576).toFixed(1)+' MB'; a.classList.add('on');
  vrecNote('Recorded about '+secs+' s. Tap Save video, then "Save Video" to put it in Photos.');
}
async function vrecSave(){
  if(!VREC.blob) return;
  const ext=VREC.blob.type.indexOf('mp4')>=0?'mp4':'webm';
  const name='resonator-'+new Date().toISOString().slice(0,19).replace(/[-:T]/g,'')+'.'+ext;
  const f=new File([VREC.blob],name,{type:VREC.blob.type});
  try{ if(navigator.canShare&&navigator.canShare({files:[f]})){ await navigator.share({files:[f],title:'RESONATOR'}); return; } }
  catch(e){ if(e&&e.name==='AbortError') return; }
  const u=URL.createObjectURL(f), a=document.createElement('a'); a.href=u; a.download=name; document.body.appendChild(a); a.click();
  setTimeout(()=>{ URL.revokeObjectURL(u); a.remove(); },10000);
}
// drawn on top of the 3D view while recording: it lands in the video, and the red dot shows it is on
function vrecOverlay(){
  const s=Math.floor((performance.now()-VREC.t0)/1000);
  g2.save(); g2.font='600 11px '+getComputedStyle(document.body).getPropertyValue('--mono');
  g2.fillStyle='rgba(8,13,26,0.55)'; g2.fillRect(8,H-30,Math.min(W-16,250),22);
  g2.fillStyle='#F0EAD8'; g2.fillText('RESONATOR · '+state.shape+' · '+(state.geo?state.geo.P.length:0)+' masses',14,H-15);
  g2.fillStyle='#FF5A4E'; g2.beginPath(); g2.arc(W-58,18,5,0,7); g2.fill();
  g2.fillStyle='#F0EAD8'; g2.fillText(Math.floor(s/60)+':'+String(s%60).padStart(2,'0'),W-48,22);
  g2.restore();
}
document.getElementById('vrecbtn').onclick=()=>{ VREC.on?vrecStop():vrecStart(); };
document.getElementById('vreclink').onclick=e=>{ e.preventDefault(); vrecSave(); };
""")
rep("function frame(ts){requestAnimationFrame(frame);if(!W)resize();if(state.tool!=='orbit'&&!drag&&ts-(state._lastDraw||0)<100)return;",
    "function frame(ts){requestAnimationFrame(frame);if(!W)resize();if(state.tool!=='orbit'&&!drag&&!VREC.on&&ts-(state._lastDraw||0)<100)return;")
rep("""   g2.setLineDash([]);
 }
}
requestAnimationFrame(frame);""", """   g2.setLineDash([]);
 }
 if(VREC.on) vrecOverlay();   // G
}
requestAnimationFrame(frame);""")
# a small note line under the buttons, styled like the other hints
rep("</style>", ".vrecnote{font-size:11px;color:var(--dim);margin:2px 2px 10px;min-height:1em}.vrecnote.warn{color:var(--tension)}\n</style>")
open(P, 'w', encoding='utf-8').write(s)
print('patched OK')
