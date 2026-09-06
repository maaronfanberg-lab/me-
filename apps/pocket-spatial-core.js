(function(root,factory){
  var api=factory();
  if(typeof module==='object'&&module.exports){module.exports=api;}
  if(root){root.PocketSpatialCore=api;}
}(this,function(){
  'use strict';

  function clamp(v,min,max){return Math.max(min,Math.min(max,v));}

  function calculate(spacePercent,angleDegrees){
    var wet=clamp(Number(spacePercent)||0,0,100)/100;
    var deg=clamp(Number(angleDegrees)||0,20,70);
    var theta=deg*Math.PI/180;
    var itd=(0.0875/343)*(theta+Math.sin(theta));
    var cutoff=7000-(3800*wet);
    var farGain=0.22*wet;
    var directGain=1-(0.18*wet);
    var baseMasterGain=1-(0.06*wet);
    return{
      wet:wet,
      deg:deg,
      itd:itd,
      cutoff:cutoff,
      farGain:farGain,
      directGain:directGain,
      baseMasterGain:baseMasterGain
    };
  }

  function calculateDepth(depthPercent){
    var depth=clamp(Number(depthPercent)||0,0,100)/100;
    return{
      depth:depth,
      refl1DelayL:0.011,
      refl1DelayR:0.013,
      refl2DelayL:0.021,
      refl2DelayR:0.024,
      refl1Gain:0.14*depth,
      refl2Gain:0.07*depth,
      reflCutoff:2600,
      reflQ:0.5
    };
  }

  function appliedTargets(spacePercent,angleDegrees,depthPercent,enabled){
    var p=calculate(spacePercent,angleDegrees);
    var d=calculateDepth(depthPercent);
    var active=!!enabled;
    var farGain=active?p.farGain:0;
    var directGain=active?p.directGain:1;
    var refl1Gain=active?d.refl1Gain:0;
    var refl2Gain=active?d.refl2Gain:0;
    var nominalSum=directGain+farGain+refl1Gain+refl2Gain;
    var headroomGain=nominalSum>1?1/nominalSum:1;
    var masterGain=active?Math.min(p.baseMasterGain,headroomGain):1;

    return{
      wet:p.wet,
      deg:p.deg,
      depth:d.depth,
      delaySeconds:p.itd,
      cutoffHz:p.cutoff,
      farGain:farGain,
      directGain:directGain,
      refl1DelayL:d.refl1DelayL,
      refl1DelayR:d.refl1DelayR,
      refl2DelayL:d.refl2DelayL,
      refl2DelayR:d.refl2DelayR,
      refl1Gain:refl1Gain,
      refl2Gain:refl2Gain,
      reflCutoff:d.reflCutoff,
      reflQ:d.reflQ,
      nominalSum:nominalSum,
      masterGain:masterGain
    };
  }

  function readouts(spacePercent,angleDegrees,depthPercent,enabled){
    var t=appliedTargets(spacePercent,angleDegrees,depthPercent,enabled);
    return{
      spaceText:Math.round(t.wet*100)+'%',
      angleText:Math.round(t.deg)+'°',
      depthText:Math.round(t.depth*100)+'%',
      delayText:(t.delaySeconds*1000).toFixed(2)+' ms',
      cutoffText:Math.round(t.cutoffHz)+' Hz',
      farText:Math.round(t.farGain*100)+'%',
      directText:Math.round(t.directGain*100)+'%',
      reflectionTimesText:'11/13 · 21/24 ms',
      reflectionGainText:(t.refl1Gain*100).toFixed(1)+'% / '+(t.refl2Gain*100).toFixed(1)+'%',
      reflectionCutoffText:Math.round(t.reflCutoff)+' Hz',
      masterText:Math.round(t.masterGain*100)+'%'
    };
  }

  return{
    calculate:calculate,
    calculateDepth:calculateDepth,
    appliedTargets:appliedTargets,
    readouts:readouts
  };
}));

(function(){
  'use strict';
  if(typeof document==='undefined')return;
  var build='20260906-commons-buffered-2';
  function versioned(src){return src+'?v='+build;}
  function load(src,next){
    var script=document.createElement('script');
    script.src=versioned(src);
    script.async=false;
    if(next)script.onload=next;
    document.head.appendChild(script);
  }
  load('pocket-spatial-commons-buffered.js',function(){
    load('pocket-spatial-buffered-catalog.js',function(){
      load('pocket-spatial-buffer-probe.js');
    });
  });
}());
