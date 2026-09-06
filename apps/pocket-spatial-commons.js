(function(root){
'use strict';

var API='https://commons.wikimedia.org/w/api.php';
var CATEGORY='Category:Audio files of music';
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

function buildCatalogURL(callbackName){
  return API+'?action=query'+
    '&generator=categorymembers'+
    '&gcmtitle='+encodeURIComponent(CATEGORY)+
    '&gcmnamespace=6'+
    '&gcmtype=file'+
    '&gcmlimit=12'+
    '&prop=videoinfo'+
    '&viprop='+encodeURIComponent('url|mime|derivatives|extmetadata')+
    '&viextmetadatafilter='+encodeURIComponent('LicenseShortName|LicenseUrl|Artist|Credit|AttributionRequired|UsageTerms')+
    '&format=json'+
    '&callback='+encodeURIComponent(callbackName);
}

function jsonp(template,callback){
  jsonpCounter+=1;
  var name='PocketSpatialCommonsJSONP'+jsonpCounter;
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
  script.onerror=function(){finish(new Error('commons_jsonp_failed'));};
  script.src=template.replace(/%7Bcallback%7D/i,encodeURIComponent(name)).replace('{callback}',encodeURIComponent(name));
  script.async=true;
  document.head.appendChild(script);
  timer=setTimeout(function(){finish(new Error('commons_jsonp_timeout'));},12000);
}

function plain(value){
  return String(value==null?'':value)
    .replace(/<[^>]*>/g,'')
    .replace(/&amp;/g,'&')
    .replace(/&quot;/g,'"')
    .replace(/&#39;|&apos;/g,"'")
    .replace(/&lt;/g,'<')
    .replace(/&gt;/g,'>')
    .replace(/\s+/g,' ')
    .replace(/^\s+|\s+$/g,'');
}

function metadataValue(info,key){
  var meta=info&&info.extmetadata&&info.extmetadata[key];
  return meta?plain(meta.value):'';
}

function licenseAllowsSpatial(info){
  var text=plain(metadataValue(info,'LicenseShortName')+' '+metadataValue(info,'LicenseUrl')+' '+metadataValue(info,'UsageTerms')).toLowerCase();
  if(!text)return false;
  if(text.indexOf('noncommercial')!==-1||text.indexOf('no derivatives')!==-1||text.indexOf('noderivatives')!==-1)return false;
  if(text.indexOf('/by-nc')!==-1||text.indexOf('-nc-')!==-1||text.indexOf('/by-nd')!==-1||text.indexOf('-nd-')!==-1)return false;
  return true;
}

function isHTTPS(value){return /^https:\/\//i.test(String(value||''));}

function looksLikeMP3(mime,url,key){
  var m=String(mime||'').toLowerCase();
  var u=String(url||'').toLowerCase().split('?')[0];
  var k=String(key||'').toLowerCase();
  return m.indexOf('audio/mpeg')!==-1||m.indexOf('audio/mp3')!==-1||/\.mp3$/.test(u)||k==='mp3'||k.indexOf('mp3')!==-1;
}

function selectMP3(info){
  if(!info)return null;
  if(isHTTPS(info.url)&&looksLikeMP3(info.mime,info.url,'')){
    return {url:info.url,mime:info.mime||'audio/mpeg',source:'original'};
  }
  var derivatives=info.derivatives||[];
  for(var i=0;i<derivatives.length;i+=1){
    var d=derivatives[i]||{};
    var url=d.src||d.url||'';
    if(isHTTPS(url)&&looksLikeMP3(d.type||d.mime,url,d.transcodekey||d.key)){
      return {url:url,mime:d.type||d.mime||'audio/mpeg',source:'mp3_derivative'};
    }
  }
  return null;
}

function pageURL(title){
  return 'https://commons.wikimedia.org/wiki/'+encodeURIComponent(String(title||'').replace(/ /g,'_'));
}

function normalizePage(page){
  var info=page&&page.videoinfo&&page.videoinfo[0];
  if(!info||!licenseAllowsSpatial(info))return null;
  var transport=selectMP3(info);
  if(!transport)return null;
  return {
    pageid:page.pageid,
    title:plain(page.title||'Untitled'),
    artist:metadataValue(info,'Artist')||'Wikimedia Commons contributor',
    license:metadataValue(info,'LicenseShortName')||metadataValue(info,'UsageTerms')||'Free license',
    license_url:metadataValue(info,'LicenseUrl'),
    attribution_required:metadataValue(info,'AttributionRequired'),
    file_page:pageURL(page.title),
    audio:transport.url,
    transport_source:transport.source
  };
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

function mediaErrorCode(media){return media&&media.error?media.error.code:null;}

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
  if(trackLabel)trackLabel.textContent='Commons · '+track.title.replace(/^File:/,'')+' · '+track.artist;
  if(playerStatus){
    if(spatialSupported){
      playerStatus.textContent='Wikimedia Commons MP3 passed the live Web Audio PCM probe. Tap Play, then turn Spatial on.';
      playerStatus.className='status good';
    }else{
      playerStatus.textContent='Commons audio is loaded for dry playback, but this device did not prove PCM access for the spatial engine.';
      playerStatus.className='status warn';
    }
  }
}

function testTrack(ui,track,control,diagnostic){
  control.disabled=true;
  control.textContent='TESTING LIVE PCM…';
  diagnostic.textContent='Testing native MP3 playback and Web Audio PCM side by side for about two seconds…';
  diagnostic.className='status';
  probeStream(track.audio,function(result){
    state.lastProbe={pageid:track.pageid,result:result};
    control.disabled=false;
    loadIntoPlayer(track,result.supported);
    if(result.supported){
      control.textContent='SPATIAL PCM VERIFIED ✓';
      diagnostic.textContent='Verified on this device: the Commons stream advances and Web Audio receives non-flat PCM (max deviation '+result.max_analyser_deviation+').';
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
    ui.tracks.appendChild(el('div','status','No iPhone-compatible free-music MP3 candidates were returned in this batch.'));
    return;
  }
  var heading=el('div','status','COMMONS FREE MUSIC · '+state.tracks.length+' TEST TRACKS');
  heading.style.marginTop='12px';
  heading.style.fontWeight='700';
  ui.tracks.appendChild(heading);

  for(var i=0;i<state.tracks.length;i+=1){
    (function(track){
      var row=el('div','metric');
      row.style.marginTop='8px';
      var name=el('b','',track.title.replace(/^File:/,''));
      name.style.display='block';
      row.appendChild(name);
      var meta=el('span','',track.artist+' · '+track.license);
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);
      var rights=el('div','status good','Spatial test candidate: Wikimedia Commons free-license media; check the file page for attribution/share-alike terms.');
      rights.style.marginTop='4px';
      row.appendChild(rights);
      var link=el('a','','Open file + license on Wikimedia Commons');
      link.href=track.file_page;
      link.target='_blank';
      link.rel='noopener';
      link.style.display='inline-block';
      link.style.marginTop='6px';
      link.style.color='inherit';
      row.appendChild(link);
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
  ui.load.textContent='LOADING COMMONS…';
  setStatus(ui,'Requesting a small batch of free-license music files from Wikimedia Commons…','');
  jsonp(buildCatalogURL('{callback}'),function(error,data){
    ui.load.disabled=false;
    ui.load.textContent='RELOAD FREE MUSIC CATALOG';
    if(error){
      state.tracks=[];
      renderTracks(ui);
      setStatus(ui,'Wikimedia Commons catalog request failed: '+error.message,'warn');
      return;
    }
    var pages=data&&data.query&&data.query.pages?data.query.pages:{};
    var tracks=[];
    for(var key in pages){
      if(Object.prototype.hasOwnProperty.call(pages,key)){
        var track=normalizePage(pages[key]);
        if(track)tracks.push(track);
      }
    }
    state.tracks=tracks;
    renderTracks(ui);
    if(tracks.length)setStatus(ui,'Free-music catalog loaded. Choose a track and run the live PCM test on this device.','good');
    else setStatus(ui,'Commons responded, but this batch had no MP3 transport candidates. Reload for another batch.','warn');
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var card=el('div','card');
  card.id='commonsCard';
  var title=el('div','','WIKIMEDIA COMMONS · LIVE SPATIAL TEST');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);
  var status=el('div','status','No account or API key required. This test uses free-license music from Wikimedia Commons.');
  status.id='commonsStatus';
  card.appendChild(status);
  var ui={card:card,status:status,load:null,tracks:null};
  var load=button('LOAD FREE MUSIC TEST CATALOG',function(){loadCatalog(ui);});
  load.id='commonsLoad';
  ui.load=load;
  card.appendChild(load);
  var tracks=el('div','');
  tracks.id='commonsTracks';
  ui.tracks=tracks;
  card.appendChild(tracks);
  var note=el('div','legal','');
  note.appendChild(document.createTextNode('Live-processing test only. Pocket Spatial does not record, save, export, or persist the streamed media. License and attribution details remain linked to each Commons file page.'));
  card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);
  return ui;
}

function boot(){
  var ui=createUI();
  if(!ui)return;
  root.PocketSpatialCommons={
    buildCatalogURL:buildCatalogURL,
    licenseAllowsSpatial:licenseAllowsSpatial,
    selectMP3:selectMP3,
    normalizePage:normalizePage,
    probeStream:probeStream,
    getLastProbe:function(){return state.lastProbe;}
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
