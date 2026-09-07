(function(root){
'use strict';

/*
 * Pocket Spatial free-radio source module.
 * Kept at the historical buffer-probe filename so the existing loader chain
 * can pick it up without disturbing the working cinema DSP graph.
 */

var MIRRORS=[
  'https://de1.api.radio-browser.info',
  'https://nl1.api.radio-browser.info'
];
var REQUEST_LIMIT=90;
var DISPLAY_LIMIT=28;
var VERIFY_MS=1700;
var STALL_MS=9000;

var state={
  audio:null,
  ui:null,
  stations:[],
  currentIndex:-1,
  currentURL:'',
  currentButton:null,
  currentDiagnostic:null,
  active:false,
  autoScan:false,
  failures:0,
  stallTimer:null,
  verifyTimer:null,
  clickedStation:''
};

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

function clean(value){
  return String(value==null?'':value).replace(/\s+/g,' ').replace(/^\s+|\s+$/g,'');
}

function sameURL(a,b){
  return clean(a).replace(/\/$/,'')===clean(b).replace(/\/$/,'');
}

function clearTimers(){
  if(state.stallTimer){root.clearTimeout(state.stallTimer);state.stallTimer=null;}
  if(state.verifyTimer){root.clearTimeout(state.verifyTimer);state.verifyTimer=null;}
}

function setStatus(ui,text,kind){
  if(!ui||!ui.status)return;
  ui.status.textContent=text;
  ui.status.className='status'+(kind?' '+kind:'');
}

function xhrJSON(url,callback){
  if(!root.XMLHttpRequest){callback(new Error('xhr_unavailable'));return;}
  var xhr=new root.XMLHttpRequest();
  try{xhr.open('GET',url,true);}catch(error){callback(error);return;}
  xhr.timeout=12000;
  xhr.onerror=function(){callback(new Error('network_or_cors_error'));};
  xhr.ontimeout=function(){callback(new Error('radio_browser_timeout'));};
  xhr.onload=function(){
    var status=Number(xhr.status)||0;
    if(status<200||status>=300){callback(new Error('radio_browser_http_'+status));return;}
    try{callback(null,JSON.parse(xhr.responseText||'[]'));}
    catch(error){callback(new Error('radio_browser_bad_json'));}
  };
  try{xhr.send();}catch(error){callback(error);}
}

function requestPath(path,callback,mirrorIndex){
  mirrorIndex=Number(mirrorIndex)||0;
  if(mirrorIndex>=MIRRORS.length){callback(new Error('all_radio_browser_mirrors_failed'));return;}
  xhrJSON(MIRRORS[mirrorIndex]+path,function(error,data){
    if(error){requestPath(path,callback,mirrorIndex+1);return;}
    callback(null,data,MIRRORS[mirrorIndex]);
  });
}

function stationPath(kind,query){
  var tail='?hidebroken=true&order=votes&reverse=true&limit='+REQUEST_LIMIT;
  if(kind==='top')return '/json/stations/topvote/'+REQUEST_LIMIT+'?hidebroken=true';
  return '/json/stations/by'+kind+'/'+encodeURIComponent(query)+tail;
}

function codecOkay(station){
  var codec=clean(station&&station.codec).toUpperCase();
  if(Number(station&&station.hls)===1)return true;
  return codec.indexOf('MP3')!==-1||codec.indexOf('MPEG')!==-1||codec.indexOf('AAC')!==-1;
}

function normalizeStation(station){
  if(!station||Number(station.lastcheckok)!==1)return null;
  var url=clean(station.url_resolved||station.url);
  if(!/^https:\/\//i.test(url))return null;
  if(!codecOkay(station))return null;
  var name=clean(station.name)||'Unnamed station';
  var codec=clean(station.codec)||(Number(station.hls)===1?'HLS':'stream');
  var bitrate=Math.max(0,Number(station.bitrate)||0);
  return{
    id:clean(station.stationuuid)||url,
    name:name,
    audio:url,
    homepage:/^https?:\/\//i.test(clean(station.homepage))?clean(station.homepage):'',
    favicon:/^https:\/\//i.test(clean(station.favicon))?clean(station.favicon):'',
    country:clean(station.country)||clean(station.countrycode),
    tags:clean(station.tags),
    codec:codec,
    bitrate:bitrate,
    votes:Math.max(0,Number(station.votes)||0),
    hls:Number(station.hls)===1
  };
}

function mergeStations(groups){
  var out=[];
  var seen={};
  for(var g=0;g<groups.length;g+=1){
    var raw=groups[g]||[];
    for(var i=0;i<raw.length;i+=1){
      var station=normalizeStation(raw[i]);
      if(!station||seen[station.audio])continue;
      seen[station.audio]=true;
      out.push(station);
    }
  }
  out.sort(function(a,b){return b.votes-a.votes;});
  return out.slice(0,DISPLAY_LIMIT);
}

function fetchCatalog(query,callback){
  query=clean(query);
  if(!query){
    requestPath(stationPath('top',''),function(error,data){
      callback(error,error?[]:mergeStations([data]));
    });
    return;
  }
  var remaining=2;
  var errors=[];
  var groups=[[],[]];
  function done(){
    remaining-=1;
    if(remaining>0)return;
    var merged=mergeStations(groups);
    if(!merged.length&&errors.length===2){callback(errors[0],[]);return;}
    callback(null,merged);
  }
  requestPath(stationPath('name',query),function(error,data){if(error)errors.push(error);else groups[0]=data||[];done();});
  requestPath(stationPath('tag',query),function(error,data){if(error)errors.push(error);else groups[1]=data||[];done();});
}

function ensureSpatialOn(){
  var badge=document.getElementById('badge');
  var spatial=document.getElementById('spatial');
  if(spatial&&badge&&badge.className.indexOf(' on')===-1){
    try{spatial.click();}catch(error){}
  }
}

function updateMainTrack(station){
  var label=document.getElementById('track');
  if(!label)return;
  var meta=station.codec+(station.bitrate?' '+station.bitrate+' kbps':'');
  label.textContent=station.name+' · free internet radio · '+meta;
}

function setCurrentControl(buttonNode,diagnostic,text,kind){
  if(state.currentButton&&state.currentButton!==buttonNode){
    state.currentButton.disabled=false;
    if(state.currentButton.textContent.indexOf('FAILED')===-1)state.currentButton.textContent='TRY LIVE + SPATIAL';
  }
  if(state.currentDiagnostic&&state.currentDiagnostic!==diagnostic&&state.currentDiagnostic.className.indexOf('good')===-1){
    state.currentDiagnostic.textContent='Ready to test this stream.';
    state.currentDiagnostic.className='status';
  }
  state.currentButton=buttonNode||null;
  state.currentDiagnostic=diagnostic||null;
  if(buttonNode){buttonNode.disabled=false;buttonNode.textContent='TESTING STREAM…';}
  if(diagnostic){diagnostic.textContent=text||'Opening stream…';diagnostic.className='status'+(kind?' '+kind:'');}
}

function clickCount(station){
  if(!station||!station.id||state.clickedStation===station.id)return;
  state.clickedStation=station.id;
  requestPath('/json/url/'+encodeURIComponent(station.id),function(){});
}

function currentMatches(){
  if(!state.active||!state.audio||!state.currentURL)return false;
  return sameURL(state.audio.src,state.currentURL)||sameURL(state.audio.currentSrc,state.currentURL);
}

function markReady(){
  if(!currentMatches()||state.audio.paused||state.audio.readyState<2)return;
  var station=state.stations[state.currentIndex];
  clearTimers();
  state.autoScan=false;
  state.failures=0;
  if(state.currentButton)state.currentButton.textContent='PLAYING · SPATIAL READY ✓';
  if(state.currentDiagnostic){
    state.currentDiagnostic.textContent='SPATIAL READY ✓ Stream stayed alive through the shared Pocket Spatial audio element. Cinema processing is on.';
    state.currentDiagnostic.className='status good';
  }
  setStatus(state.ui,'Found a spatial-ready free stream: '+station.name+'. Your receiver gets the same Pocket Spatial cinema-matrix output as local/Audius playback.','good');
  clickCount(station);
}

function failCurrent(reason){
  clearTimers();
  var station=state.stations[state.currentIndex];
  if(state.currentButton){state.currentButton.disabled=false;state.currentButton.textContent='FAILED · TRY AGAIN';}
  if(state.currentDiagnostic){
    state.currentDiagnostic.textContent='Rejected: '+reason+'.';
    state.currentDiagnostic.className='status warn';
  }
  if(!state.autoScan)return;
  state.failures+=1;
  if(state.failures>=state.stations.length){
    state.autoScan=false;
    state.active=false;
    setStatus(state.ui,'Scanner tried every candidate in this batch and none survived the iPhone/Web Audio path. Try another genre or reload the catalog.','warn');
    return;
  }
  root.setTimeout(function(){
    var next=(state.currentIndex+1)%state.stations.length;
    var entry=state.ui&&state.ui.entries?state.ui.entries[next]:null;
    playStation(next,entry&&entry.button,entry&&entry.diagnostic,true);
  },300);
}

function playStation(index,buttonNode,diagnostic,isAuto){
  if(!state.audio||!state.stations.length)return;
  if(index<0)index=0;
  if(index>=state.stations.length)index=0;
  var station=state.stations[index];
  state.currentIndex=index;
  state.currentURL=station.audio;
  state.active=true;
  state.autoScan=!!isAuto||state.autoScan;
  clearTimers();
  setCurrentControl(buttonNode,diagnostic,'Testing HTTPS/CORS playback into Pocket Spatial…','');
  updateMainTrack(station);
  try{state.audio.pause();}catch(error){}
  state.audio.crossOrigin='anonymous';
  state.audio.setAttribute('crossorigin','anonymous');
  state.audio.src=station.audio;
  try{state.audio.load();}catch(error2){}
  ensureSpatialOn();
  setStatus(state.ui,(state.autoScan?'Scanner testing: ':'Testing: ')+station.name+' · '+station.codec+(station.bitrate?' '+station.bitrate+' kbps':''),'');
  try{
    var promise=state.audio.play();
    if(promise&&typeof promise.then==='function'){
      promise.catch(function(error){
        if(currentMatches())failCurrent('playback start failed'+(error&&error.message?' · '+error.message:''));
      });
    }
  }catch(error3){
    failCurrent('playback exception');
  }
}

function startScan(){
  if(!state.stations.length){loadCatalog(state.ui,true);return;}
  state.autoScan=true;
  state.failures=0;
  var start=state.currentIndex>=0?(state.currentIndex+1)%state.stations.length:0;
  var entry=state.ui.entries[start];
  playStation(start,entry&&entry.button,entry&&entry.diagnostic,true);
}

function nextStation(){
  if(!state.stations.length)return;
  state.autoScan=false;
  state.failures=0;
  var next=(state.currentIndex+1)%state.stations.length;
  var entry=state.ui.entries[next];
  playStation(next,entry&&entry.button,entry&&entry.diagnostic,false);
}

function bindAudioEvents(){
  if(!state.audio)return;

  /* Capture failures before the older Audius listener can mistake a radio failure for an Audius failure. */
  state.audio.addEventListener('error',function(event){
    if(!currentMatches())return;
    if(event&&event.stopImmediatePropagation)event.stopImmediatePropagation();
    failCurrent('stream, codec, HTTPS, or CORS failure');
  },true);

  state.audio.addEventListener('stalled',function(event){
    if(!currentMatches())return;
    if(event&&event.stopImmediatePropagation)event.stopImmediatePropagation();
    if(state.stallTimer)root.clearTimeout(state.stallTimer);
    state.stallTimer=root.setTimeout(function(){if(currentMatches())failCurrent('stream stalled for too long');},STALL_MS);
  },true);

  state.audio.addEventListener('ended',function(event){
    if(!currentMatches())return;
    if(event&&event.stopImmediatePropagation)event.stopImmediatePropagation();
    failCurrent('stream ended');
  },true);

  state.audio.addEventListener('playing',function(){
    if(!currentMatches())return;
    clearTimers();
    state.verifyTimer=root.setTimeout(markReady,VERIFY_MS);
  });

  state.audio.addEventListener('loadstart',function(){
    if(!state.active)return;
    if(state.audio.src&&!sameURL(state.audio.src,state.currentURL)){
      state.active=false;
      state.autoScan=false;
      clearTimers();
    }
  },true);
}

function renderStations(ui){
  while(ui.results.firstChild)ui.results.removeChild(ui.results.firstChild);
  ui.entries=[];
  if(!state.stations.length){
    ui.results.appendChild(el('div','status','No HTTPS MP3/AAC/HLS candidates survived the first filter. Try another search.'));
    return;
  }

  var heading=el('div','status','RADIO BROWSER · '+state.stations.length+' HTTPS STREAM CANDIDATES');
  heading.style.marginTop='12px';
  heading.style.fontWeight='700';
  ui.results.appendChild(heading);

  for(var i=0;i<state.stations.length;i+=1){
    (function(station,index){
      var row=el('div','metric');
      row.style.marginTop='8px';

      var name=el('b','',station.name);
      name.style.display='block';
      row.appendChild(name);

      var bits=[];
      if(station.country)bits.push(station.country);
      bits.push(station.codec+(station.bitrate?' '+station.bitrate+' kbps':''));
      if(station.tags){
        var tags=station.tags.split(',').slice(0,4).join(', ');
        if(tags)bits.push(tags);
      }
      var meta=el('span','',bits.join(' · '));
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);

      var diagnostic=el('div','status','Ready to test this stream. HTTPS and a Safari-friendly codec passed the first filter.');
      diagnostic.style.marginTop='5px';
      row.appendChild(diagnostic);

      if(station.homepage){
        var link=el('a','','Station website');
        link.href=station.homepage;
        link.target='_blank';
        link.rel='noopener';
        link.style.display='inline-block';
        link.style.marginTop='6px';
        link.style.color='inherit';
        row.appendChild(link);
      }

      var play=button('TRY LIVE + SPATIAL',function(){
        state.autoScan=true;
        state.failures=0;
        playStation(index,play,diagnostic,true);
      });
      play.style.marginTop='8px';
      row.appendChild(play);

      ui.entries[index]={button:play,diagnostic:diagnostic};
      ui.results.appendChild(row);
    }(state.stations[i],i));
  }
}

function loadCatalog(ui,scanAfter){
  if(!ui)return;
  var query=clean(ui.query.value);
  ui.load.disabled=true;
  ui.load.textContent=query?'SEARCHING FREE RADIO…':'LOADING TOP FREE RADIO…';
  setStatus(ui,query?'Searching station names and tags for “'+query+'”…':'Loading highly-voted free radio stations…','');
  fetchCatalog(query,function(error,stations){
    ui.load.disabled=false;
    ui.load.textContent='SEARCH / RELOAD FREE RADIO';
    if(error){
      state.stations=[];
      renderStations(ui);
      setStatus(ui,'Radio Browser could not be reached through the available mirrors: '+error.message+'.','warn');
      return;
    }
    state.stations=stations;
    state.currentIndex=-1;
    state.failures=0;
    renderStations(ui);
    if(stations.length){
      setStatus(ui,'Found '+stations.length+' HTTPS MP3/AAC/HLS candidates. Tap SCAN and Pocket Spatial will automatically reject streams that fail on this iPhone.','good');
      if(scanAfter)startScan();
    }else{
      setStatus(ui,'Radio Browser answered, but no candidates survived the HTTPS/codec filter. Try a different genre or station name.','warn');
    }
  });
}

function quickSearch(ui,value){
  ui.query.value=value;
  loadCatalog(ui,false);
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;

  var sub=document.querySelector('.sub');
  if(sub)sub.textContent='Live cinema-style spatial processor · Audius, free internet radio, and local audio';

  var card=el('div','card');
  card.id='radioBrowserSpatialCard';

  var title=el('div','','FREE RADIO · SPATIAL STREAM SCANNER');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);

  var status=el('div','status','Radio Browser supplies free station listings and resolved stream URLs. Pocket Spatial keeps only HTTPS MP3/AAC/HLS candidates, then tests them on the actual iPhone audio path.');
  card.appendChild(status);

  var query=el('input','');
  query.type='text';
  query.placeholder='Genre or station name… (blank = top stations)';
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
  card.appendChild(query);

  var ui={card:card,status:status,query:query,load:null,scan:null,next:null,results:null,entries:[]};
  state.ui=ui;

  query.addEventListener('keydown',function(event){if((event.key||'')==='Enter')loadCatalog(ui,false);});

  var quick=el('div','row');
  var rock=button('ROCK',function(){quickSearch(ui,'rock');});
  var electronic=button('ELECTRONIC',function(){quickSearch(ui,'electronic');});
  var jazz=button('JAZZ',function(){quickSearch(ui,'jazz');});
  quick.appendChild(rock);quick.appendChild(electronic);quick.appendChild(jazz);
  card.appendChild(quick);

  var load=button('LOAD TOP FREE RADIO',function(){loadCatalog(ui,false);});
  ui.load=load;
  card.appendChild(load);

  var scan=button('SCAN FOR A SPATIAL-READY STATION',function(){startScan();});
  scan.className='primary';
  ui.scan=scan;
  card.appendChild(scan);

  var next=button('NEXT STATION',function(){nextStation();});
  ui.next=next;
  card.appendChild(next);

  var results=el('div','');
  ui.results=results;
  card.appendChild(results);

  var note=el('div','legal','Free source: Radio Browser. Pocket Spatial does not record or save radio audio. A station is marked SPATIAL READY only after its HTTPS stream survives playback through the shared cross-origin audio element long enough to reach the cinema-processing path. Individual stations can disappear or change formats at any time.');
  note.style.marginTop='9px';
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
  root.PocketSpatialRadioBrowser={
    load:function(query){state.ui.query.value=query||'';loadCatalog(state.ui,false);},
    scan:startScan,
    next:nextStation,
    getStations:function(){return state.stations.slice();},
    ui:state.ui
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
