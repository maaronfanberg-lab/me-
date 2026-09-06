(function(root){
'use strict';

var API='https://api.openverse.org/v1/audio/';
var DEFAULT_QUERY='music';
var state={tracks:[],lastProbe:null};

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

function setStatus(ui,text,kind){
  ui.status.textContent=text;
  ui.status.className='status'+(kind?' '+kind:'');
}

function buildSearchURL(query){
  return API+'?q='+encodeURIComponent(query||DEFAULT_QUERY)+
    '&license=by'+
    '&extension=mp3'+
    '&page_size=30';
}

function requestJSON(url,callback){
  var xhr=new XMLHttpRequest();
  var finished=false;
  function finish(error,data){
    if(finished)return;
    finished=true;
    callback(error,data);
  }
  xhr.open('GET',url,true);
  xhr.timeout=15000;
  xhr.onreadystatechange=function(){
    if(xhr.readyState!==4||finished)return;
    if(xhr.status<200||xhr.status>=300){finish(new Error('openverse_http_'+xhr.status));return;}
    var data=null;
    try{data=JSON.parse(xhr.responseText);}catch(e){finish(new Error('openverse_invalid_json'));return;}
    finish(null,data);
  };
  xhr.ontimeout=function(){finish(new Error('openverse_timeout'));};
  xhr.onerror=function(){finish(new Error('openverse_network_error'));};
  xhr.send(null);
}

function licenseAllowsSpatial(track){
  return String((track&&track.license)||'').toLowerCase()==='by';
}

function licenseLabel(track){
  var version=String((track&&track.license_version)||'');
  return 'CC BY'+(version?' '+version:'');
}

function mp3URL(track){
  if(!track)return null;
  if(String(track.filetype||'').toLowerCase()==='mp3'&&track.url)return track.url;
  var alt=track.alt_files||[];
  for(var i=0;i<alt.length;i+=1){
    if(String(alt[i].filetype||'').toLowerCase()==='mp3'&&alt[i].url)return alt[i].url;
  }
  return null;
}

function sourcePage(track){
  return (track&&(track.foreign_landing_url||track.detail_url||track.related_url))||null;
}

function hiddenAudio(url,crossOrigin,muted){
  var media=document.createElement('audio');
  media.preload='auto';
  media.setAttribute('playsinline','playsinline');
  media.style.position='absolute';
  media.style.left='-9999px';
  media.style.width='1px';
  media.style.height='1px';
  if(crossOrigin)media.crossOrigin='anonymous';
  if(muted)media.muted=true;
  media.src=url;
  document.body.appendChild(media);
  return media;
}

function removeNode(node){
  if(node&&node.parentNode)node.parentNode.removeChild(node);
}

function safePlay(media){
  try{
    var result=media.play();
    if(result&&typeof result['catch']==='function')result['catch'](function(){});
  }catch(e){}
}

function mediaErrorCode(media){
  return media&&media.error?media.error.code:null;
}

function probeStream(url,callback){
  var AC=root.AudioContext||root.webkitAudioContext;
  if(!AC){callback({supported:false,reason:'web_audio_unavailable'});return;}

  var nativeMedia=hiddenAudio(url,false,true);
  var tappedMedia=hiddenAudio(url,true,false);
  var ctx=null,source=null,analyser=null,silent=null,timer=null;
  var ticks=0,maxDeviation=0;

  function cleanup(){
    if(timer)clearInterval(timer);
    try{nativeMedia.pause();}catch(e){}
    try{tappedMedia.pause();}catch(e2){}
    removeNode(nativeMedia);
    removeNode(tappedMedia);
    try{if(ctx&&ctx.close)ctx.close();}catch(e3){}
  }

  try{
    ctx=new AC();
    source=ctx.createMediaElementSource(tappedMedia);
    analyser=ctx.createAnalyser();
    analyser.fftSize=256;
    analyser.smoothingTimeConstant=0;
    silent=ctx.createGain();
    silent.gain.value=0;
    source.connect(analyser);
    analyser.connect(silent);
    silent.connect(ctx.destination);
    if(ctx.state==='suspended'&&ctx.resume)ctx.resume();
  }catch(error){
    cleanup();
    callback({supported:false,reason:'probe_graph_failed',detail:error.message||String(error)});
    return;
  }

  var data=new Uint8Array(analyser.fftSize);
  safePlay(nativeMedia);
  safePlay(tappedMedia);

  timer=setInterval(function(){
    ticks+=1;
    try{
      analyser.getByteTimeDomainData(data);
      for(var i=0;i<data.length;i+=1){
        var deviation=Math.abs(data[i]-128);
        if(deviation>maxDeviation)maxDeviation=deviation;
      }
    }catch(e){}

    if(ticks>=20){
      var nativeAdvanced=nativeMedia.currentTime>0.10;
      var tappedAdvanced=tappedMedia.currentTime>0.10;
      var pcmFlowing=maxDeviation>2;
      var result={
        supported:nativeAdvanced&&tappedAdvanced&&pcmFlowing,
        native_stream_playing:nativeAdvanced,
        cors_stream_playing:tappedAdvanced,
        web_audio_pcm_flowing:pcmFlowing,
        max_analyser_deviation:maxDeviation,
        native_media_error:mediaErrorCode(nativeMedia),
        tapped_media_error:mediaErrorCode(tappedMedia)
      };
      if(!nativeAdvanced)result.reason='native_stream_did_not_advance';
      else if(!tappedAdvanced)result.reason='cors_media_did_not_advance';
      else if(!pcmFlowing)result.reason='web_audio_pcm_flatline';
      else result.reason='spatial_pcm_available';
      cleanup();
      callback(result);
    }
  },100);
}

function loadIntoPlayer(track,url,spatialSupported){
  var player=document.getElementById('audio');
  var trackLabel=document.getElementById('track');
  var playerStatus=document.getElementById('status');
  if(!player)return;
  try{player.pause();}catch(e){}
  player.removeAttribute('src');
  if(spatialSupported)player.crossOrigin='anonymous';
  else player.removeAttribute('crossorigin');
  player.src=url;
  try{player.load();}catch(e2){}
  if(trackLabel)trackLabel.textContent='Openverse · '+(track.title||'Untitled')+' · '+(track.creator||'Unknown creator');
  if(playerStatus){
    if(spatialSupported){
      playerStatus.textContent='Openverse MP3 passed the live Web Audio PCM probe. Tap Play, then turn Spatial on.';
      playerStatus.className='status good';
    }else{
      playerStatus.textContent='Openverse MP3 is loaded for dry playback, but this device did not prove PCM access for the spatial engine.';
      playerStatus.className='status warn';
    }
  }
}

function testTrack(ui,track,control,diagnostic){
  var url=mp3URL(track);
  if(!licenseAllowsSpatial(track)){
    diagnostic.textContent='Blocked from the spatial test: this result is not CC BY.';
    diagnostic.className='status warn';
    return;
  }
  if(!url){
    diagnostic.textContent='This result does not expose an MP3 URL compatible with the iPhone 6 test.';
    diagnostic.className='status warn';
    return;
  }
  control.disabled=true;
  control.textContent='TESTING LIVE PCM…';
  diagnostic.textContent='Testing native MP3 playback and Web Audio PCM side by side for about two seconds…';
  diagnostic.className='status';
  probeStream(url,function(result){
    state.lastProbe={id:track.id,result:result};
    control.disabled=false;
    loadIntoPlayer(track,url,result.supported);
    if(result.supported){
      control.textContent='SPATIAL PCM VERIFIED ✓';
      diagnostic.textContent='Verified on this device: the MP3 advances and Web Audio receives non-flat PCM (max deviation '+result.max_analyser_deviation+').';
      diagnostic.className='status good';
    }else if(result.native_stream_playing){
      control.textContent='DRY STREAM ONLY';
      diagnostic.textContent='The MP3 plays, but the spatial path was not verified ('+result.reason+'). Loaded dry instead.';
      diagnostic.className='status warn';
    }else{
      control.textContent='RETRY STREAM TEST';
      diagnostic.textContent='The live stream test did not establish playback ('+result.reason+'). Nothing is being claimed as spatial.';
      diagnostic.className='status warn';
    }
  });
}

function renderTracks(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  if(!state.tracks.length){ui.tracks.appendChild(el('div','status','No compatible CC BY MP3 test tracks were returned.'));return;}
  var heading=el('div','status','OPENVERSE TEST CATALOG · '+state.tracks.length+' TRACKS');
  heading.style.marginTop='12px';heading.style.fontWeight='700';ui.tracks.appendChild(heading);
  for(var i=0;i<state.tracks.length;i+=1){
    (function(track){
      var row=el('div','metric');row.style.marginTop='8px';
      var name=el('b','',track.title||'Untitled');name.style.display='block';row.appendChild(name);
      var provider=track.provider||track.source||'open source';
      var meta=el('span','',(track.creator||'Unknown creator')+' · '+licenseLabel(track)+' · '+provider);
      meta.style.display='block';meta.style.marginTop='4px';row.appendChild(meta);
      var rights=el('div','status good','Spatial test candidate: CC BY metadata + MP3. Verify the source page before reuse outside this test.');
      rights.style.marginTop='4px';row.appendChild(rights);
      var original=sourcePage(track);
      if(original){
        var link=el('a','','Open original source');link.href=original;link.target='_blank';link.rel='noopener';
        link.style.display='inline-block';link.style.marginTop='6px';link.style.color='inherit';row.appendChild(link);
      }
      var diagnostic=el('div','status','Not tested on this device yet.');diagnostic.style.marginTop='6px';row.appendChild(diagnostic);
      var test=button('TEST + LOAD LIVE STREAM',function(){testTrack(ui,track,test,diagnostic);});test.style.marginTop='8px';row.appendChild(test);
      ui.tracks.appendChild(row);
    }(state.tracks[i]));
  }
}

function loadCatalog(ui){
  var query=ui.query.value||DEFAULT_QUERY;
  ui.load.disabled=true;ui.load.textContent='SEARCHING OPENVERSE…';
  setStatus(ui,'Searching anonymous Openverse audio for CC BY MP3 results…','');
  requestJSON(buildSearchURL(query),function(error,data){
    ui.load.disabled=false;ui.load.textContent='SEARCH OPEN MUSIC';
    if(error){state.tracks=[];renderTracks(ui);setStatus(ui,'Openverse API test failed: '+error.message,'warn');return;}
    var results=(data&&data.results)||[];
    var eligible=[];
    for(var i=0;i<results.length;i+=1){if(licenseAllowsSpatial(results[i])&&mp3URL(results[i]))eligible.push(results[i]);}
    state.tracks=eligible;renderTracks(ui);
    if(eligible.length)setStatus(ui,'Openverse results loaded. Pick a track and run the live PCM test on this device.','good');
    else setStatus(ui,'Openverse answered, but no compatible CC BY MP3 results survived the local filter.','warn');
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var card=el('div','card');card.id='openverseCard';
  var title=el('div','','OPENVERSE · NO-ACCOUNT LIVE TEST');title.style.fontWeight='700';title.style.letterSpacing='.06em';title.style.fontSize='12px';card.appendChild(title);
  var status=el('div','status','No login or API key required. This test searches CC BY MP3 audio through the public Openverse API.');status.id='openverseStatus';card.appendChild(status);
  var query=document.createElement('input');query.type='search';query.id='openverseQuery';query.value=DEFAULT_QUERY;query.setAttribute('aria-label','Openverse music search');
  query.style.width='100%';query.style.minHeight='46px';query.style.borderRadius='12px';query.style.border='1px solid #293347';query.style.background='#0b1018';query.style.color='#edf2fb';query.style.padding='10px 12px';query.style.fontSize='16px';query.style.marginTop='10px';card.appendChild(query);
  var load=button('SEARCH OPEN MUSIC',function(){loadCatalog(ui);});load.id='openverseLoad';card.appendChild(load);
  var tracks=el('div','');tracks.id='openverseTracks';card.appendChild(tracks);
  var note=el('div','legal','');
  note.appendChild(document.createTextNode('Development test: results are restricted to CC BY MP3 entries but are not tied to one provider. Openverse warns that license metadata should be verified at the original source, so every result links back to its source page. Pocket Spatial does not download, copy, or proxy the audio.'));
  card.appendChild(note);hero.parentNode.insertBefore(card,hero);
  return {card:card,status:status,query:query,load:load,tracks:tracks};
}

function boot(){
  var ui=createUI();if(!ui)return;
  root.PocketSpatialOpenverse={buildSearchURL:buildSearchURL,licenseAllowsSpatial:licenseAllowsSpatial,mp3URL:mp3URL,probeStream:probeStream,getLastProbe:function(){return state.lastProbe;}};
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
