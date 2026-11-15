(function(root){
'use strict';

var API='https://api.audius.co/v1';
var APP_NAME='PocketSpatial';
var API_LIMIT=50;
var DISPLAY_RESULTS=30;
var state={tracks:[],currentIndex:-1,currentButton:null,currentDiagnostic:null,ui:null,audio:null,stallTimer:null,autoFailures:0,mode:'idle'};

function el(tag,className,text){
  var node=document.createElement(tag);
  if(className)node.className=className;
  if(text!=null)node.textContent=text;
  return node;
}

function button(text,handler){
  var b=el('button','',text);
  b.type='button';
  b.addEventListener('click',handler);
  return b;
}

function cleanText(value){
  return String(value==null?'':value).replace(/\s+/g,' ').replace(/^\s+|\s+$/g,'');
}

function setStatus(ui,text,kind){
  ui.status.textContent=text;
  ui.status.className='status'+(kind?' '+kind:'');
}

function formatDuration(seconds){
  var n=Math.max(0,Math.round(Number(seconds)||0));
  if(!n)return '';
  var m=Math.floor(n/60);
  var s=n%60;
  return m+':'+(s<10?'0':'')+s;
}

function isPlayable(track){
  if(!track||!track.id)return false;
  if(track.is_streamable===false)return false;
  if(track.is_stream_gated===true)return false;
  if(track.access&&track.access.stream===false)return false;
  if(track.stream_conditions)return false;
  return true;
}

function streamURL(id){
  return API+'/tracks/'+encodeURIComponent(String(id||''))+'/stream?app_name='+encodeURIComponent(APP_NAME);
}

function pageURL(track){
  var p=cleanText(track&&track.permalink);
  if(/^https:\/\//i.test(p))return p;
  if(p&&p.charAt(0)!=='/')p='/'+p;
  return 'https://audius.co'+p;
}

function normalizeTrack(track){
  if(!isPlayable(track))return null;
  var user=track.user||{};
  return{
    pageid:'audius:'+String(track.id),
    source:'Audius',
    title:cleanText(track.title)||'Untitled Audius track',
    artist:cleanText(user.name||user.handle)||'Audius artist',
    license:cleanText(track.license),
    duration:Number(track.duration)||0,
    file_page:pageURL(track),
    audio:streamURL(track.id),
    audius_id:String(track.id)
  };
}

function buildCatalogURL(query){
  var q=cleanText(query);
  if(q){
    return API+'/tracks/search?query='+encodeURIComponent(q)+'&limit='+API_LIMIT+'&app_name='+encodeURIComponent(APP_NAME);
  }
  return API+'/tracks/trending?limit='+API_LIMIT+'&app_name='+encodeURIComponent(APP_NAME);
}

function xhrJSON(url,callback){
  if(!root.XMLHttpRequest){callback(new Error('xhr_unavailable'));return;}
  var xhr=new root.XMLHttpRequest();
  try{xhr.open('GET',url,true);}catch(e){callback(e);return;}
  xhr.timeout=15000;
  xhr.onerror=function(){callback(new Error('audius_catalog_failed_or_cors_blocked'));};
  xhr.ontimeout=function(){callback(new Error('audius_catalog_timeout'));};
  xhr.onload=function(){
    var status=Number(xhr.status)||0;
    if(status<200||status>=300){callback(new Error('audius_http_'+status));return;}
    var data=null;
    try{data=JSON.parse(xhr.responseText||'{}');}catch(e){callback(new Error('audius_bad_json'));return;}
    callback(null,data);
  };
  try{xhr.send();}catch(e){callback(e);}
}

function collectTracks(data){
  var raw=data&&data.data&&data.data.length!=null?data.data:[];
  var tracks=[];
  for(var i=0;i<raw.length&&tracks.length<DISPLAY_RESULTS;i+=1){
    var track=normalizeTrack(raw[i]);
    if(track)tracks.push(track);
  }
  return tracks;
}

function clearStallTimer(){
  if(state.stallTimer){root.clearTimeout(state.stallTimer);state.stallTimer=null;}
}

function setCurrentControl(buttonNode,diagnostic,text,kind){
  if(state.currentButton&&state.currentButton!==buttonNode){
    state.currentButton.disabled=false;
    state.currentButton.textContent='PLAY LIVE + SPATIAL';
  }
  if(state.currentDiagnostic&&state.currentDiagnostic!==diagnostic){
    state.currentDiagnostic.textContent='Ready for live Audius playback.';
    state.currentDiagnostic.className='status';
  }
  state.currentButton=buttonNode||null;
  state.currentDiagnostic=diagnostic||null;
  if(buttonNode){buttonNode.disabled=false;buttonNode.textContent='PLAYING LIVE';}
  if(diagnostic){diagnostic.textContent=text||'Opening live Audius stream…';diagnostic.className='status'+(kind?' '+kind:'');}
}

function ensureSpatialOn(){
  var badge=document.getElementById('badge');
  var spatial=document.getElementById('spatial');
  if(spatial&&badge&&badge.className.indexOf(' on')===-1){
    try{spatial.click();}catch(e){}
  }
}

function updateMainTrack(track){
  var label=document.getElementById('track');
  if(label)label.textContent=track.title+' — '+track.artist+' · Audius live stream';
}

function playPromiseHandled(p,diagnostic){
  if(!p||typeof p.then!=='function')return;
  p.then(function(){
    if(diagnostic){diagnostic.textContent='Live stream playing through Pocket Spatial.';diagnostic.className='status good';}
  },function(error){
    if(diagnostic){diagnostic.textContent='This stream did not start: '+(error&&error.message?error.message:'playback blocked')+'. Trying the next result…';diagnostic.className='status warn';}
    autoAdvance('playback start failed');
  });
}

function playTrack(index,buttonNode,diagnostic,isAuto){
  if(!state.audio||!state.tracks.length)return;
  if(index<0)index=0;
  if(index>=state.tracks.length)index=0;
  var track=state.tracks[index];
  state.currentIndex=index;
  state.mode='audius';
  clearStallTimer();
  setCurrentControl(buttonNode,diagnostic,'Opening live Audius stream…','');
  updateMainTrack(track);
  state.audio.pause();
  state.audio.crossOrigin='anonymous';
  state.audio.setAttribute('crossorigin','anonymous');
  state.audio.src=track.audio;
  try{state.audio.load();}catch(e){}
  ensureSpatialOn();
  if(state.ui){setStatus(state.ui,(isAuto?'Trying next stream: ':'Playing: ')+track.title+' — '+track.artist,'good');}
  try{playPromiseHandled(state.audio.play(),diagnostic);}catch(e){
    if(diagnostic){diagnostic.textContent='Stream failed to start. Trying the next result…';diagnostic.className='status warn';}
    autoAdvance('playback exception');
  }
}

function autoAdvance(reason){
  if(state.mode!=='audius'||!state.tracks.length)return;
  state.autoFailures+=1;
  if(state.autoFailures>=state.tracks.length){
    clearStallTimer();
    if(state.currentDiagnostic){state.currentDiagnostic.textContent='Audius returned results, but none of these streams could be played through the browser audio pipeline.';state.currentDiagnostic.className='status warn';}
    if(state.ui)setStatus(state.ui,'No playable live stream survived this pass. Try another search or reload Audius.','warn');
    return;
  }
  var next=(state.currentIndex+1)%state.tracks.length;
  var entry=state.ui&&state.ui.entries?state.ui.entries[next]:null;
  playTrack(next,entry&&entry.button,entry&&entry.diagnostic,true);
}

function nextTrack(){
  if(!state.tracks.length)return;
  state.autoFailures=0;
  var next=(state.currentIndex+1)%state.tracks.length;
  var entry=state.ui&&state.ui.entries?state.ui.entries[next]:null;
  playTrack(next,entry&&entry.button,entry&&entry.diagnostic,true);
}

function bindAudioEvents(){
  if(!state.audio)return;
  state.audio.addEventListener('canplay',function(){clearStallTimer();state.autoFailures=0;});
  state.audio.addEventListener('playing',function(){
    clearStallTimer();
    if(state.currentDiagnostic){state.currentDiagnostic.textContent='Live stream playing through Pocket Spatial.';state.currentDiagnostic.className='status good';}
  });
  state.audio.addEventListener('error',function(){
    if(state.mode!=='audius')return;
    if(state.currentDiagnostic){state.currentDiagnostic.textContent='This Audius stream failed. Trying the next result automatically…';state.currentDiagnostic.className='status warn';}
    autoAdvance('media error');
  });
  state.audio.addEventListener('stalled',function(){
    if(state.mode!=='audius')return;
    clearStallTimer();
    state.stallTimer=root.setTimeout(function(){
      if(state.mode!=='audius')return;
      if(state.currentDiagnostic){state.currentDiagnostic.textContent='Stream stalled for too long. Trying the next result…';state.currentDiagnostic.className='status warn';}
      autoAdvance('stall timeout');
    },12000);
  });
  state.audio.addEventListener('ended',function(){if(state.mode==='audius')nextTrack();});
  var file=document.getElementById('file');
  if(file)file.addEventListener('change',function(){state.mode='local';clearStallTimer();});
}

function renderTracks(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  ui.entries=[];
  if(!state.tracks.length){
    ui.tracks.appendChild(el('div','status','Audius responded, but no ordinary ungated streamable tracks were returned for this search.'));
    return;
  }
  var heading=el('div','status','AUDIUS · '+state.tracks.length+' LIVE STREAM CANDIDATES');
  heading.style.marginTop='12px';
  heading.style.fontWeight='700';
  ui.tracks.appendChild(heading);
  for(var i=0;i<state.tracks.length;i+=1){
    (function(track,index){
      var row=el('div','metric');
      row.style.marginTop='8px';
      var name=el('b','',track.title);
      name.style.display='block';
      row.appendChild(name);
      var metaText=track.artist;
      if(track.duration)metaText+=' · '+formatDuration(track.duration);
      if(track.license)metaText+=' · '+track.license;
      var meta=el('span','',metaText);
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);
      var access=el('div','status good','Audius reports this track as API-streamable and ungated. Pocket Spatial plays the live stream without exporting or saving the track.');
      access.style.marginTop='4px';
      row.appendChild(access);
      var link=el('a','','Open this track on Audius');
      link.href=track.file_page;
      link.target='_blank';
      link.rel='noopener';
      link.style.display='inline-block';
      link.style.marginTop='6px';
      link.style.color='inherit';
      row.appendChild(link);
      var diagnostic=el('div','status','Ready for live Audius playback.');
      diagnostic.style.marginTop='6px';
      row.appendChild(diagnostic);
      var play=button('PLAY LIVE + SPATIAL',function(){
        state.autoFailures=0;
        playTrack(index,play,diagnostic,false);
      });
      play.style.marginTop='8px';
      row.appendChild(play);
      ui.entries[index]={button:play,diagnostic:diagnostic};
      ui.tracks.appendChild(row);
    }(state.tracks[i],i));
  }
}

function finishCatalog(ui,error,data,label){
  ui.load.disabled=false;
  ui.load.textContent='SEARCH / RELOAD AUDIUS';
  if(error){
    state.tracks=[];
    renderTracks(ui);
    setStatus(ui,'Audius catalog request failed: '+error.message,'warn');
    return;
  }
  state.tracks=collectTracks(data);
  state.currentIndex=-1;
  state.autoFailures=0;
  renderTracks(ui);
  if(state.tracks.length){
    setStatus(ui,'Audius connected. '+state.tracks.length+' live stream candidates found for '+label+'. Tap any result; failures will skip automatically.','good');
  }else{
    setStatus(ui,'Audius connected, but this search returned no ordinary ungated streamable tracks.','warn');
  }
}

function loadCatalog(ui){
  var query=ui.query?cleanText(ui.query.value):'';
  ui.load.disabled=true;
  ui.load.textContent=query?'SEARCHING AUDIUS…':'LOADING TRENDING…';
  setStatus(ui,query?'Searching Audius for “'+query+'”…':'Loading trending Audius tracks…','');
  xhrJSON(buildCatalogURL(query),function(error,data){finishCatalog(ui,error,data,query?'“'+query+'”':'trending');});
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var sub=document.querySelector('.sub');
  if(sub)sub.textContent='Live spatial processor for Audius streams and local audio · routes through the iPhone audio output';
  var card=el('div','card');
  card.id='audiusLiveCard';
  var title=el('div','','AUDIUS · LIVE SPATIAL MUSIC');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);
  var status=el('div','status','Search Audius or leave the box blank for trending tracks. Playback is live; Pocket Spatial does not pre-download the whole track.');
  status.id='audiusLiveStatus';
  card.appendChild(status);
  var query=el('input','');
  query.type='text';
  query.placeholder='Artist, track, genre… (blank = trending)';
  query.id='audiusLiveQuery';
  query.autocapitalize='off';
  query.autocomplete='off';
  query.style.width='100%';
  query.style.boxSizing='border-box';
  query.style.margin='8px 0';
  query.style.minHeight='46px';
  query.style.borderRadius='12px';
  query.style.border='1px solid var(--line)';
  query.style.background='#0b1018';
  query.style.color='var(--text)';
  query.style.padding='10px';
  var ui={card:card,status:status,query:query,load:null,next:null,tracks:null,entries:[]};
  card.appendChild(query);
  query.addEventListener('keydown',function(event){if((event.key||'')==='Enter')loadCatalog(ui);});
  var load=button('LOAD AUDIUS MUSIC',function(){loadCatalog(ui);});
  load.id='audiusLiveLoad';
  ui.load=load;
  card.appendChild(load);
  var next=button('NEXT LIVE TRACK',function(){nextTrack();});
  next.id='audiusLiveNext';
  ui.next=next;
  card.appendChild(next);
  var tracks=el('div','');
  tracks.id='audiusLiveTracks';
  ui.tracks=tracks;
  card.appendChild(tracks);
  var note=el('div','legal','Pocket Spatial uses Audius API-accessible streams and respects Audius stream gating/access controls. It does not rip, export, or persist streamed tracks.');
  note.style.marginTop='8px';
  card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);
  return ui;
}

function boot(){
  state.audio=document.getElementById('audio');
  if(!state.audio)return;
  state.audio.crossOrigin='anonymous';
  state.audio.setAttribute('crossorigin','anonymous');
  state.ui=createUI();
  if(!state.ui)return;
  bindAudioEvents();
  root.PocketSpatialAudiusCatalog={
    buildCatalogURL:buildCatalogURL,
    isPlayable:isPlayable,
    normalizeTrack:normalizeTrack,
    streamURL:streamURL,
    load:function(query){state.ui.query.value=query||'';loadCatalog(state.ui);},
    next:nextTrack,
    ui:state.ui
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));