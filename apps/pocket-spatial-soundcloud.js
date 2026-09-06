(function(root){
'use strict';

var config=root.PocketSpatialSoundCloudConfig||{brokerURL:'',configured:false};
var SESSION_KEY='pocketSpatial.soundcloud.session.v1';
var state={session:null,me:null,tracks:[],health:null};

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

function setSession(value){
  state.session=value||null;
  try{
    if(value)localStorage.setItem(SESSION_KEY,value);
    else localStorage.removeItem(SESSION_KEY);
  }catch(e){}
}

function loadSession(){
  try{return localStorage.getItem(SESSION_KEY)||null;}catch(e){return null;}
}

function cleanHash(){
  if(!history||!history.replaceState)return;
  history.replaceState(null,document.title,location.pathname+location.search);
}

function consumeOAuthFragment(){
  var hash=(location.hash||'').replace(/^#/,'');
  if(!hash)return null;
  var parts=hash.split('&');
  var result={};
  for(var i=0;i<parts.length;i+=1){
    var pair=parts[i].split('=');
    result[decodeURIComponent(pair[0]||'')]=decodeURIComponent(pair.slice(1).join('=')||'');
  }
  if(result.sc_session){setSession(result.sc_session);cleanHash();return {connected:true};}
  if(result.sc_error){cleanHash();return {error:result.sc_error};}
  return null;
}

function broker(path){
  var base=(config.brokerURL||'').replace(/\/+$/,'');
  return base+path;
}

function api(path,options){
  options=options||{};
  options.headers=options.headers||{};
  if(state.session)options.headers.Authorization='Bearer '+state.session;
  return fetch(broker(path),options).then(function(response){
    var rotated=response.headers.get('x-pocket-session');
    if(rotated)setSession(rotated);
    return response.text().then(function(text){
      var data={};
      try{data=text?JSON.parse(text):{};}catch(e){data={error:'invalid_json'};}
      if(response.status===401){setSession(null);}
      if(!response.ok){
        var err=new Error(data.error||('http_'+response.status));
        err.status=response.status;
        err.data=data;
        throw err;
      }
      return data;
    });
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;

  var card=el('div','card');
  card.id='soundcloudCard';

  var title=el('div','', 'SOUNDCLOUD CONNECTION');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);

  var status=el('div','status','Checking connector…');
  status.id='scStatus';
  card.appendChild(status);

  var actions=el('div','row');
  var connect=button('CONNECT SOUNDCLOUD',function(){
    if(!config.brokerURL)return;
    location.href=broker('/oauth/start');
  });
  connect.id='scConnect';
  var refresh=button('REFRESH',function(){refreshLibrary(ui);});
  refresh.id='scRefresh';
  var signout=button('SIGN OUT',function(){signOut(ui);});
  signout.id='scSignout';
  actions.appendChild(connect);
  actions.appendChild(refresh);
  actions.appendChild(signout);
  card.appendChild(actions);

  var profile=el('div','status','');
  profile.id='scProfile';
  card.appendChild(profile);

  var tracks=el('div','');
  tracks.id='scTracks';
  card.appendChild(tracks);

  var note=el('div','legal','');
  note.appendChild(document.createTextNode('This connector currently loads '));
  var bold=document.createElement('b');
  bold.textContent='your own SoundCloud uploads';
  note.appendChild(bold);
  note.appendChild(document.createTextNode('. They are rights-safe candidates for our processor because you are the uploader. The HLS-to-iPhone-6 spatial transport is the next layer; other users’ tracks stay on SoundCloud unless their license explicitly permits modification.'));
  card.appendChild(note);

  hero.parentNode.insertBefore(card,hero);

  return {card:card,status:status,connect:connect,refresh:refresh,signout:signout,profile:profile,tracks:tracks};
}

function setStatus(ui,text,kind){
  ui.status.textContent=text;
  ui.status.className='status'+(kind?' '+kind:'');
}

function renderTrackList(ui){
  while(ui.tracks.firstChild)ui.tracks.removeChild(ui.tracks.firstChild);
  if(!state.tracks.length){
    ui.tracks.appendChild(el('div','status','No uploaded tracks returned for this account.'));
    return;
  }

  var heading=el('div','status','YOUR UPLOADS · '+state.tracks.length);
  heading.style.marginTop='12px';
  heading.style.fontWeight='700';
  ui.tracks.appendChild(heading);

  for(var i=0;i<state.tracks.length;i+=1){
    (function(track){
      var row=el('div','metric');
      row.style.marginTop='8px';
      var name=el('b','',track.title||'Untitled');
      name.style.display='block';
      row.appendChild(name);

      var meta=el('span','', 'Own upload · '+(track.license||'license not specified'));
      meta.style.display='block';
      meta.style.marginTop='4px';
      row.appendChild(meta);

      var rights=el('div','status good','Spatial rights check: own upload ✓');
      rights.style.marginTop='4px';
      row.appendChild(rights);

      if(track.permalink_url){
        var link=el('a','', 'Open original on SoundCloud');
        link.href=track.permalink_url;
        link.target='_blank';
        link.rel='noopener';
        link.style.display='inline-block';
        link.style.marginTop='6px';
        link.style.color='inherit';
        row.appendChild(link);
      }

      var next=el('div','status','Spatial stream bridge: next layer');
      row.appendChild(next);
      ui.tracks.appendChild(row);
    }(state.tracks[i]));
  }
}

function render(ui){
  var connected=Boolean(state.session&&state.me);
  ui.connect.style.display=connected?'none':'block';
  ui.refresh.style.display=connected?'block':'none';
  ui.signout.style.display=connected?'block':'none';

  if(state.me&&state.me.user){
    var user=state.me.user;
    ui.profile.textContent='Connected as '+(user.username||'SoundCloud user')+'.';
    ui.profile.className='status good';
  }else{
    ui.profile.textContent='';
  }
  renderTrackList(ui);
}

function refreshLibrary(ui){
  if(!state.session){render(ui);return Promise.resolve();}
  setStatus(ui,'Loading your SoundCloud account…','');
  return Promise.all([api('/api/me'),api('/api/tracks')]).then(function(values){
    state.me=values[0];
    state.tracks=values[1].tracks||[];
    setStatus(ui,'SoundCloud connected. Your own uploads are loaded.','good');
    render(ui);
  }).catch(function(error){
    state.me=null;
    state.tracks=[];
    if(error.status===401){
      setStatus(ui,'SoundCloud session expired. Connect again.','warn');
    }else{
      setStatus(ui,'SoundCloud connection error: '+error.message,'warn');
    }
    render(ui);
  });
}

function signOut(ui){
  var hadSession=state.session;
  setSession(null);
  state.me=null;
  state.tracks=[];
  render(ui);
  setStatus(ui,'Signed out of the Pocket Spatial connector.','');
  if(hadSession){
    fetch(broker('/api/signout'),{method:'POST',headers:{Authorization:'Bearer '+hadSession}})['catch'](function(){});
  }
}

function boot(){
  var ui=createUI();
  if(!ui)return;

  var oauth=consumeOAuthFragment();
  state.session=loadSession();

  if(!config.brokerURL){
    ui.connect.disabled=true;
    ui.refresh.style.display='none';
    ui.signout.style.display='none';
    setStatus(ui,'SoundCloud connector code is installed; broker deployment is not configured yet.','warn');
    render(ui);
    return;
  }

  fetch(broker('/health')).then(function(response){return response.json();}).then(function(health){
    state.health=health;
    if(!health.configured){
      ui.connect.disabled=true;
      setStatus(ui,'SoundCloud connector is online, but API app credentials are not configured yet.','warn');
      render(ui);
      return;
    }
    ui.connect.disabled=false;
    if(oauth&&oauth.error){setStatus(ui,'SoundCloud sign-in failed: '+oauth.error,'warn');}
    if(state.session)refreshLibrary(ui);
    else{
      setStatus(ui,'SoundCloud connector is ready. Tap Connect SoundCloud.','good');
      render(ui);
    }
  })['catch'](function(){
    ui.connect.disabled=true;
    setStatus(ui,'SoundCloud broker could not be reached. Local spatial playback still works.','warn');
    render(ui);
  });
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
