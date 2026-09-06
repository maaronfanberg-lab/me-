(function(root){
'use strict';

var TEST_CLIENT_ID='709fa152';
var API='https://api.jamendo.com/v3.0/tracks/';
var jsonpCounter=0;
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

function removeNode(node){
  if(node&&node.parentNode)node.parentNode.removeChild(node);
}

function buildTracksURL(callbackName){
  return API+'?client_id='+encodeURIComponent(TEST_CLIENT_ID)+
    '&format=json'+
    '&limit=16'+
    '&audioformat=mp32'+
    '&include=licenses'+
    '&ccnd=false'+
    '&order=popularity_total'+
    '&groupby=artist_id'+
    '&callback='+encodeURIComponent(callbackName);
}

function jsonp(url,callback){
  jsonpCounter+=1;
  var name='PocketSpatialJamendoJSONP'+jsonpCounter;
  var script=document.createElement('script');
  var done=false;
  var timer=null;

  function finish(error,data){
    if(done)return;
    done=true;
    if(timer)clearTimeout(timer);
    removeNode(script);
    try{delete root[name];}catch(e){root[name]=null;}
    callback(error,data);
  }

  root[name]=function(data){finish(null,data);};
  script.onerror=function(){finish(new Error('jamendo_jsonp_failed'));};
  script.src=url.replace('{callback}',encodeURIComponent(name));
  script.async=true;
  document.head.appendChild(script);
  timer=setTimeout(function(){finish(new Error('jamendo_jsonp_timeout'));},12000);
}

function licenseURL(track){
  return String((track&&track.license_ccurl)||'').toLowerCase();
}

function licenseAllowsSpatial(track){
  var url=licenseURL(track);
  if(!url)return false;
  if(url.indexOf('-nd/')!==-1||url.indexOf('/nd/')!==-1)return false;
  return url.indexOf('creativecommons.org/')!==-1;
}

function licenseLabel(track){
  var url=licenseURL(track);
  if(!url)return 'License unavailable';
  var match=url.match(/licenses\/([^/]+)\//);
  if(match&&match[1])return 'CC '+match[1].toUpperCase();
  if(url.indexOf('publicdomain/zero')!==-1||url.indexOf('/zero/')!==-1)return 'CC0';
  return 'Creative Commons';
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
  var ctx=null;
  var source=null;
  var analyser=null;
  var silent=null;
  var timer=null;
  var ticks=0;
  var maxDeviation=0;

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

function loadIntoPlayer(track,spatialSupported){
  var player=document.getElementById('audio');
  var trackLabel=document.getElementById('track');
  var playerStatus=document.getElementById('status');
  if(!player)return;

  try{player.pause();}catch(e){}
  player.removeAttribute('src');
  if(spatialSupported)player.crossOrigin='anonymous';
  else player.removeAttribute('crossorigin');
  player.src=track.audio;
  try{player.load();}catch(e2){}

  if(trackLabel)trackLabel.textContent='Jamendo · '+(track.name||'Untitled')+' · '+(track.artist_name||'Unknown artist');
  if(playerStatus){
    if(spatialSupported){
      playerStatus.textContent='Jamendo stream passed the live Web Audio PCM probe. Tap Play, then turn Spatial on.';
      playerStatus.className='status good';
    }else{
      playerStatus.textContent='Jamendo stream is loaded for dry playback, but this device did not prove PCM access for the spatial engine.';
      playerStatus.className='status warn';
    }
  }
}

function testTrack(ui,track,control,diagnostic){
  if(!licenseAllowsSpatial(track)){
    diagnostic.textContent='Blocked from the spatial test: this track does not expose a derivative-permitting Creative Commons license.';
    diagnostic.className='status warn';
    return;
  }
  if(!track.audio){
    diagnostic.textContent='Jamendo did not return a stream URL for this track.';
    diagnostic.className='status warn';
    return;
  }

  control.disabled=true;
  control.textContent='TESTING LIVE PCM…';
  diagnostic.textContent='Testing native stream playback and Web Audio PCM side by side for about two seconds…';
  diagnostic.className='status';

  probeStream(track.audio,function(result){
    state.lastProbe={track_id:track.id,result:result};
    control.disabled=false;
    loadIntoPlayer(track,result.supported);
    if(result.supported){
      control.textContent='SPATIAL PCM VERIFIED ✓';
      diagnostic.textContent='Verified on this device: Jamendo stream advances and Web Audio receives non-flat PCM (max deviation '+result.max_analyser_deviation+').';
      diagnostic.className='status good';
    }else if(result.native_stream_playing){
      control.textContent='DRY STREAM ONLY';
      diagnostic.textContent='The stream plays, but the spatial path was not verified ('+result.reason+'). Loaded dry instead.';
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
  if(!state.tracks.length){
    ui.tracks.appendChild(el('div','status','No derivative-permitting test tracks were returned.'));
    return;
  }

  var heading=el('div','status','JAMENDO TEST CATALOG · '+state.tracks.length+' TRACKS');
  heading.style.marginTop='12px';
  heading.style.fontWeight='700';
  ui.tracks.appendChild(heading);

  for(var i=0;i<state.tracks.length;i+=1){
    (function(track){
      var row=el('div','metric');
      row.style.marginTop='8px';
      var name=el('b','',track.name||'Untitled');
      name.style.display='block';
      row.appendChild(name);

      var meta=el('span','',(track.artist_name||'Unknown artist')+' · '+licenseLabel(track));
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);

      var rights=el('div','status good','Spatial test eligible: Creative Commons license has no NoDerivatives restriction.');
      rights.style.marginTop='4px';
      row.appendChild(rights);

      if(track.shareurl){
        var link=el('a','','Open original on Jamendo');
        link.href=track.shareurl;
        link.target='_blank';
        link.rel='noopener';
        link.style.display='inline-block';
        link.style.marginTop='6px';
        link.style.color='inherit';
        row.appendChild(link);
      }

      var diagnostic=el('div','status','Not tested on this device yet.');
      diagnostic.style.marginTop='6px';
      row.appendChild(diagnostic);

      var test=button('TEST + LOAD LIVE STREAM',function(){testTrack(ui,track,test,diagnostic);});
      test.style.marginTop='8px';
      row.appendChild(test);
      ui.tracks.appendChild(row);
    }(state.tracks[i]));
  }
}

function loadCatalog(ui){
  ui.load.disabled=true;
  ui.load.textContent='LOADING JAMENDO…';
  setStatus(ui,'Requesting popular derivative-permitting tracks through Jamendo’s official read API…','');

  var template=buildTracksURL('{callback}');
  jsonp(template,function(error,data){
    ui.load.disabled=false;
    ui.load.textContent='RELOAD TEST CATALOG';
    if(error){
      state.tracks=[];
      renderTracks(ui);
      setStatus(ui,'Jamendo API test failed: '+error.message,'warn');
      return;
    }
    if(!data||!data.headers||data.headers.status!=='success'){
      state.tracks=[];
      renderTracks(ui);
      setStatus(ui,'Jamendo returned an API error. The test client may be unavailable or rate-limited.','warn');
      return;
    }
    var results=data.results||[];
    var eligible=[];
    for(var i=0;i<results.length;i+=1){
      if(licenseAllowsSpatial(results[i])&&results[i].audio)eligible.push(results[i]);
    }
    state.tracks=eligible;
    renderTracks(ui);
    setStatus(ui,'Jamendo test catalog loaded. Choose a track and run the live PCM test on this device.','good');
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;

  var card=el('div','card');
  card.id='jamendoCard';

  var title=el('div','','JAMENDO · LIVE SPATIAL TEST');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);

  var status=el('div','status','Ready to use Jamendo’s published test Client ID. No Jamendo account is required for this development test.');
  status.id='jamendoStatus';
  card.appendChild(status);

  var load=button('LOAD TEST CATALOG',function(){loadCatalog(ui);});
  load.id='jamendoLoad';
  card.appendChild(load);

  var tracks=el('div','');
  tracks.id='jamendoTracks';
  card.appendChild(tracks);

  var note=el('div','legal','');
  note.appendChild(document.createTextNode('Development test only: this uses Jamendo’s published read-API test Client ID. Pocket Spatial also rejects NoDerivatives licenses locally before enabling the spatial test. A private app Client ID is still required before any production release.'));
  card.appendChild(note);

  hero.parentNode.insertBefore(card,hero);
  return {card:card,status:status,load:load,tracks:tracks};
}

function boot(){
  var ui=createUI();
  if(!ui)return;
  root.PocketSpatialJamendo={
    testClientId:TEST_CLIENT_ID,
    buildTracksURL:buildTracksURL,
    licenseAllowsSpatial:licenseAllowsSpatial,
    probeStream:probeStream,
    getLastProbe:function(){return state.lastProbe;}
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
