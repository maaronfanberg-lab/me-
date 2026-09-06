(function(root){
'use strict';

var SEARCH_API='https://archive.org/advancedsearch.php';
var METADATA_API='https://archive.org/metadata/';
var DOWNLOAD_BASE='https://archive.org/download/';
var DEFAULT_QUERY='';
var state={tracks:[],lastProbe:null};

function el(tag,className,text){var node=document.createElement(tag);if(className)node.className=className;if(text!=null)node.textContent=text;return node;}
function button(text,handler){var b=el('button','',text);b.type='button';b.addEventListener('click',handler);return b;}
function setStatus(ui,text,kind){ui.status.textContent=text;ui.status.className='status'+(kind?' '+kind:'');}

function cleanQuery(value){return String(value||'').replace(/[^a-zA-Z0-9 _-]+/g,' ').replace(/\s+/g,' ').replace(/^\s+|\s+$/g,'');}

function buildSearchURL(query){
  var q='mediatype:(audio) AND licenseurl:http*by*';
  var term=cleanQuery(query);
  if(term)q+=' AND ('+term+')';
  return SEARCH_API+'?q='+encodeURIComponent(q)+
    '&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=creator&fl%5B%5D=licenseurl'+
    '&sort%5B%5D=downloads+desc&rows=30&page=1&output=json';
}

function requestJSON(url,callback){
  var xhr=new XMLHttpRequest(),finished=false;
  function finish(error,data){if(finished)return;finished=true;callback(error,data);}
  xhr.open('GET',url,true);xhr.timeout=18000;
  xhr.onreadystatechange=function(){
    if(xhr.readyState!==4||finished)return;
    if(xhr.status<200||xhr.status>=300){finish(new Error('archive_http_'+xhr.status));return;}
    var data=null;try{data=JSON.parse(xhr.responseText);}catch(e){finish(new Error('archive_invalid_json'));return;}
    finish(null,data);
  };
  xhr.ontimeout=function(){finish(new Error('archive_timeout'));};
  xhr.onerror=function(){finish(new Error('archive_network_error'));};
  xhr.send(null);
}

function firstValue(value){if(value&&typeof value!=='string'&&typeof value.length==='number')return value.length?String(value[0]):'';return String(value||'');}

function isExactCCBY(value){
  var url=firstValue(value).toLowerCase().replace(/\?.*$/,'').replace(/#.*$/,'').replace(/\/+$/,'');
  return /^https?:\/\/creativecommons\.org\/licenses\/by\/[0-9.]+$/.test(url);
}

function encodePath(value){var parts=String(value||'').split('/');for(var i=0;i<parts.length;i+=1)parts[i]=encodeURIComponent(parts[i]);return parts.join('/');}

function selectMP3(files){
  files=files||[];var fallback=null;
  for(var i=0;i<files.length;i+=1){
    var file=files[i]||{},name=String(file.name||'');
    if(!/\.mp3$/i.test(name))continue;
    if(file.private===true||String(file.private||'').toLowerCase()==='true')continue;
    if(!fallback)fallback=file;
    if(String(file.source||'').toLowerCase()==='original')return file;
  }
  return fallback;
}

function itemFromMetadata(data){
  if(!data||!data.metadata)return null;
  var metadata=data.metadata;
  if(!isExactCCBY(metadata.licenseurl))return null;
  var identifier=String(metadata.identifier||''),file=selectMP3(data.files);
  if(!identifier||!file||!file.name)return null;
  return{identifier:identifier,title:firstValue(metadata.title)||identifier,creator:firstValue(metadata.creator)||'Unknown creator',licenseurl:firstValue(metadata.licenseurl),audio:DOWNLOAD_BASE+encodeURIComponent(identifier)+'/'+encodePath(file.name),source:'https://archive.org/details/'+encodeURIComponent(identifier),filename:String(file.name),format:String(file.format||'MP3')};
}

function hydrateDocs(docs,callback){
  docs=(docs||[]).slice(0,12);
  if(!docs.length){callback([]);return;}
  var pending=docs.length,results=[];
  function done(){pending-=1;if(pending===0)callback(results);}
  for(var i=0;i<docs.length;i+=1){
    (function(doc){
      var id=String((doc&&doc.identifier)||'');
      if(!id){done();return;}
      requestJSON(METADATA_API+encodeURIComponent(id),function(error,data){if(!error){var item=itemFromMetadata(data);if(item)results.push(item);}done();});
    }(docs[i]));
  }
}

function hiddenAudio(url,crossOrigin,muted){
  var media=document.createElement('audio');media.preload='auto';media.setAttribute('playsinline','playsinline');media.style.position='absolute';media.style.left='-9999px';media.style.width='1px';media.style.height='1px';
  if(crossOrigin)media.crossOrigin='anonymous';if(muted)media.muted=true;media.src=url;document.body.appendChild(media);return media;
}
function removeNode(node){if(node&&node.parentNode)node.parentNode.removeChild(node);}
function safePlay(media){try{var result=media.play();if(result&&typeof result['catch']==='function')result['catch'](function(){});}catch(e){}}
function mediaErrorCode(media){return media&&media.error?media.error.code:null;}

function probeStream(url,callback){
  var AC=root.AudioContext||root.webkitAudioContext;
  if(!AC){callback({supported:false,reason:'web_audio_unavailable'});return;}
  var nativeMedia=hiddenAudio(url,false,true),tappedMedia=hiddenAudio(url,true,false);
  var ctx=null,source=null,analyser=null,silent=null,timer=null,ticks=0,maxDeviation=0;
  function cleanup(){if(timer)clearInterval(timer);try{nativeMedia.pause();}catch(e){}try{tappedMedia.pause();}catch(e2){}removeNode(nativeMedia);removeNode(tappedMedia);try{if(ctx&&ctx.close)ctx.close();}catch(e3){}}
  try{
    ctx=new AC();source=ctx.createMediaElementSource(tappedMedia);analyser=ctx.createAnalyser();analyser.fftSize=256;analyser.smoothingTimeConstant=0;silent=ctx.createGain();silent.gain.value=0;source.connect(analyser);analyser.connect(silent);silent.connect(ctx.destination);if(ctx.state==='suspended'&&ctx.resume)ctx.resume();
  }catch(error){cleanup();callback({supported:false,reason:'probe_graph_failed',detail:error.message||String(error)});return;}
  var data=new Uint8Array(analyser.fftSize);safePlay(nativeMedia);safePlay(tappedMedia);
  timer=setInterval(function(){
    ticks+=1;
    try{analyser.getByteTimeDomainData(data);for(var i=0;i<data.length;i+=1){var d=Math.abs(data[i]-128);if(d>maxDeviation)maxDeviation=d;}}catch(e){}
    if(ticks>=20){
      var nativeAdvanced=nativeMedia.currentTime>0.10,tappedAdvanced=tappedMedia.currentTime>0.10,pcmFlowing=maxDeviation>2;
      var result={supported:nativeAdvanced&&tappedAdvanced&&pcmFlowing,native_stream_playing:nativeAdvanced,cors_stream_playing:tappedAdvanced,web_audio_pcm_flowing:pcmFlowing,max_analyser_deviation:maxDeviation,native_media_error:mediaErrorCode(nativeMedia),tapped_media_error:mediaErrorCode(tappedMedia)};
      if(!nativeAdvanced)result.reason='native_stream_did_not_advance';else if(!tappedAdvanced)result.reason='cors_media_did_not_advance';else if(!pcmFlowing)result.reason='web_audio_pcm_flatline';else result.reason='spatial_pcm_available';
      cleanup();callback(result);
    }
  },100);
}

function loadIntoPlayer(track,spatialSupported){
  var player=document.getElementById('audio'),trackLabel=document.getElementById('track'),playerStatus=document.getElementById('status');
  if(!player)return;try{player.pause();}catch(e){}player.removeAttribute('src');if(spatialSupported)player.crossOrigin='anonymous';else player.removeAttribute('crossorigin');player.src=track.audio;try{player.load();}catch(e2){}
  if(trackLabel)trackLabel.textContent='Internet Archive · '+track.title+' · '+track.creator;
  if(playerStatus){if(spatialSupported){playerStatus.textContent='Internet Archive MP3 passed the live Web Audio PCM probe. Tap Play, then turn Spatial on.';playerStatus.className='status good';}else{playerStatus.textContent='Internet Archive MP3 is loaded for dry playback, but this device did not prove PCM access for the spatial engine.';playerStatus.className='status warn';}}
}

function testTrack(ui,track,control,diagnostic){
  control.disabled=true;control.textContent='TESTING LIVE PCM…';diagnostic.textContent='Testing direct Archive MP3 playback and Web Audio PCM side by side for about two seconds…';diagnostic.className='status';
  probeStream(track.audio,function(result){
    state.lastProbe={identifier:track.identifier,result:result};control.disabled=false;loadIntoPlayer(track,result.supported);
    if(result.supported){control.textContent='SPATIAL PCM VERIFIED ✓';diagnostic.textContent='Verified on this device: the Archive MP3 advances and Web Audio receives non-flat PCM (max deviation '+result.max_analyser_deviation+').';diagnostic.className='status good';}
    else if(result.native_stream_playing){control.textContent='DRY STREAM ONLY';diagnostic.textContent='The MP3 plays, but the spatial path was not verified ('+result.reason+'). Loaded dry instead.';diagnostic.className='status warn';}
    else{control.textContent='RETRY STREAM TEST';diagnostic.textContent='The live stream test did not establish playback ('+result.reason+'). Nothing is being claimed as spatial.';diagnostic.className='status warn';}
  });
}

function renderTracks(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  if(!state.tracks.length){ui.tracks.appendChild(el('div','status','No exact-CC-BY MP3 items were found in this test search.'));return;}
  var heading=el('div','status','INTERNET ARCHIVE TEST CATALOG · '+state.tracks.length+' ITEMS');heading.style.marginTop='12px';heading.style.fontWeight='700';ui.tracks.appendChild(heading);
  for(var i=0;i<state.tracks.length;i+=1){
    (function(track){
      var row=el('div','metric');row.style.marginTop='8px';var name=el('b','',track.title);name.style.display='block';row.appendChild(name);
      var meta=el('span','',track.creator+' · CC BY · '+track.format);meta.style.display='block';meta.style.marginTop='4px';row.appendChild(meta);
      var rights=el('div','status good','Spatial test candidate: live item metadata resolves to an exact Creative Commons Attribution license.');rights.style.marginTop='4px';row.appendChild(rights);
      var link=el('a','','Open original on Internet Archive');link.href=track.source;link.target='_blank';link.rel='noopener';link.style.display='inline-block';link.style.marginTop='6px';link.style.color='inherit';row.appendChild(link);
      var diagnostic=el('div','status','Not tested on this device yet.');diagnostic.style.marginTop='6px';row.appendChild(diagnostic);
      var test=button('TEST + LOAD LIVE STREAM',function(){testTrack(ui,track,test,diagnostic);});test.style.marginTop='8px';row.appendChild(test);ui.tracks.appendChild(row);
    }(state.tracks[i]));
  }
}

function loadCatalog(ui){
  ui.load.disabled=true;ui.load.textContent='SEARCHING ARCHIVE…';setStatus(ui,'Discovering Creative Commons audio, then rechecking each item for exact CC BY + MP3…','');
  requestJSON(buildSearchURL(ui.query.value),function(error,data){
    if(error){ui.load.disabled=false;ui.load.textContent='SEARCH OPEN AUDIO';state.tracks=[];renderTracks(ui);setStatus(ui,'Internet Archive search failed: '+error.message,'warn');return;}
    var docs=(data&&data.response&&data.response.docs)||[];
    hydrateDocs(docs,function(items){ui.load.disabled=false;ui.load.textContent='SEARCH OPEN AUDIO';state.tracks=items;renderTracks(ui);if(items.length)setStatus(ui,'Rights-filtered Archive items loaded. Pick one and run the live PCM test on this device.','good');else setStatus(ui,'Archive search answered, but none of the returned items survived exact-license + MP3 verification.','warn');});
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');if(!hero||!hero.parentNode)return null;
  var card=el('div','card');card.id='archiveCard';var title=el('div','','INTERNET ARCHIVE · NO-ACCOUNT LIVE TEST');title.style.fontWeight='700';title.style.letterSpacing='.06em';title.style.fontSize='12px';card.appendChild(title);
  var status=el('div','status','No login or API key required. Search is broad, but Pocket Spatial only offers items whose live metadata resolves to exact CC BY and contains an MP3.');status.id='archiveStatus';card.appendChild(status);
  var query=document.createElement('input');query.type='search';query.id='archiveQuery';query.value=DEFAULT_QUERY;query.placeholder='Optional search, e.g. ambient';query.setAttribute('aria-label','Internet Archive audio search');query.style.width='100%';query.style.minHeight='46px';query.style.borderRadius='12px';query.style.border='1px solid #293347';query.style.background='#0b1018';query.style.color='#edf2fb';query.style.padding='10px 12px';query.style.fontSize='16px';query.style.marginTop='10px';card.appendChild(query);
  var load=button('SEARCH OPEN AUDIO',function(){loadCatalog(ui);});load.id='archiveLoad';card.appendChild(load);var tracks=el('div','');tracks.id='archiveTracks';card.appendChild(tracks);
  var note=el('div','legal','');note.appendChild(document.createTextNode('Development test only. Audio is streamed directly from archive.org, never copied or proxied by Pocket Spatial. Broad search results are not trusted: the app re-fetches each item’s metadata and requires an exact CC BY license before displaying it.'));card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);return {card:card,status:status,query:query,load:load,tracks:tracks};
}

function boot(){var ui=createUI();if(!ui)return;root.PocketSpatialInternetArchive={buildSearchURL:buildSearchURL,isExactCCBY:isExactCCBY,selectMP3:selectMP3,itemFromMetadata:itemFromMetadata,probeStream:probeStream,getLastProbe:function(){return state.lastProbe;}};}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();

}(this));
