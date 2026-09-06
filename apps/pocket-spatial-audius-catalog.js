(function(root){
'use strict';

var API='https://api.audius.co/v1';
var LIMIT=50;
var state={tracks:[]};

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

function isHTTPS(value){return /^https:\/\//i.test(String(value||''));}

function buildCatalogURL(){return API+'/tracks/remixables?limit='+LIMIT;}

function streamURL(id){return API+'/tracks/'+encodeURIComponent(String(id||''))+'/stream';}

function trackPage(track){
  var permalink=String(track&&track.permalink||'');
  if(isHTTPS(permalink))return permalink;
  if(permalink){
    if(permalink.charAt(0)!=='/')permalink='/'+permalink;
    return 'https://audius.co'+permalink;
  }
  return 'https://audius.co';
}

function licenseValue(track){
  return plain(track&&(track.license||track.license_type||track.licenseType)||'');
}

function licenseAllowsSpatial(track){
  var value=licenseValue(track).toLowerCase();
  if(!value)return true;
  if(value.indexOf('no derivatives')!==-1||value.indexOf('noderivatives')!==-1)return false;
  if(value.indexOf('-nd')!==-1||value.indexOf('_nd')!==-1||/(^|[^a-z])nd([^a-z]|$)/.test(value))return false;
  if(value.indexOf('all rights reserved')!==-1)return false;
  return true;
}

function artistName(track){
  var user=track&&track.user||{};
  return plain(user.name||user.display_name||user.displayName||user.handle||'Audius artist');
}

function streamable(track){
  if(!track)return false;
  if(track.is_streamable===false||track.isStreamable===false)return false;
  if(String(track.is_streamable).toLowerCase()==='false'||String(track.isStreamable).toLowerCase()==='false')return false;
  return true;
}

function normalizeTrack(track){
  if(!track||track.id==null||!streamable(track)||!licenseAllowsSpatial(track))return null;
  var duration=Number(track.duration)||0;
  return{
    pageid:'audius:'+String(track.id),
    id:String(track.id),
    title:plain(track.title||'Untitled Audius track'),
    artist:artistName(track),
    license:licenseValue(track)||'Audius remixable',
    file_page:trackPage(track),
    audio:streamURL(track.id),
    duration:duration,
    provider:'Audius',
    sourceLabel:'Audius'
  };
}

function responseItems(data){
  if(!data)return[];
  if(Object.prototype.toString.call(data.data)==='[object Array]')return data.data;
  if(data.data&&Object.prototype.toString.call(data.data.tracks)==='[object Array]')return data.data.tracks;
  if(Object.prototype.toString.call(data.tracks)==='[object Array]')return data.tracks;
  return[];
}

function normalizedTracks(data){
  var source=responseItems(data),out=[];
  for(var i=0;i<source.length;i+=1){
    var track=normalizeTrack(source[i]);
    if(track)out.push(track);
  }
  return out;
}

root.PocketSpatialAudiusCatalogAPI={
  buildCatalogURL:buildCatalogURL,
  streamURL:streamURL,
  trackPage:trackPage,
  licenseAllowsSpatial:licenseAllowsSpatial,
  normalizeTrack:normalizeTrack,
  normalizedTracks:normalizedTracks
};

if(typeof document==='undefined')return;

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

function renderTracks(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  if(!state.tracks.length){
    ui.tracks.appendChild(el('div','status','Audius returned no compatible remixable tracks in this batch. Reload to try again.'));
    return;
  }
  var heading=el('div','status','AUDIUS · '+state.tracks.length+' REMIXABLE IMMERSIVE CANDIDATES');
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
      var duration=track.duration>0?' · '+Math.round(track.duration)+' s':'';
      var meta=el('span','',track.artist+' · '+track.license+duration);
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);
      var rights=el('div','status good','Returned by Audius as remixable. Pocket Spatial also rejects explicit NoDerivatives / All Rights Reserved metadata when present.');
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
      var diagnostic=el('div','status','Ready to test Audius through the verified buffered Web Audio path.');
      diagnostic.style.marginTop='6px';
      row.appendChild(diagnostic);
      var play=button('BUFFER + PLAY AUDIUS',function(){
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

function loadCatalog(ui){
  if(!root.XMLHttpRequest){setStatus(ui,'This browser does not expose XMLHttpRequest for Audius catalog loading.','warn');return;}
  ui.load.disabled=true;
  ui.load.textContent='LOADING AUDIUS…';
  setStatus(ui,'Requesting Audius remixable tracks with anonymous read-only API access…','');
  var xhr=new root.XMLHttpRequest();
  try{xhr.open('GET',buildCatalogURL(),true);}catch(e){
    ui.load.disabled=false;
    ui.load.textContent='RETRY AUDIUS CATALOG';
    setStatus(ui,'Could not open the Audius catalog request: '+(e.message||String(e)),'warn');
    return;
  }
  xhr.timeout=12000;
  xhr.onerror=function(){
    ui.load.disabled=false;
    ui.load.textContent='RETRY AUDIUS CATALOG';
    setStatus(ui,'The Audius catalog request failed before a response arrived.','warn');
  };
  xhr.ontimeout=function(){
    ui.load.disabled=false;
    ui.load.textContent='RETRY AUDIUS CATALOG';
    setStatus(ui,'The Audius catalog request timed out.','warn');
  };
  xhr.onload=function(){
    ui.load.disabled=false;
    ui.load.textContent='RELOAD AUDIUS CATALOG';
    var status=Number(xhr.status)||0;
    if(status<200||status>=300){setStatus(ui,'Audius returned HTTP '+status+' for the remixable catalog.','warn');return;}
    var data=null;
    try{data=JSON.parse(xhr.responseText||'{}');}catch(e){setStatus(ui,'Audius returned catalog data Safari could not parse.','warn');return;}
    state.tracks=normalizedTracks(data);
    renderTracks(ui);
    if(state.tracks.length)setStatus(ui,'Audius is connected. Pick a remixable track and tap BUFFER + PLAY AUDIUS.','good');
    else setStatus(ui,'Audius responded, but this batch had no compatible remixable tracks.','warn');
  };
  try{xhr.send();}catch(e){
    ui.load.disabled=false;
    ui.load.textContent='RETRY AUDIUS CATALOG';
    setStatus(ui,'Could not send the Audius catalog request: '+(e.message||String(e)),'warn');
  }
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var card=el('div','card');
  card.id='audiusCard';
  var title=el('div','','AUDIUS · FREE IMMERSIVE MUSIC');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);
  var status=el('div','status','Large free music source. This first test uses Audius anonymous read-only remixable tracks, so no account or API key is required.');
  status.id='audiusStatus';
  card.appendChild(status);
  var ui={card:card,status:status,load:null,tracks:null};
  var load=button('LOAD AUDIUS FREE MUSIC',function(){loadCatalog(ui);});
  load.id='audiusLoad';
  ui.load=load;
  card.appendChild(load);
  var tracks=el('div','');
  tracks.id='audiusTracks';
  ui.tracks=tracks;
  card.appendChild(tracks);
  var note=el('div','legal','Pocket Spatial does not record, save, export, or persist Audius media. Audio is fetched into temporary RAM only, decoded into Web Audio, and discarded when playback ends or the page closes.');
  note.style.marginTop='8px';
  card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);
  return ui;
}

function boot(){
  var ui=createUI();
  if(!ui)return;
  root.PocketSpatialAudiusCatalog=root.PocketSpatialAudiusCatalogAPI;
  root.PocketSpatialAudiusCatalog.ui=ui;
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
