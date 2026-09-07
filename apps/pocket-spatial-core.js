(function(root,factory){
  var api=factory();
  if(typeof module==='object'&&module.exports){module.exports=api;}
  if(root){root.PocketSpatialCore=api;}
}(this,function(){
  'use strict';

  function clamp(v,min,max){return Math.max(min,Math.min(max,v));}

  function calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent){
    var wet=clamp(Number(spacePercent)||0,0,250)/100;
    var deg=clamp(Number(angleDegrees)||0,0,180);
    var stretch=clamp(Number(delayStretchPercent)||100,25,800)/100;
    var theta=deg*Math.PI/180;
    var itd=(0.0875/343)*(theta+Math.sin(theta))*stretch;
    var cutoff=clamp(Number(headShadowHz)||3300,400,12000);
    var polarity=clamp(Number(crossfeedPolarityPercent)||0,-100,100)/100;
    var phaseSign=polarity<0?-1:1;
    var phaseAmount=Math.abs(polarity);
    var farGain=0.22*wet*(0.35+0.65*phaseAmount)*phaseSign;
    var directGain=Math.max(0.05,1-(0.18*Math.min(wet,2.5)));
    return{
      wet:wet,
      deg:deg,
      stretch:stretch,
      itd:itd,
      cutoff:cutoff,
      polarity:polarity,
      farGain:farGain,
      directGain:directGain
    };
  }

  function calculateDepth(depthPercent,roomScalePercent,reflectionToneHz){
    var depth=clamp(Number(depthPercent)||0,0,300)/100;
    var roomScale=clamp(Number(roomScalePercent)||100,25,600)/100;
    var tone=clamp(Number(reflectionToneHz)||3300,300,12000);
    return{
      depth:depth,
      roomScale:roomScale,
      refl1DelayL:0.017*roomScale,
      refl1DelayR:0.019*roomScale,
      refl2DelayL:0.031*roomScale,
      refl2DelayR:0.034*roomScale,
      refl1Gain:0.18*depth,
      refl2Gain:0.10*depth,
      reflCutoff:tone,
      reflQ:0.65
    };
  }

  function appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,enabled){
    var p=calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent);
    var d=calculateDepth(depthPercent,roomScalePercent,reflectionToneHz);
    var active=!!enabled;
    var farGain=active?p.farGain:0;
    var directGain=active?p.directGain:1;
    var refl1Gain=active?d.refl1Gain:0;
    var refl2Gain=active?d.refl2Gain:0;
    var worstCaseSum=Math.abs(directGain)+Math.abs(farGain)+Math.abs(refl1Gain)+Math.abs(refl2Gain);
    var masterGain=active?Math.min(0.92,0.88/Math.max(1,worstCaseSum)):1;

    return{
      wet:p.wet,
      deg:p.deg,
      depth:d.depth,
      delayStretch:p.stretch,
      delaySeconds:p.itd,
      cutoffHz:p.cutoff,
      polarity:p.polarity,
      farGain:farGain,
      directGain:directGain,
      roomScale:d.roomScale,
      refl1DelayL:d.refl1DelayL,
      refl1DelayR:d.refl1DelayR,
      refl2DelayL:d.refl2DelayL,
      refl2DelayR:d.refl2DelayR,
      refl1Gain:refl1Gain,
      refl2Gain:refl2Gain,
      reflCutoff:d.reflCutoff,
      reflQ:d.reflQ,
      masterGain:masterGain
    };
  }

  function readouts(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,enabled){
    var t=appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,enabled);
    return{
      spaceText:Math.round(t.wet*100)+'%',
      angleText:Math.round(t.deg)+'°',
      depthText:Math.round(t.depth*100)+'%',
      delayStretchText:Math.round(t.delayStretch*100)+'%',
      headShadowText:Math.round(t.cutoffHz)+' Hz',
      roomScaleText:Math.round(t.roomScale*100)+'%',
      reflectionToneText:Math.round(t.reflCutoff)+' Hz',
      polarityText:(t.polarity<0?'INVERTED ':'NORMAL ')+Math.round(Math.abs(t.polarity)*100)+'%',
      delayText:(t.delaySeconds*1000).toFixed(2)+' ms',
      cutoffText:Math.round(t.cutoffHz)+' Hz',
      farText:(t.farGain<0?'-':'')+Math.round(Math.abs(t.farGain)*100)+'%',
      directText:Math.round(t.directGain*100)+'%',
      reflectionTimesText:Math.round(t.refl1DelayL*1000)+'/'+Math.round(t.refl1DelayR*1000)+' · '+Math.round(t.refl2DelayL*1000)+'/'+Math.round(t.refl2DelayR*1000)+' ms',
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
  var build='20260907-extreme-lab-1';
  function versioned(src){return src+'?v='+build;}
  function load(src,next){
    var script=document.createElement('script');
    script.src=versioned(src);
    script.async=false;
    if(next)script.onload=next;
    document.head.appendChild(script);
  }
  load('pocket-spatial-commons-buffered.js',function(){
    load('pocket-spatial-single-playback.js',function(){
      load('pocket-spatial-buffered-catalog.js',function(){
        load('pocket-spatial-audius-catalog.js',function(){
          load('pocket-spatial-buffer-probe.js');
        });
      });
    });
  });
}());