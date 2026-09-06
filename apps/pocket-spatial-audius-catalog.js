(function(root){
'use strict';

var API='https://api.audius.co/v1';
var APP_NAME='PocketSpatial';
var API_LIMIT=100;
var DISPLAY_RESULTS=24;
var DISCOVERY_QUERIES=['CC BY','Creative Commons Attribution','creative commons','CC0'];
var state={tracks:[]};

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

function cleanText(value){
  return String(value==null?'':value).replace(/\s+/g,' ').replace(/^\s+|\s+$/g,'');
}

function licenseAllowsSpatial(track){
  var text=cleanText(track&&track.license).toLowerCase().replace(/_/g,'-');
  if(!text)return false;
  if(text.indexOf('all rights reserved')!==-1)return false;
  if(text.indexOf('noncommercial')!==-1||text.indexOf('non-commercial')!==-1)return false;
  if(text.indexOf('no derivatives')!==-1||text.indexOf('noderivatives')!==-1||text.indexOf('no-derivatives')!==-1)return false;
  if(text.indexOf('by-nc')!==-1||text.indexOf('-nc-')!==-1||text.indexOf(' nc ')!==-1)return false;
  if(text.indexOf('by-nd')!==-1||text.indexOf('-nd-')!==-1||/\bnd\b/.test(text))return false;
  if(text.indexOf('cc0')!==-1||text.indexOf('public domain')!==-1)return true;
  if(text.indexOf('creative commons attribution')!==-1)return true;
  if(text.indexOf('cc by')!==-1||text.indexOf('cc-by')!==-1||text.indexOf('by-sa')!==-1)return true;
  return false;
}

function isPlayable(track){
  var duration;
  if(!track||!track.id)return false;
  if(track.is_streamable===false)return false;
  if(track.is_stream_gated===true)return false;
  if(track.stream_conditions)return false;
  if(track.access&&track.access.stream===false)return false;
  duration=Number(track.duration)||0;
  if(duration>180)return false;
  return licenseAllowsSpatial(track);
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
  var duration=Number(track.duration)||0;
  var user=track.user||{};
  return{
    pageid:'audius:'+String(track.id),
    source:'Audius',
    title:cleanText(track.title)||'Untitled Audius track',
    artist:cleanText(user.name||user.handle)||'Audius artist',
    license:cleanText(track.license),
    duration:duration,
    file_page:pageURL(track),
    audio:streamURL(track.id),
    audius_id:String(track.id)
  };
}

function buildCatalogURL(query){
  var q=cleanText(query)||DISCOVERY_QUERIES[0];
  return API+'/tracks/search?query='+encodeURIComponent(q)+'&limit='+API_LIMIT+'&app_name='+encodeURIComponent(APP_NAME);
}

function xhrJSON(url,callback){
  if(!root.XMLHttpRequest){callback(new Error('xhr_unavailable'));return;}
  var xhr=new root.XMLHttpRequest();
  try{xhr.open('GET',url,true);}catch(e){callback(e);return;}
  xhr.timeout=12000;
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

function renderTracks(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  if(!state.tracks.length){
    ui.tracks.appendChild(el('div','status','No derivative-permitting Audius tracks were returned. Pocket Spatial will try several rights-safe searches when the box is blank.'));
    return;
  }
  var heading=el('div','status','AUDIUS · '+state.tracks.length+' BUFFERED IMMERSIVE CANDIDATES');
  heading.style.marginTop='12px';
  heading.style.fontWeight='700';
  ui.tracks.appendChild(heading);
  for(var i=0;i<state.tracks.length;i+=1){
    (function(track){
      var row=el('div','metric');
      row.style.marginTop='8px';
      var name=el('b','',track.title);
      name.style.display='block';
      row.appendChild(name);
      var meta=el('span','',track.artist+' · '+track.license+(track.duration?' · '+Math.round(track.duration)+' s':''));
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);
      var rights=el('div','status good','Derivative-permitting Audius license verified. NC, NoDerivatives, All Rights Reserved, and gated tracks are excluded.');
      rights.style.marginTop='4px';
      row.appendChild(rights);
      var link=el('a','','Open this track on Audius');
      link.href=track.file_page;
      link.target='_blank';
      link.rel='noopener';
      link.style.display='inline-block';
      link.style.marginTop='6px';
      link.style.color='inherit';
      row.appendChild(link);
      var diagnostic=el('div','status','Ready to fetch the Audius MP3 into temporary memory.');
      diagnostic.style.marginTop='6px';
      row.appendChild(diagnostic);
      var play=button('BUFFER + PLAY IMMERSIVE',function(){
        var player=root.PocketSpatialBufferedPlayer||root.PocketSpatialBufferedCommons;
        if(!player){
          diagnostic.textContent='The buffered immersive engine did not load.';
          diagnostic.className='status warn';
          return;
        }
        player.toggle(track,play,diagnostic);
      });
      play.style.marginTop='8px';
      row.appendChild(play);
      ui.tracks.appendChild(row);
    }(state.tracks[i]));
  }
}

function showTracks(ui,tracks,label){
  state.tracks=tracks||[];
  ui.load.disabled=false;
  ui.load.textContent='SEARCH / RELOAD AUDIUS';
  renderTracks(ui);
  if(state.tracks.length){
    setStatus(ui,'Audius connected through “'+cleanText(label)+'” with derivative-permitting tracks. Pick one and tap BUFFER + PLAY IMMERSIVE.','good');
  }else{
    setStatus(ui,'Audius responded, but no derivative-permitting <=180 s tracks were found in the rights-safe discovery searches.','warn');
  }
}

function finishCatalog(ui,error,data,query){
  if(error){
    state.tracks=[];
    ui.load.disabled=false;
    ui.load.textContent='SEARCH / RELOAD AUDIUS';
    renderTracks(ui);
    setStatus(ui,'Audius catalog request failed: '+error.message,'warn');
    return;
  }
  showTracks(ui,collectTracks(data),query);
}

function loadDiscovery(ui,index){
  var query;
  if(index>=DISCOVERY_QUERIES.length){
    showTracks(ui,[],'rights-safe discovery');
    return;
  }
  query=DISCOVERY_QUERIES[index];
  setStatus(ui,'Audius connected. Checking rights-safe search '+(index+1)+'/'+DISCOVERY_QUERIES.length+': “'+query+'”…','');
  xhrJSON(buildCatalogURL(query),function(error,data){
    var tracks;
    if(error){
      if(index+1<DISCOVERY_QUERIES.length){loadDiscovery(ui,index+1);return;}
      finishCatalog(ui,error,data,query);
      return;
    }
    tracks=collectTracks(data);
    if(tracks.length){showTracks(ui,tracks,query);return;}
    loadDiscovery(ui,index+1);
  });
}

function loadCatalog(ui){
  var query=ui.query?cleanText(ui.query.value):'';
  ui.load.disabled=true;
  ui.load.textContent=query?'SEARCHING AUDIUS…':'DISCOVERING AUDIUS…';
  if(query){
    setStatus(ui,'Searching Audius for “'+query+'” and checking creator licenses…','');
    xhrJSON(buildCatalogURL(query),function(error,data){finishCatalog(ui,error,data,query);});
    return;
  }
  setStatus(ui,'Searching Audius more deeply for explicit derivative-permitting licenses…','');
  loadDiscovery(ui,0);
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var card=el('div','card');
  card.id='audiusBufferedCard';
  var title=el('div','','AUDIUS · IMMERSIVE MUSIC');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);
  var status=el('div','status','Second live source. Pocket Spatial queries Audius directly and only offers tracks with an affirmative derivative-permitting license.');
  status.id='audiusBufferedStatus';
  card.appendChild(status);
  var query=el('input','');
  query.type='text';
  query.placeholder='Artist, track, genre… (blank = rights-safe discovery)';
  query.id='audiusBufferedQuery';
  query.autocapitalize='off';
  query.autocomplete='off';
  query.style.width='100%';
  query.style.boxSizing='border-box';
  query.style.margin='8px 0';
  var ui={card:card,status:status,query:query,load:null,tracks:null};
  card.appendChild(query);
  var load=button('LOAD AUDIUS MUSIC',function(){loadCatalog(ui);});
  load.id='audiusBufferedLoad';
  ui.load=load;
  card.appendChild(load);
  var tracks=el('div','');
  tracks.id='audiusBufferedTracks';
  ui.tracks=tracks;
  card.appendChild(tracks);
  var limits=(root.PocketSpatialBufferedPlayer||root.PocketSpatialBufferedCommons);
  limits=limits&&limits.limits;
  var limitText=limits?Math.round(limits.compressedBytes/1048576)+' MB / '+limits.durationSeconds+' s':'conservative iPhone 6';
  var note=el('div','legal','Temporary-memory playback only. '+limitText+' safety ceiling. Nothing is recorded, exported, or persisted by Pocket Spatial. Creator-selected Audius restrictions remain in force.');
  note.style.marginTop='8px';
  card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);
  return ui;
}

function boot(){
  var ui=createUI();
  if(!ui)return;
  root.PocketSpatialAudiusCatalog={
    buildCatalogURL:buildCatalogURL,
    licenseAllowsSpatial:licenseAllowsSpatial,
    isPlayable:isPlayable,
    normalizeTrack:normalizeTrack,
    streamURL:streamURL,
    discoveryQueries:DISCOVERY_QUERIES.slice(0),
    ui:ui
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
