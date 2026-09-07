(function(root,factory){
  var api=factory();
  if(typeof module==='object'&&module.exports){module.exports=api;}
  if(root){root.PocketSpatialCore=api;}
}(this,function(){
  'use strict';

  function clamp(v,min,max){return Math.max(min,Math.min(max,v));}
  function exp01(x,shape){x=clamp(Number(x)||0,0,1);shape=Math.max(0.01,Number(shape)||1);return (Math.exp(shape*x)-1)/(Math.exp(shape)-1);}
  function signedPow(x,p){var s=x<0?-1:1;return s*Math.pow(Math.abs(x),p);}
  function logMap(raw,inMin,inMax,outMin,outMax){
    var n=clamp((Number(raw)-inMin)/(inMax-inMin),0,1);
    return outMin*Math.pow(outMax/outMin,n);
  }

  function calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent){
    var rawSpace=clamp(Number(spacePercent)||0,0,250);
    var rawAngle=clamp(Number(angleDegrees)||0,0,180);
    var rawStretch=clamp(Number(delayStretchPercent)||100,25,800);
    var spaceNorm=rawSpace/250;
    var spaceCurve=exp01(spaceNorm,2.45);
    var wet=3.6*spaceCurve;
    var angleNorm=rawAngle/180;
    var angleCurve=exp01(angleNorm,2.15);
    var baseDelayMs=0.18+14.32*angleCurve;
    var stretchNorm=(rawStretch-25)/(800-25);
    var stretchCurve=0.45+4.55*exp01(stretchNorm,2.35);
    var itd=(baseDelayMs*stretchCurve)/1000;
    var cutoff=logMap(clamp(Number(headShadowHz)||3300,400,12000),400,12000,420,14000);
    var polarity=clamp(Number(crossfeedPolarityPercent)||0,-100,100)/100;
    var polarityCurve=signedPow(polarity,0.62);
    var angleStrength=0.18+1.55*angleCurve;
    var farGain=(0.035+0.92*spaceCurve)*angleStrength*polarityCurve;
    var directGain=Math.max(0.18,1-(0.58*spaceCurve));
    return{rawSpace:rawSpace,wet:wet,deg:rawAngle,angleCurve:angleCurve,angleStrength:angleStrength,stretch:stretchCurve,itd:itd,cutoff:cutoff,polarity:polarity,farGain:farGain,directGain:directGain};
  }

  function calculateDepth(depthPercent,roomScalePercent,reflectionToneHz,roomWrapPercent){
    var rawDepth=clamp(Number(depthPercent)||0,0,300);
    var depthCurve=exp01(rawDepth/300,2.55);
    var rawRoom=clamp(Number(roomScalePercent)||100,25,600);
    var roomNorm=(rawRoom-25)/(600-25);
    var roomCurve=0.38+7.62*exp01(roomNorm,2.45);
    var tone=logMap(clamp(Number(reflectionToneHz)||3300,300,12000),300,12000,320,14500);
    var wrapRaw=clamp(Number(roomWrapPercent)||0,0,300);
    var wrapCurve=exp01(wrapRaw/300,2.4);
    var directDistanceGain=Math.max(0.10,1-(0.86*depthCurve));
    return{
      depth:4.0*depthCurve,depthCurve:depthCurve,directDistanceGain:directDistanceGain,roomScale:roomCurve,
      refl1DelayL:(0.010+0.030*roomCurve),refl1DelayR:(0.014+0.036*roomCurve),
      refl2DelayL:(0.026+0.061*roomCurve),refl2DelayR:(0.032+0.071*roomCurve),
      refl1Gain:0.72*depthCurve,refl2Gain:0.48*depthCurve,reflCutoff:tone,reflQ:0.50,
      wrapRaw:wrapRaw,wrapCurve:wrapCurve,
      wrapDelayL1:0.078+0.092*roomCurve,wrapDelayR1:0.094+0.113*roomCurve,
      wrapDelayL2:0.164+0.171*roomCurve,wrapDelayR2:0.193+0.204*roomCurve,
      wrapGain1:0.96*wrapCurve,wrapGain2:0.66*wrapCurve,
      wrapCutoff:Math.max(480,Math.min(tone*0.66,7600))
    };
  }

  function appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled){
    var p=calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent);
    var d=calculateDepth(depthPercent,roomScalePercent,reflectionToneHz,roomWrapPercent);
    var active=!!enabled;
    var farGain=active?p.farGain:0;
    var directGain=active?Math.max(0.07,p.directGain*d.directDistanceGain):1;
    var refl1Gain=active?d.refl1Gain:0;
    var refl2Gain=active?d.refl2Gain:0;
    var wrapGain1=active?d.wrapGain1:0;
    var wrapGain2=active?d.wrapGain2:0;
    var energy=(directGain*directGain)+(farGain*farGain)+(refl1Gain*refl1Gain)+(refl2Gain*refl2Gain)+(wrapGain1*wrapGain1)+(wrapGain2*wrapGain2);
    var masterGain=active?Math.min(0.96,0.92/Math.sqrt(Math.max(1,energy*1.12))):1;
    return{
      wet:p.wet,deg:p.deg,depth:d.depth,delayStretch:p.stretch,delaySeconds:p.itd,cutoffHz:p.cutoff,polarity:p.polarity,
      farGain:farGain,directGain:directGain,distanceDirect:d.directDistanceGain,roomScale:d.roomScale,
      refl1DelayL:d.refl1DelayL,refl1DelayR:d.refl1DelayR,refl2DelayL:d.refl2DelayL,refl2DelayR:d.refl2DelayR,
      refl1Gain:refl1Gain,refl2Gain:refl2Gain,reflCutoff:d.reflCutoff,reflQ:d.reflQ,wrapRaw:d.wrapRaw,
      wrapDelayL1:d.wrapDelayL1,wrapDelayR1:d.wrapDelayR1,wrapDelayL2:d.wrapDelayL2,wrapDelayR2:d.wrapDelayR2,
      wrapGain1:wrapGain1,wrapGain2:wrapGain2,wrapCutoff:d.wrapCutoff,masterGain:masterGain
    };
  }

  function readouts(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled){
    var t=appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled);
    return{
      spaceText:Math.round(Number(spacePercent)||0)+'% → '+Math.round(t.wet*100)+'%',
      angleText:Math.round(t.deg)+'° → '+(t.delaySeconds*1000).toFixed(2)+' ms',
      depthText:Math.round(Number(depthPercent)||0)+'% → direct '+Math.round(t.distanceDirect*100)+'%',
      delayStretchText:t.delayStretch.toFixed(2)+'×',headShadowText:Math.round(t.cutoffHz)+' Hz',
      roomScaleText:Math.round(Number(roomScalePercent)||0)+'% → '+t.roomScale.toFixed(2)+'×',reflectionToneText:Math.round(t.reflCutoff)+' Hz',
      polarityText:(t.polarity<0?'INVERTED ':'NORMAL ')+Math.round(Math.abs(t.polarity)*100)+'%',roomWrapText:Math.round(Number(roomWrapPercent)||0)+'% → '+Math.round(t.wrapGain1*100)+'%',
      delayText:(t.delaySeconds*1000).toFixed(2)+' ms',cutoffText:Math.round(t.cutoffHz)+' Hz',farText:(t.farGain<0?'-':'')+Math.round(Math.abs(t.farGain)*100)+'%',directText:Math.round(t.directGain*100)+'%',
      reflectionTimesText:Math.round(t.refl1DelayL*1000)+'/'+Math.round(t.refl1DelayR*1000)+' · '+Math.round(t.refl2DelayL*1000)+'/'+Math.round(t.refl2DelayR*1000)+' ms',
      reflectionGainText:(t.refl1Gain*100).toFixed(1)+'% / '+(t.refl2Gain*100).toFixed(1)+'%',
      wrapTimesText:Math.round(t.wrapDelayL1*1000)+'/'+Math.round(t.wrapDelayR1*1000)+' · '+Math.round(t.wrapDelayL2*1000)+'/'+Math.round(t.wrapDelayR2*1000)+' ms',
      wrapGainText:(t.wrapGain1*100).toFixed(1)+'% / '+(t.wrapGain2*100).toFixed(1)+'%',reflectionCutoffText:Math.round(t.reflCutoff)+' Hz',masterText:Math.round(t.masterGain*100)+'%'
    };
  }
  return{calculate:calculate,calculateDepth:calculateDepth,appliedTargets:appliedTargets,readouts:readouts};
}));

(function(){
  'use strict';
  if(typeof document==='undefined')return;
  var build='20260907-profound-3d-1';
  function versioned(src){return src+'?v='+build;}
  function load(src,next){var script=document.createElement('script');script.src=versioned(src);script.async=false;if(next)script.onload=next;document.head.appendChild(script);}
  load('pocket-spatial-commons-buffered.js',function(){load('pocket-spatial-single-playback.js',function(){load('pocket-spatial-buffered-catalog.js',function(){load('pocket-spatial-audius-catalog.js',function(){load('pocket-spatial-buffer-probe.js');});});});});
}());
