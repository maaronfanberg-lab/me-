export const PAGE = String.raw`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
<title>Room Next</title>
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#f4f4f5;background:#0b0c0f}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#161922 0,#0b0c0f 44%);min-height:100vh}button,input,select{font:inherit}.shell{max-width:760px;margin:0 auto;min-height:100vh;padding:18px 14px 130px}.top{display:flex;gap:14px;align-items:flex-start;justify-content:space-between;margin-bottom:16px}.title{font-size:27px;font-weight:760;letter-spacing:-.03em}.sub{color:#a1a1aa;font-size:13px;margin-top:5px;line-height:1.35}.pill{white-space:nowrap;font-size:12px;border:1px solid #2d313c;background:#151821;border-radius:999px;padding:7px 10px;color:#c8cad0}.scene{border:1px solid #272b34;background:#11141a;border-radius:16px;padding:12px 14px;color:#b7bac2;font-size:13px;margin-bottom:14px}.feed{display:flex;flex-direction:column;gap:10px}.msg{border:1px solid #262a33;background:#12151b;border-radius:16px;padding:12px 14px;box-shadow:0 10px 35px rgba(0,0,0,.16)}.msg.you{background:#161b24;border-color:#303745}.meta{display:flex;align-items:center;gap:8px;margin-bottom:6px}.speaker{font-weight:700}.target{font-size:11px;color:#7d828d}.time{margin-left:auto;font-size:11px;color:#6f7480}.text{line-height:1.45;font-size:16px;white-space:pre-wrap}.action .text{font-style:italic;color:#b9bdc7}.empty{padding:38px 16px;text-align:center;color:#777d88}.composer{position:fixed;left:0;right:0;bottom:0;background:linear-gradient(180deg,rgba(11,12,15,0),rgba(11,12,15,.96) 18%,#0b0c0f 45%);padding:28px 12px max(12px,env(safe-area-inset-bottom))}.composer-inner{max-width:760px;margin:0 auto;border:1px solid #2d323d;background:#13161d;border-radius:18px;padding:9px;box-shadow:0 -8px 34px rgba(0,0,0,.35)}.row{display:flex;gap:8px}.entry{flex:1;min-width:0;border:0;outline:none;color:#f4f4f5;background:transparent;padding:11px 10px}.send{border:0;border-radius:12px;padding:0 16px;font-weight:700;background:#f2f2f3;color:#0b0c0f}.controls{display:flex;gap:8px;margin-top:6px;padding:0 4px}.controls select,.controls input{color:#9fa4ae;background:transparent;border:0;outline:none;font-size:12px;min-width:0}.controls select{max-width:140px}.controls input{flex:1}.note{font-size:11px;color:#676d78;margin:8px 5px 1px}.error{color:#ff9e9e}.thinking{opacity:.7}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#7ad7a5;margin-right:6px}.quiet .dot{background:#7f8490}@media(max-width:520px){.title{font-size:24px}.text{font-size:15.5px}.pill{font-size:11px}.shell{padding-top:14px}}
</style>
</head>
<body>
<main class="shell">
  <div class="top">
    <div><div class="title">Room Next</div><div class="sub">Fresh world. Private minds. Nobody is required to speak.</div></div>
    <div id="status" class="pill quiet"><span class="dot"></span>connecting</div>
  </div>
  <div id="scene" class="scene">Loading the room…</div>
  <section id="feed" class="feed"><div class="empty">The room is quiet.</div></section>
</main>
<div class="composer">
  <div class="composer-inner">
    <div class="row">
      <input id="text" class="entry" maxlength="700" autocomplete="off" placeholder="Say something…" />
      <button id="send" class="send">Send</button>
    </div>
    <div class="controls">
      <select id="target" aria-label="Target">
        <option value="room">to the room</option>
        <option value="sarah">to Sarah</option>
        <option value="mara">to Mara</option>
        <option value="owen">to Owen</option>
        <option value="jules">to Jules</option>
      </select>
      <input id="key" type="password" autocomplete="off" placeholder="owner key, if configured" />
    </div>
    <div id="note" class="note">One person may answer. Or nobody may. That is intentional.</div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);let lastRevision=-1;let sending=false;let firstLoad=true;
const savedKey=localStorage.getItem('roomNextKey')||'';$('key').value=savedKey;
$('key').addEventListener('change',()=>localStorage.setItem('roomNextKey',$('key').value.trim()));
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function clock(iso){try{return new Date(iso).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})}catch{return''}}
function render(state){
  $('scene').textContent=state.scene||'A quiet shared room.';
  const open=state.conversation&&state.conversation.open;
  $('status').className='pill '+(open?'':'quiet');
  $('status').innerHTML='<span class="dot"></span>'+(open?'conversation open':'quiet');
  const list=state.transcript||[];
  if(!list.length){$('feed').innerHTML='<div class="empty">The room is quiet. You can speak first, or leave it alone.</div>';return}
  $('feed').innerHTML=list.map(m=>'<article class="msg '+(m.speaker==='You'?'you ':'')+(m.kind==='action'?'action':'')+'"><div class="meta"><span class="speaker">'+esc(m.speaker)+'</span><span class="target">'+(m.target&&m.target!=='room'?'→ '+esc(m.target):'')+'</span><span class="time">'+clock(m.at)+'</span></div><div class="text">'+esc(m.text)+'</div></article>').join('');
  if(firstLoad){firstLoad=false;window.scrollTo({top:document.body.scrollHeight,behavior:'instant'})}
}
async function refresh(){
  try{
    const r=await fetch('/api/state?x='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('state '+r.status);
    const s=await r.json();if(s.revision!==lastRevision){lastRevision=s.revision;render(s)}
  }catch(e){$('status').className='pill quiet';$('status').innerHTML='<span class="dot"></span>reconnecting'}
}
async function send(){
  if(sending)return;const text=$('text').value.trim();if(!text)return;sending=true;$('send').disabled=true;$('note').className='note thinking';$('note').textContent='The room is deciding who, if anyone, wants to respond…';
  const headers={'content-type':'application/json'};const key=$('key').value.trim();if(key)headers.authorization='Bearer '+key;
  try{
    const r=await fetch('/api/say',{method:'POST',headers,body:JSON.stringify({text,target:$('target').value})});
    const data=await r.json();if(r.status===401){throw new Error('This Room has an owner key. Enter it below and try again.')}if(!r.ok)throw new Error(data.error||('HTTP '+r.status));
    $('text').value='';lastRevision=data.revision;render(data);window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'});$('note').className='note';$('note').textContent='Quiet is allowed. The next autonomous beat happens on its own.';
  }catch(e){$('note').className='note error';$('note').textContent=e.message||String(e)}finally{sending=false;$('send').disabled=false;$('text').focus()}
}
$('send').addEventListener('click',send);$('text').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
refresh();setInterval(refresh,1500);
</script>
</body>
</html>`;
