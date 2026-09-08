(function(root){
'use strict';

var AC=root.AudioContext||root.webkitAudioContext;
var core=root.PocketSpatialHeadphonesCore;
var audio=document.getElementById('audio');
var spatial=document.getElementById('spatial');
var file=document.getElementById('file');
var badge=document.getElementById('badge');
var status=document.getElementById('status');
var track=document.getElementById('track');
var monoButton=document.getElementById('monoCheck');
var controls={
  externalize:document.getElementById('externalize'),
  width:document.getElementById('width'),
  depth:document.getElementById('depth'),
  room:document.getElementById('room'),
  headShadow:document.getElementById('headShadow')
};
var ctx=null,source=null,split=null,dryMerge=null,wetMerge=null,dryGain=null,wetGain=null,outputBus=null,monoSplit=null,monoL=null,monoR=null,monoSum=null,monoMerge=null,stereoGain=null,monoGain=null,limiter=null;
var directL=null,directR=null,crossHP_L=null,crossHP_R=null,crossLP_L=null,crossLP_R=null,crossDelayL=null,crossDelayR=null,crossGainL=null,crossGainR=null;
var sideL=null,sideR=null,sideBus=null,sideHP=null,widthL=null,widthR=null;
var refl1L=null,refl1R=null,refl2L=null,refl2R=null,refl1FilterL=null,refl1FilterR=null,refl2FilterL=null,refl2FilterR=null,refl1GainL=null,refl1GainR=null,refl2GainL=null,refl2GainR=null;
var enabled=false,mono=false,objectURL=null,lastParams=null;

function clamp(v,a,b){return Math.max(a,Math.min(b,Number(v)||0));}
function text(id,value){var n=document.getElementById(id);if(n)n.textContent=value;}
function setParam(param,value,tau){if(!param)return;var t=ctx?ctx.currentTime:0;try{param.cancelScheduledValues(t);param.setTargetAtTime(value,t,tau==null?.025:tau);}catch(e){param.value=value;}}
function oneChannel(node){try{node.channelCount=1;node.channelCountMode='explicit';node.channelInterpretation='discrete';}catch(e){}}
function connectMono(node,merger,channel){node.connect(merger,0,channel);}
function values(){return{
  externalize:clamp(controls.externalize.value,0,100),
  width:clamp(controls.width.value,0,100),
  depth:clamp(controls.depth.value,0,100),
  room:clamp(controls.room.value,0,100),
  headShadow:clamp(controls.headShadow.value,900,7000)
};}

function buildGraph(){
  if(ctx)return true;
  if(!AC||!core){status.textContent=!AC?'Web Audio is unavailable in this browser.':'The headphone DSP core did not load.';status.className='status warn';return false;}
  if(root.PocketSpatialReceiverMatrix){status.textContent='Safety tripwire: receiver matrix code is present. Reload the dedicated headphone page.';status.className='status warn';return false;}
  try{
    ctx=new AC();
    source=ctx.createMediaElementSource(audio);
    split=ctx.createChannelSplitter(2);
    dryMerge=ctx.createChannelMerger(2);
    wetMerge=ctx.createChannelMerger(2);
    dryGain=ctx.createGain();wetGain=ctx.createGain();outputBus=ctx.createGain();
    stereoGain=ctx.createGain();monoGain=ctx.createGain();monoSplit=ctx.createChannelSplitter(2);monoL=ctx.createGain();monoR=ctx.createGain();monoSum=ctx.createGain();oneChannel(monoSum);monoMerge=ctx.createChannelMerger(2);
    limiter=ctx.createDynamicsCompressor();

    directL=ctx.createGain();directR=ctx.createGain();
    crossHP_L=ctx.createBiquadFilter();crossHP_R=ctx.createBiquadFilter();crossLP_L=ctx.createBiquadFilter();crossLP_R=ctx.createBiquadFilter();crossDelayL=ctx.createDelay(.01);crossDelayR=ctx.createDelay(.01);crossGainL=ctx.createGain();crossGainR=ctx.createGain();
    crossHP_L.type=crossHP_R.type='highpass';crossHP_L.Q.value=crossHP_R.Q.value=.55;crossLP_L.type=crossLP_R.type='lowpass';crossLP_L.Q.value=crossLP_R.Q.value=.55;

    sideL=ctx.createGain();sideR=ctx.createGain();sideBus=ctx.createGain();oneChannel(sideBus);sideL.gain.value=.5;sideR.gain.value=-.5;sideHP=ctx.createBiquadFilter();sideHP.type='highpass';sideHP.Q.value=.55;widthL=ctx.createGain();widthR=ctx.createGain();

    refl1L=ctx.createDelay(.12);refl1R=ctx.createDelay(.12);refl2L=ctx.createDelay(.12);refl2R=ctx.createDelay(.12);
    refl1FilterL=ctx.createBiquadFilter();refl1FilterR=ctx.createBiquadFilter();refl2FilterL=ctx.createBiquadFilter();refl2FilterR=ctx.createBiquadFilter();
    refl1GainL=ctx.createGain();refl1GainR=ctx.createGain();refl2GainL=ctx.createGain();refl2GainR=ctx.createGain();
    [refl1FilterL,refl1FilterR,refl2FilterL,refl2FilterR].forEach(function(f){f.type='lowpass';f.Q.value=.5;});

    source.connect(split);
    split.connect(dryMerge,0,0);split.connect(dryMerge,1,1);

    split.connect(directL,0);connectMono(directL,wetMerge,0);split.connect(directR,1);connectMono(directR,wetMerge,1);

    split.connect(crossHP_L,0);crossHP_L.connect(crossLP_L);crossLP_L.connect(crossDelayL);crossDelayL.connect(crossGainL);connectMono(crossGainL,wetMerge,1);
    split.connect(crossHP_R,1);crossHP_R.connect(crossLP_R);crossLP_R.connect(crossDelayR);crossDelayR.connect(crossGainR);connectMono(crossGainR,wetMerge,0);

    split.connect(sideL,0);split.connect(sideR,1);sideL.connect(sideBus);sideR.connect(sideBus);sideBus.connect(sideHP);sideHP.connect(widthL);sideHP.connect(widthR);connectMono(widthL,wetMerge,0);connectMono(widthR,wetMerge,1);

    /* Early reflections remain above the bass-protection HPF and are deliberately asymmetric. */
    crossHP_L.connect(refl1L);refl1L.connect(refl1FilterL);refl1FilterL.connect(refl1GainL);connectMono(refl1GainL,wetMerge,0);
    crossHP_R.connect(refl1R);refl1R.connect(refl1FilterR);refl1FilterR.connect(refl1GainR);connectMono(refl1GainR,wetMerge,1);
    crossHP_L.connect(refl2L);refl2L.connect(refl2FilterL);refl2FilterL.connect(refl2GainL);connectMono(refl2GainL,wetMerge,1);
    crossHP_R.connect(refl2R);refl2R.connect(refl2FilterR);refl2FilterR.connect(refl2GainR);connectMono(refl2GainR,wetMerge,0);

    dryMerge.connect(dryGain);wetMerge.connect(wetGain);dryGain.connect(outputBus);wetGain.connect(outputBus);
    outputBus.connect(stereoGain);stereoGain.connect(limiter);
    outputBus.connect(monoSplit);monoL.gain.value=monoR.gain.value=.5;monoSplit.connect(monoL,0);monoSplit.connect(monoR,1);monoL.connect(monoSum);monoR.connect(monoSum);monoSum.connect(monoMerge,0,0);monoSum.connect(monoMerge,0,1);monoMerge.connect(monoGain);monoGain.connect(limiter);
    limiter.connect(ctx.destination);

    apply();applyMono();
    text('engine','Web Audio · custom binaural stereo');
    text('safetyRead','RECEIVER MATRIX ABSENT ✓');
    status.textContent='Headphone engine ready. Spatial OFF is the level-matched reference.';status.className='status good';
    return true;
  }catch(error){status.textContent='Headphone graph could not start: '+error.message;status.className='status warn';return false;}
}

function updateReadouts(p){
  var v=values();
  text('externalizeRead',Math.round(v.externalize)+'%');text('widthRead',Math.round(v.width)+'%');text('depthRead',Math.round(v.depth)+'%');text('roomRead',Math.round(v.room)+'%');text('headShadowRead',Math.round(v.headShadow)+' Hz');
  text('itdRead',(p.crossDelaySeconds*1000).toFixed(2)+' ms');text('crossRead',(p.crossGain*100).toFixed(1)+'%');text('reflectionRead',Math.round(p.refl1DelayL*1000)+'–'+Math.round(p.refl2DelayR*1000)+' ms');text('bassRead','< '+p.crossHighpassHz+' Hz untouched');text('headroomRead',Math.round(p.masterGain*100)+'% · budget '+(p.outputBudget*100).toFixed(0)+'%');
  document.documentElement.style.setProperty('--stage-width',String(.28+.72*(v.width/100)));
  document.documentElement.style.setProperty('--stage-depth',String(.22+.78*(v.depth/100)));
}

function apply(){
  var p=core.calculate(values());lastParams=p;updateReadouts(p);if(!ctx)return;
  var c=p.compressor;limiter.threshold.value=c.threshold;limiter.knee.value=c.knee;limiter.ratio.value=c.ratio;limiter.attack.value=c.attack;limiter.release.value=c.release;
  crossHP_L.frequency.value=crossHP_R.frequency.value=p.crossHighpassHz;sideHP.frequency.value=p.sideHighpassHz;crossLP_L.frequency.value=crossLP_R.frequency.value=p.headShadowHz;
  crossDelayL.delayTime.value=crossDelayR.delayTime.value=p.crossDelaySeconds;
  refl1L.delayTime.value=p.refl1DelayL;refl1R.delayTime.value=p.refl1DelayR;refl2L.delayTime.value=p.refl2DelayL;refl2R.delayTime.value=p.refl2DelayR;
  [refl1FilterL,refl1FilterR,refl2FilterL,refl2FilterR].forEach(function(f){f.frequency.value=p.reflCutoffHz;});

  setParam(dryGain.gain,enabled?0:.78,.015);setParam(wetGain.gain,enabled?p.masterGain:0,.015);
  setParam(directL.gain,p.directGain);setParam(directR.gain,p.directGain);
  setParam(crossGainL.gain,p.crossGain);setParam(crossGainR.gain,p.crossGain);
  setParam(widthL.gain,p.widthGain);setParam(widthR.gain,-p.widthGain);
  setParam(refl1GainL.gain,p.refl1Gain);setParam(refl1GainR.gain,p.refl1Gain*.94);setParam(refl2GainL.gain,p.refl2Gain*.90);setParam(refl2GainR.gain,p.refl2Gain);
}

function applyMono(){if(!ctx)return;setParam(stereoGain.gain,mono?0:1,.01);setParam(monoGain.gain,mono?1:0,.01);if(monoButton){monoButton.textContent=mono?'MONO CHECK: ON':'MONO CHECK: OFF';monoButton.className=mono?'warnButton':'';}}
function setEnabled(next){enabled=!!next;if(!buildGraph())return;if(ctx.state==='suspended')ctx.resume();apply();badge.textContent=enabled?'Headphone spatial on':'Headphone spatial off';badge.className='badge'+(enabled?' on':'');spatial.textContent=enabled?'TURN HEADPHONE SPATIAL OFF':'TURN HEADPHONE SPATIAL ON';status.textContent=enabled?'Spatial field active. Listen for the stage leaving the earcups, not merely getting louder.':'Reference bypass active through the same output limiter.';status.className='status'+(enabled?' good':'');}

spatial.addEventListener('click',function(){setEnabled(!enabled);});
if(monoButton)monoButton.addEventListener('click',function(){if(!buildGraph())return;mono=!mono;applyMono();});
Object.keys(controls).forEach(function(key){controls[key].addEventListener('input',apply);});
document.querySelectorAll('.preset').forEach(function(button){button.addEventListener('click',function(){Object.keys(controls).forEach(function(key){var val=button.getAttribute('data-'+key.toLowerCase());if(val!=null)controls[key].value=val;});apply();});});

file.addEventListener('change',function(){var f=file.files&&file.files[0];if(!f)return;if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(f);audio.removeAttribute('crossorigin');audio.crossOrigin=null;audio.src=objectURL;audio.load();track.textContent=f.name+' · local audio';});
audio.addEventListener('play',function(){if(ctx&&ctx.state==='suspended')ctx.resume();});
root.addEventListener('pagehide',function(){if(objectURL){URL.revokeObjectURL(objectURL);objectURL=null;}});

lastParams=core.calculate(values());updateReadouts(lastParams);
root.PocketSpatialHeadphones={version:'20260908-headphones-custom-1',enable:function(){setEnabled(true);},disable:function(){setEnabled(false);},apply:apply,values:values,parameters:function(){return lastParams;}};

}(window));
