(function(root){
'use strict';

var API='https://commons.wikimedia.org/w/api.php';
var TEST_TITLE='File:Music loop 168bpm (Still frivolous).ogg';
var TEST_PAGE='https://commons.wikimedia.org/wiki/File:Music_loop_168bpm_(Still_frivolous).ogg';
var MAX_BYTES=1048576;
var jsonpCounter=0;
var lastResult=null;

function el(tag,className,text){
  var node=document.createElement(tag);
  if(className)node.className=className;
  if(text!=null)node.textContent=text;
  return node;
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

function licenseAllowsProbe(info){
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

function buildMetadataURL(callbackName){
  return API+'?action=query'+
    '&titles='+encodeURIComponent(TEST_TITLE)+
    '&prop=videoinfo'+
    '&viprop='+encodeURIComponent('url|mime|derivatives|extmetadata')+
    '&viextmetadatafilter='+encodeURIComponent('LicenseShortName|LicenseUrl|UsageTerms')+
    '&format=json'+
    '&callback='+encodeURIComponent(callbackName);
}

function jsonp(template,callback){
  jsonpCounter+=1;
  var name='PocketSpatialBufferJSONP'+jsonpCounter;
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
  script.onerror=function(){finish(new Error('buffer_metadata_request_failed'));};
  script.src=template.replace(/%7Bcallback%7D/i,encodeURIComponent(name)).replace('{callback}',encodeURIComponent(name));
  script.async=true;
  document.head.appendChild(script);
  timer=setTimeout(function(){finish(new Error('buffer_metadata_timeout'));},12000);
}

function resolveTestClip(callback){
  jsonp(buildMetadataURL('{callback}'),function(error,data){
    if(error){callback(error);return;}
    var pages=data&&data.query&&data.query.pages?data.query.pages:{};
    var info=null;
    for(var key in pages){
      if(Object.prototype.hasOwnProperty.call(pages,key)){
        info=pages[key]&&pages[key].videoinfo&&pages[key].videoinfo[0];
        if(info)break;
      }
    }
    if(!info){callback(new Error('buffer_test_clip_missing'));return;}
    if(!licenseAllowsProbe(info)){callback(new Error('buffer_test_license_not_permitted'));return;}
    var mp3=selectMP3(info);
    if(!mp3){callback(new Error('buffer_test_mp3_missing'));return;}
    callback(null,{url:mp3,license:metadataValue(info,'LicenseShortName')||metadataValue(info,'UsageTerms')||'free license'});
  });
}

function probeBufferedPCM(url,callback){
  var AC=root.AudioContext||root.webkitAudioContext;
  if(!AC){callback({supported:false,reason:'web_audio_unavailable'});return;}
  if(!root.XMLHttpRequest){callback({supported:false,reason:'xhr_unavailable'});return;}

  var ctx=null;
  var analyser=null;
  var silent=null;
  var source=null;
  var xhr=null;
  var timer=null;
  var finished=false;
  var maxDeviation=0;
  var ticks=0;
  var decodedDuration=0;
  var receivedBytes=0;

  function cleanup(){
    if(timer)clearInterval(timer);
    try{if(source)source.stop(0);}catch(e){}
    try{if(xhr&&xhr.readyState!==4)xhr.abort();}catch(e2){}
    try{if(ctx&&ctx.close)ctx.close();}catch(e3){}
    source=null;
    analyser=null;
    silent=null;
    xhr=null;
    ctx=null;
  }

  function finish(result){
    if(finished)return;
    finished=true;
    result.received_bytes=receivedBytes;
    result.decoded_duration=decodedDuration;
    result.max_analyser_deviation=maxDeviation;
    cleanup();
    callback(result);
  }

  try{
    ctx=new AC();
    analyser=ctx.createAnalyser();
    analyser.fftSize=256;
    analyser.smoothingTimeConstant=0;
    silent=ctx.createGain();
    silent.gain.value=0;
    analyser.connect(silent);
    silent.connect(ctx.destination);
    if(ctx.state==='suspended'&&ctx.resume)ctx.resume();
  }catch(error){
    finish({supported:false,reason:'buffer_probe_graph_failed',detail:error.message||String(error)});
    return;
  }

  xhr=new root.XMLHttpRequest();
  try{
    xhr.open('GET',url,true);
    xhr.responseType='arraybuffer';
  }catch(openError){
    finish({supported:false,reason:'buffer_xhr_open_failed',detail:openError.message||String(openError)});
    return;
  }

  xhr.onprogress=function(event){
    if(finished)return;
    if(event&&event.lengthComputable&&event.total>MAX_BYTES){
      receivedBytes=event.loaded||0;
      finish({supported:false,reason:'buffer_probe_too_large',declared_bytes:event.total,max_bytes:MAX_BYTES});
    }
  };

  xhr.onerror=function(){finish({supported:false,reason:'buffer_xhr_failed'});};
  xhr.ontimeout=function(){finish({supported:false,reason:'buffer_xhr_timeout'});};
  xhr.timeout=15000;

  xhr.onload=function(){
    if(finished)return;
    var status=Number(xhr.status)||0;
    if(status<200||status>=300){finish({supported:false,reason:'buffer_http_failed',http_status:status});return;}
    var bytes=xhr.response&&xhr.response.byteLength?xhr.response.byteLength:0;
    receivedBytes=bytes;
    if(!bytes){finish({supported:false,reason:'buffer_empty_response'});return;}
    if(bytes>MAX_BYTES){finish({supported:false,reason:'buffer_probe_too_large',declared_bytes:bytes,max_bytes:MAX_BYTES});return;}

    try{
      ctx.decodeAudioData(xhr.response,function(buffer){
        if(finished)return;
        if(!buffer||!(buffer.duration>0)){finish({supported:false,reason:'decoded_buffer_empty'});return;}
        decodedDuration=buffer.duration;
        try{
          source=ctx.createBufferSource();
          source.buffer=buffer;
          source.connect(analyser);
          source.start(0);
        }catch(sourceError){
          finish({supported:false,reason:'buffer_source_failed',detail:sourceError.message||String(sourceError)});
          return;
        }

        var data=new Uint8Array(analyser.fftSize);
        timer=setInterval(function(){
          ticks+=1;
          try{
            analyser.getByteTimeDomainData(data);
            for(var i=0;i<data.length;i+=1){
              var deviation=Math.abs(data[i]-128);
              if(deviation>maxDeviation)maxDeviation=deviation;
            }
          }catch(e){}
          if(ticks>=15){
            finish({supported:maxDeviation>2,reason:maxDeviation>2?'buffered_pcm_available':'buffer_pcm_flatline'});
          }
        },100);
      },function(error){
        finish({supported:false,reason:'decode_audio_data_failed',detail:error&&error.message?error.message:String(error||'decode_failed')});
      });
    }catch(decodeError){
      finish({supported:false,reason:'decode_audio_data_threw',detail:decodeError.message||String(decodeError)});
    }
  };

  try{xhr.send();}catch(sendError){finish({supported:false,reason:'buffer_xhr_send_failed',detail:sendError.message||String(sendError)});}
}

function setStatus(ui,text,kind){
  ui.status.textContent=text;
  ui.status.className='status'+(kind?' '+kind:'');
}

function run(ui){
  ui.button.disabled=true;
  ui.button.textContent='TESTING BUFFERED PCM…';
  setStatus(ui,'Bypassing the remote audio-element tap. Resolving a 5.7-second Commons music loop, then decoding it directly into Web Audio RAM…','');
  resolveTestClip(function(error,clip){
    if(error){
      ui.button.disabled=false;
      ui.button.textContent='RETRY BUFFERED PCM CHECK';
      setStatus(ui,'Could not prepare the tiny Commons control clip: '+error.message,'warn');
      return;
    }
    probeBufferedPCM(clip.url,function(result){
      lastResult=result;
      ui.button.disabled=false;
      if(result.supported){
        ui.button.textContent='BUFFERED PCM VERIFIED ✓';
        setStatus(ui,'Verified: remote audio bytes decoded into non-flat Web Audio PCM on this iPhone. The old media-element tap is the broken layer. Bytes '+result.received_bytes+', duration '+result.decoded_duration.toFixed(1)+' s, analyser deviation '+result.max_analyser_deviation+'.','good');
      }else{
        ui.button.textContent='BUFFERED PCM NOT VERIFIED';
        setStatus(ui,'Buffered Web Audio test failed at '+result.reason+'. Bytes '+result.received_bytes+', decoded duration '+result.decoded_duration.toFixed(1)+' s, analyser deviation '+result.max_analyser_deviation+'.','warn');
      }
    });
  });
}

function createUI(){
  var hero=document.querySelector('.card.hero');
  if(!hero||!hero.parentNode)return null;
  var card=el('div','card');
  card.id='bufferProbeCard';
  var title=el('div','','IPHONE 6 · BUFFERED PCM CHECK');
  title.style.fontWeight='700';
  title.style.letterSpacing='.06em';
  title.style.fontSize='12px';
  card.appendChild(title);
  var status=el('div','status','Use this only if a Commons track says web_audio_pcm_flatline. It tests a tiny remote clip without using an HTML audio-element tap.');
  card.appendChild(status);
  var ui={card:card,status:status,button:null};
  var button=el('button','','RUN BUFFERED PCM CHECK');
  button.type='button';
  button.addEventListener('click',function(){run(ui);});
  ui.button=button;
  card.appendChild(button);
  var link=el('a','','Open the 5.7-second Commons test clip + license');
  link.href=TEST_PAGE;
  link.target='_blank';
  link.rel='noopener';
  link.style.display='inline-block';
  link.style.marginTop='6px';
  link.style.color='inherit';
  card.appendChild(link);
  var note=el('div','legal','This diagnostic keeps the compressed bytes and decoded AudioBuffer in memory only for the short test, then releases them. It does not record, save, export, or persist the clip.');
  note.style.marginTop='8px';
  card.appendChild(note);
  hero.parentNode.insertBefore(card,hero);
  return ui;
}

function boot(){
  var ui=createUI();
  root.PocketSpatialBufferProbe={
    buildMetadataURL:buildMetadataURL,
    licenseAllowsProbe:licenseAllowsProbe,
    selectMP3:selectMP3,
    probeBufferedPCM:probeBufferedPCM,
    getLastResult:function(){return lastResult;},
    ui:ui
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
