(function(root){
'use strict';

var MAX_COMPRESSED_BYTES=6291456;
var MAX_DURATION_SECONDS=180;
var PRESET_SPACE=86;
var PRESET_ANGLE=64;
var PRESET_DEPTH=58;

var state={
  ctx:null,
  source:null,
  monoMerger:null,
  splitter:null,
  merger:null,
  master:null,
  directL:null,directR:null,crossL:null,crossR:null,
  delayL:null,delayR:null,filterL:null,filterR:null,
  reflDelayL1:null,reflDelayR1:null,reflDelayL2:null,reflDelayR2:null,
  reflFilterL1:null,reflFilterR1:null,reflFilterL2:null,reflFilterR2:null,
  reflGainL1:null,reflGainR1:null,reflGainL2:null,reflGainR2:null,
  xhr:null,
  playing:false,
  activePageId:null,
  activeControl:null,
  activeDiagnostic:null,
  savedUI:null
};

function byId(id){return document.getElementById(id);}
function text(id,value){var n=byId(id);if(n)n.textContent=value;}
function core(){return root.PocketSpatialCore;}
function AC(){return root.AudioContext||root.webkitAudioContext;}

function setParam(param,value){
  if(!state.ctx||!param)return;
  var t=state.ctx.currentTime;
  try{param.cancelScheduledValues(t);param.setTargetAtTime(value,t,0.035);}catch(e){param.value=value;}
}

function setFixedParam(param,value){
  if(param&&param.value!==value)param.value=value;
}

function currentValues(){
  var space=byId('space'),angle=byId('angle'),depth=byId('depth');
  return {
    space:space?space.value:PRESET_SPACE,
    angle:angle?angle.value:PRESET_ANGLE,
    depth:depth?depth.value:PRESET_DEPTH
  };
}

function renderReadouts(active){
  var c=core();
  if(!c)return;
  var v=currentValues();
  var r=c.readouts(v.space,v.angle,v.depth,!!active);
  text('spaceRead',r.spaceText);
  text('angleRead',r.angleText);
  text('depthRead',r.depthText);
  text('delay',r.delayText);
  text('cutoff',r.cutoffText);
  text('far',r.farText);
  text('direct',r.directText);
  text('reflTimes',r.reflectionTimesText);
  text('reflGain',r.reflectionGainText);
  text('reflCutoff',r.reflectionCutoffText);
  text('master',r.masterText);
}

function apply(){
  var c=core();
  if(!c||!state.ctx)return;
  var v=currentValues();
  var t=c.appliedTargets(v.space,v.angle,v.depth,true);
  setParam(state.delayL.delayTime,t.delaySeconds);
  setParam(state.delayR.delayTime,t.delaySeconds);
  setParam(state.filterL.frequency,t.cutoffHz);
  setParam(state.filterR.frequency,t.cutoffHz);
  setParam(state.directL.gain,t.directGain);
  setParam(state.directR.gain,t.directGain);
  setParam(state.crossL.gain,t.farGain);
  setParam(state.crossR.gain,t.farGain);
  setFixedParam(state.reflDelayL1.delayTime,t.refl1DelayL);
  setFixedParam(state.reflDelayR1.delayTime,t.refl1DelayR);
  setFixedParam(state.reflDelayL2.delayTime,t.refl2DelayL);
  setFixedParam(state.reflDelayR2.delayTime,t.refl2DelayR);
  setParam(state.reflFilterL1.frequency,t.reflCutoff);
  setParam(state.reflFilterR1.frequency,t.reflCutoff);
  setParam(state.reflFilterL2.frequency,t.reflCutoff);
  setParam(state.reflFilterR2.frequency,t.reflCutoff);
  setFixedParam(state.reflFilterL1.Q,t.reflQ);
  setFixedParam(state.reflFilterR1.Q,t.reflQ);
  setFixedParam(state.reflFilterL2.Q,t.reflQ);
  setFixedParam(state.reflFilterR2.Q,t.reflQ);
  setParam(state.reflGainL1.gain,t.refl1Gain);
  setParam(state.reflGainR1.gain,t.refl1Gain);
  setParam(state.reflGainL2.gain,t.refl2Gain);
  setParam(state.reflGainR2.gain,t.refl2Gain);
  setParam(state.master.gain,t.masterGain);
  renderReadouts(true);
}

function buildGraph(){
  var C=AC();
  var c=core();
  if(!C||!c)return false;
  if(state.ctx)return true;
  try{
    state.ctx=new C();
    state.splitter=state.ctx.createChannelSplitter(2);
    state.merger=state.ctx.createChannelMerger(2);
    state.master=state.ctx.createGain();

    state.directL=state.ctx.createGain();state.directR=state.ctx.createGain();
    state.crossL=state.ctx.createGain();state.crossR=state.ctx.createGain();
    state.delayL=state.ctx.createDelay(0.01);state.delayR=state.ctx.createDelay(0.01);
    state.filterL=state.ctx.createBiquadFilter();state.filterR=state.ctx.createBiquadFilter();
    state.filterL.type='lowpass';state.filterR.type='lowpass';
    state.filterL.Q.value=.55;state.filterR.Q.value=.55;

    state.reflDelayL1=state.ctx.createDelay(0.05);state.reflDelayR1=state.ctx.createDelay(0.05);
    state.reflDelayL2=state.ctx.createDelay(0.05);state.reflDelayR2=state.ctx.createDelay(0.05);
    state.reflFilterL1=state.ctx.createBiquadFilter();state.reflFilterR1=state.ctx.createBiquadFilter();
    state.reflFilterL2=state.ctx.createBiquadFilter();state.reflFilterR2=state.ctx.createBiquadFilter();
    state.reflGainL1=state.ctx.createGain();state.reflGainR1=state.ctx.createGain();
    state.reflGainL2=state.ctx.createGain();state.reflGainR2=state.ctx.createGain();
    state.reflFilterL1.type='lowpass';state.reflFilterR1.type='lowpass';
    state.reflFilterL2.type='lowpass';state.reflFilterR2.type='lowpass';

    state.splitter.connect(state.directL,0);state.directL.connect(state.merger,0,0);
    state.splitter.connect(state.directR,1);state.directR.connect(state.merger,0,1);
    state.splitter.connect(state.delayL,0);state.delayL.connect(state.filterL);state.filterL.connect(state.crossL);state.crossL.connect(state.merger,0,1);
    state.splitter.connect(state.delayR,1);state.delayR.connect(state.filterR);state.filterR.connect(state.crossR);state.crossR.connect(state.merger,0,0);

    state.splitter.connect(state.reflDelayL1,0);state.reflDelayL1.connect(state.reflFilterL1);state.reflFilterL1.connect(state.reflGainL1);state.reflGainL1.connect(state.merger,0,0);
    state.splitter.connect(state.reflDelayL2,0);state.reflDelayL2.connect(state.reflFilterL2);state.reflFilterL2.connect(state.reflGainL2);state.reflGainL2.connect(state.merger,0,0);
    state.splitter.connect(state.reflDelayR1,1);state.reflDelayR1.connect(state.reflFilterR1);state.reflFilterR1.connect(state.reflGainR1);state.reflGainR1.connect(state.merger,0,1);
    state.splitter.connect(state.reflDelayR2,1);state.reflDelayR2.connect(state.reflFilterR2);state.reflFilterR2.connect(state.reflGainR2);state.reflGainR2.connect(state.merger,0,1);

    state.merger.connect(state.master);state.master.connect(state.ctx.destination);
    apply();
    return true;
  }catch(e){
    state.ctx=null;
    return false;
  }
}

function setImmersivePreset(){
  var space=byId('space'),angle=byId('angle'),depth=byId('depth');
  if(space)space.value=String(PRESET_SPACE);
  if(angle)angle.value=String(PRESET_ANGLE);
  if(depth)depth.value=String(PRESET_DEPTH);
  apply();
}

function saveAndTakeUI(){
  var spatial=byId('spatial'),badge=byId('badge');
  if(!state.savedUI){
    state.savedUI={
      spatialText:spatial?spatial.textContent:'TURN SPATIAL ON',
      spatialDisabled:spatial?!!spatial.disabled:false,
      badgeText:badge?badge.textContent:'Spatial off',
      badgeClass:badge?badge.className:'badge',
      priorActive:badge&&String(badge.className).indexOf(' on')!==-1
    };
  }
  if(spatial){spatial.disabled=true;spatial.textContent='BUFFERED IMMERSIVE ACTIVE';}
  if(badge){badge.textContent='Buffered immersive';badge.className='badge on';}
  text('engine','buffered');
  renderReadouts(true);
}

function restoreUI(){
  var spatial=byId('spatial'),badge=byId('badge');
  if(state.savedUI){
    if(spatial){spatial.disabled=state.savedUI.spatialDisabled;spatial.textContent=state.savedUI.spatialText;}
    if(badge){badge.textContent=state.savedUI.badgeText;badge.className=state.savedUI.badgeClass;}
    renderReadouts(state.savedUI.priorActive);
  }else{
    if(spatial){spatial.disabled=false;spatial.textContent='TURN SPATIAL ON';}
    if(badge){badge.textContent='Spatial off';badge.className='badge';}
    renderReadouts(false);
  }
  text('engine',state.ctx?'ready':'off');
  state.savedUI=null;
}

function resetActiveButton(message,kind){
  if(state.activeControl){
    state.activeControl.disabled=false;
    state.activeControl.textContent='BUFFER + PLAY IMMERSIVE';
  }
  if(state.activeDiagnostic&&message){
    state.activeDiagnostic.textContent=message;
    state.activeDiagnostic.className='status'+(kind?' '+kind:'');
  }
}

function stop(manual){
  if(state.xhr&&state.xhr.readyState!==4){try{state.xhr.abort();}catch(e){}}
  state.xhr=null;
  if(state.source){
    try{state.source.onended=null;state.source.stop(0);}catch(e2){}
    try{state.source.disconnect();}catch(e3){}
  }
  if(state.monoMerger){try{state.monoMerger.disconnect();}catch(e4){}}
  state.source=null;
  state.monoMerger=null;
  state.playing=false;
  state.activePageId=null;
  if(manual)resetActiveButton('Buffered immersive playback stopped.','');
  restoreUI();
  state.activeControl=null;
  state.activeDiagnostic=null;
}

function fail(control,diagnostic,message){
  stop(false);
  if(control){control.disabled=false;control.textContent='RETRY BUFFERED IMMERSIVE';}
  if(diagnostic){diagnostic.textContent=message;diagnostic.className='status warn';}
}

function startDecodedBuffer(buffer,track,control,diagnostic){
  if(!buffer||!(buffer.duration>0)){fail(control,diagnostic,'The remote MP3 decoded to an empty buffer.');return;}
  if(buffer.duration>MAX_DURATION_SECONDS){
    fail(control,diagnostic,'This track is '+buffer.duration.toFixed(0)+' seconds long. The iPhone 6 safety limit is '+MAX_DURATION_SECONDS+' seconds for buffered immersive playback.');
    return;
  }
  if(buffer.numberOfChannels>2){
    fail(control,diagnostic,'This file decoded to '+buffer.numberOfChannels+' channels. The current iPhone 6 immersive path accepts mono or stereo only.');
    return;
  }
  try{
    state.source=state.ctx.createBufferSource();
    state.source.buffer=buffer;
    if(buffer.numberOfChannels===1){
      state.monoMerger=state.ctx.createChannelMerger(2);
      state.source.connect(state.monoMerger,0,0);
      state.source.connect(state.monoMerger,0,1);
      state.monoMerger.connect(state.splitter);
    }else{
      state.source.connect(state.splitter);
    }
    state.playing=true;
    state.source.onended=function(){
      if(!state.playing)return;
      resetActiveButton('Buffered immersive playback finished.','good');
      state.source=null;
      state.monoMerger=null;
      state.playing=false;
      state.activePageId=null;
      restoreUI();
      state.activeControl=null;
      state.activeDiagnostic=null;
    };
    apply();
    if(state.ctx.state==='suspended'&&state.ctx.resume)state.ctx.resume();
    state.source.start(0);
    control.disabled=false;
    control.textContent='STOP IMMERSIVE PLAYBACK';
    diagnostic.textContent='Buffered immersive playback is live. '+buffer.duration.toFixed(1)+' s decoded in memory; Spatial '+PRESET_SPACE+'%, angle '+PRESET_ANGLE+'°, depth '+PRESET_DEPTH+'%. Adjust the three sliders while it plays.';
    diagnostic.className='status good';
    text('track','Commons buffered · '+String(track.title||'').replace(/^File:/,'')+' · '+(track.artist||'Wikimedia Commons contributor'));
    var status=byId('status');
    if(status){status.textContent='Remote Commons audio is playing through AudioBufferSourceNode and the Pocket Spatial DSP. Use the sliders to shape immersion.';status.className='status good';}
  }catch(e){
    fail(control,diagnostic,'Could not start buffered immersive playback: '+(e.message||String(e)));
  }
}

function fetchDecodePlay(track,control,diagnostic){
  var C=AC();
  if(!C||!core()){fail(control,diagnostic,'Web Audio or the Pocket Spatial DSP core is unavailable on this browser.');return;}
  if(!root.XMLHttpRequest){fail(control,diagnostic,'This browser does not expose XMLHttpRequest for the buffered path.');return;}
  if(!buildGraph()){fail(control,diagnostic,'Could not create the buffered immersive Web Audio graph.');return;}
  if(state.ctx.state==='suspended'&&state.ctx.resume)state.ctx.resume();
  setImmersivePreset();
  saveAndTakeUI();

  control.disabled=true;
  control.textContent='BUFFERING IMMERSIVE…';
  diagnostic.textContent='Fetching the Commons MP3 into temporary memory, then decoding it directly into Web Audio. Nothing is saved or exported.';
  diagnostic.className='status';

  var xhr=new root.XMLHttpRequest();
  state.xhr=xhr;
  try{
    xhr.open('GET',track.audio,true);
    xhr.responseType='arraybuffer';
  }catch(e){fail(control,diagnostic,'Could not open the remote MP3 request: '+(e.message||String(e)));return;}
  xhr.timeout=20000;
  xhr.onprogress=function(event){
    if(event&&event.lengthComputable&&event.total>MAX_COMPRESSED_BYTES){
      try{xhr.abort();}catch(e){}
      fail(control,diagnostic,'This MP3 is larger than the '+Math.round(MAX_COMPRESSED_BYTES/1048576)+' MB iPhone 6 compressed-audio safety limit.');
    }
  };
  xhr.onerror=function(){fail(control,diagnostic,'The Commons MP3 request failed before decoding.');};
  xhr.ontimeout=function(){fail(control,diagnostic,'The Commons MP3 request timed out before decoding.');};
  xhr.onload=function(){
    if(state.xhr!==xhr)return;
    var status=Number(xhr.status)||0;
    if(status<200||status>=300){fail(control,diagnostic,'The Commons media server returned HTTP '+status+'.');return;}
    var bytes=xhr.response&&xhr.response.byteLength?xhr.response.byteLength:0;
    if(!bytes){fail(control,diagnostic,'The Commons MP3 response contained no audio bytes.');return;}
    if(bytes>MAX_COMPRESSED_BYTES){fail(control,diagnostic,'This MP3 is '+(bytes/1048576).toFixed(1)+' MB, above the '+Math.round(MAX_COMPRESSED_BYTES/1048576)+' MB iPhone 6 safety limit.');return;}
    diagnostic.textContent='Received '+(bytes/1048576).toFixed(2)+' MB. Decoding the MP3 into Web Audio PCM…';
    try{
      state.ctx.decodeAudioData(xhr.response,function(buffer){
        if(state.xhr!==xhr)return;
        state.xhr=null;
        startDecodedBuffer(buffer,track,control,diagnostic);
      },function(error){
        fail(control,diagnostic,'Safari could not decode this MP3 into Web Audio: '+(error&&error.message?error.message:'decode_audio_data_failed'));
      });
    }catch(e){
      fail(control,diagnostic,'decodeAudioData threw an error: '+(e.message||String(e)));
    }
  };
  try{xhr.send();}catch(e){fail(control,diagnostic,'Could not send the Commons MP3 request: '+(e.message||String(e)));}
}

function toggle(track,control,diagnostic){
  if(state.playing&&state.activePageId===track.pageid){stop(true);return;}
  if(state.playing||state.xhr)stop(false);
  state.activePageId=track.pageid;
  state.activeControl=control;
  state.activeDiagnostic=diagnostic;
  fetchDecodePlay(track,control,diagnostic);
}

function bindControls(){
  var ids=['space','angle','depth'];
  for(var i=0;i<ids.length;i++){
    var n=byId(ids[i]);
    if(n)n.addEventListener('input',function(){if(state.playing)apply();});
  }
  var presets=document.querySelectorAll('.preset');
  for(var j=0;j<presets.length;j++)presets[j].addEventListener('click',function(){if(state.playing)apply();});
  var audio=byId('audio');
  if(audio)audio.addEventListener('play',function(){if(state.playing||state.xhr)stop(true);});
  var file=byId('file');
  if(file)file.addEventListener('change',function(){if(state.playing||state.xhr)stop(true);});
}

function boot(){
  bindControls();
  root.PocketSpatialBufferedCommons={
    toggle:toggle,
    stop:function(){stop(true);},
    apply:apply,
    isPlaying:function(pageid){return state.playing&&state.activePageId===pageid;},
    limits:{compressedBytes:MAX_COMPRESSED_BYTES,durationSeconds:MAX_DURATION_SECONDS},
    preset:{space:PRESET_SPACE,angle:PRESET_ANGLE,depth:PRESET_DEPTH}
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);
else boot();

}(this));
