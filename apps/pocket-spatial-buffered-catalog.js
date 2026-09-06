(function(root){
'use strict';

var API='https://commons.wikimedia.org/w/api.php';
var CATEGORY='Category:Audio files of music';
var jsonpCounter=0;
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

function removeNode(node){
  if(node&&node.parentNode)node.parentNode.removeChild(node);
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
  if(isHTTPS(info.url)&&looksLikeMP3(info.mime,info.url,''))return info.url;
  var derivatives=info.derivatives||[];
  for(var i=0;i<derivatives.length;i+=1){
    var d=derivatives[i]||{};
    var url=d.src||d.url||'';
    if(isHTTPS(url)&&looksLikeMP3(d.type||d.mime,url,d.transcodekey||d.key))return url;
  }
  return null;
}

function pageURL(title){
  return 'https://commons.wikimedia.org/wiki/'+encodeURIComponent(String(title||'').replace(/ /g,'_'));
}

function normalizePage(page){
  var info=page&&page.videoinfo&&page.videoinfo[0];
  if(!info||!licenseAllowsSpatial(info))return null;
  var audio=selectMP3(info);
  if(!audio)return null;
  return{
    pageid:page.pageid,
    title:plain(page.title||'Untitled'),
    artist:metadataValue(info,'Artist')||'Wikimedia Commons contributor',
    license:metadataValue(info,'LicenseShortName')||metadataValue(info,'UsageTerms')||'Free license',
    file_page:pageURL(page.title),
    audio:audio
  };
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
    '&viextmetadatafilter='+encodeURIComponent('LicenseShortName|LicenseUrl|Artist|UsageTerms')+
    '&format=json'+
    '&callback='+encodeURIComponent(callbackName);
}

function jsonp(template,callback){
  jsonpCounter+=1;
  var name='PocketSpatialBufferedCatalogJSONP'+jsonpCounter;
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
  script.onerror=function(){finish(new Error('commons_catalog_failed'));};
  script.src=template.replace(/%7Bcallback%7D/i,encodeURIComponent(name)).replace('{callback}',encodeURIComponent(name));
  script.async=true;
  document.head.appendChild(script);
  timer=setTimeout(function(){finish(new Error('commons_catalog_timeout'));},12000);
}

function renderTracks(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  if(!state.tracks.length){
    ui.tracks.appendChild(el('div','status','No derivative-permitting MP3 candidates were returned in this batch. Reload for another batch.'));
    return;
  }
  var heading=el('div','status','COMMONS FREE MUSIC · '+state.tracks.length+' IMMERSIVE CANDIDATES');
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
      var rights=el('div','status good','Free-license spatial candidate. Attribution/share-alike details remain on the Commons file page.');
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
      var diagnostic=el('div','status','Ready for buffered immersive playback.');
      diagnostic.style.marginTop='6px';
      row.appendChild(diagnostic);
      var play=button('BUFFER + PLAY IMMERSIVE',function(){
        var player=root.PocketSpatialBufferedCommons;
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
  ui.load.disabled=true;
  ui.load.textContent='LOADING COMMONS…';
  setStatus(ui,'Requesting derivative-permitting free music from Wikimedia Commons…','');
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
    if(tracks.length)setStatus(ui,'Catalog loaded. Pick a track and tap BUFFER + PLAY IMMERSIVE.','good');
    else setStatus(ui,'Commons responded, but this batch had no compatible MP3 candidates. Reload for another batch.','warn');
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var card=el('div','card');
  card.id='bufferedCommonsCard';
  var title=el('div','','WIKIMEDIA COMMONS · IMMERSIVE MUSIC');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);
  var status=el('div','status','No account, API key, or SoundCloud. Free-license Commons MP3s are buffered into Web Audio RAM, then routed through Pocket Spatial.');
  status.id='bufferedCommonsStatus';
  card.appendChild(status);
  var ui={card:card,status:status,load:null,tracks:null};
  var load=button('LOAD FREE MUSIC CATALOG',function(){loadCatalog(ui);});
  load.id='bufferedCommonsLoad';
  ui.load=load;
  card.appendChild(load);
  var tracks=el('div','');
  tracks.id='bufferedCommonsTracks';
  ui.tracks=tracks;
  card.appendChild(tracks);
  var limits=root.PocketSpatialBufferedCommons&&root.PocketSpatialBufferedCommons.limits;
  var limitText=limits?Math.round(limits.compressedBytes/1048576)+' MB / '+limits.durationSeconds+' s':'conservative iPhone 6';
  var note=el('div','legal','Temporary-memory playback only. The current safety ceiling is '+limitText+'. Nothing is recorded, saved, exported, or persisted by Pocket Spatial.');
  note.style.marginTop='8px';
  card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);
  return ui;
}

function boot(){
  var ui=createUI();
  if(!ui)return;
  root.PocketSpatialBufferedCatalog={
    buildCatalogURL:buildCatalogURL,
    licenseAllowsSpatial:licenseAllowsSpatial,
    selectMP3:selectMP3,
    normalizePage:normalizePage,
    ui:ui
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
