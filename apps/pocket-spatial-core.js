(function(root,factory){
  var api=factory();
  if(typeof module==='object'&&module.exports){module.exports=api;}
  if(root){root.PocketSpatialCore=api;}
}(this,function(){
  'use strict';

  function clamp(v,min,max){return Math.max(min,Math.min(max,v));}
  function exp01(x,shape){x=clamp(Number(x)||0,0,1);shape=Math.max(0.01,Number(shape)||1);return (Math.exp(shape*x)-1)/(Math.exp(shape)-1);}
  function signedPow(x,p){var s=x<0?-1:1;return s*Math.pow(Math.abs(x),p);}

  function calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent){
    var rawSpace=clamp(Number(spacePercent)||0,0,250);
    var rawAngle=clamp(Number(angleDegrees)||0,0,180);
    var rawStretch=clamp(Number(delayStretchPercent)||100,25,800);

    var spaceNorm=rawSpace/250;
    var spaceCurve=exp01(spaceNorm,3.3);
    var wet=2.8*spaceCurve;

    var angleNorm=rawAngle/180;
    var angleCurve=exp01(angleNorm,4.2);
    var baseDelayMs=0.08+7.2*angleCurve;

    var stretchNorm=(rawStretch-25)/(800-25);
    var stretchCurve=0.25+11.75*exp01(stretchNorm,3.8);
    var itd=(baseDelayMs*stretchCurve)/1000;

    var cutoff=clamp(Number(headShadowHz)||3300,400,12000);
    var polarity=clamp(Number(crossfeedPolarityPercent)||0,-100,100)/100;
    var polarityCurve=signedPow(polarity,0.72);
    var farGain=(0.04+0.78*spaceCurve)*polarityCurve;
    var directGain=Math.max(0.16,1-(0.48*spaceCurve));

    return{
      rawSpace:rawSpace,
      wet:wet,
      deg:rawAngle,
      angleCurve:angleCurve,
      stretch:stretchCurve,
      itd:itd,
      cutoff:cutoff,
      polarity:polarity,
      farGain:farGain,
      directGain:directGain
    };
  }

  function calculateDepth(depthPercent,roomScalePercent,reflectionToneHz,roomWrapPercent){
    var rawDepth=clamp(Number(depthPercent)||0,0,300);
    var depthCurve=exp01(rawDepth/300,3.4);
    var rawRoom=clamp(Number(roomScalePercent)||100,25,600);
    var roomNorm=(rawRoom-25)/(600-25);
    var roomCurve=0.32+7.68*exp01(roomNorm,3.3);
    var tone=clamp(Number(reflectionToneHz)||3300,300,12000);
    var wrapRaw=clamp(Number(roomWrapPercent)||0,0,300);
    var wrapCurve=exp01(wrapRaw/300,3.8);

    return{
      depth:3.2*depthCurve,
      roomScale:roomCurve,
      refl1DelayL:(0.013+0.037*roomCurve),
      refl1DelayR:(0.017+0.043*roomCurve),
      refl2DelayL:(0.031+0.074*roomCurve),
      refl2DelayR:(0.037+0.086*roomCurve),
      refl1Gain:0.50*depthCurve,
      refl2Gain:0.34*depthCurve,
      reflCutoff:tone,
      reflQ:0.55,
      wrapRaw:wrapRaw,
      wrapCurve:wrapCurve,
      wrapDelayL1:0.055+0.085*roomCurve,
      wrapDelayR1:0.067+0.101*roomCurve,
      wrapDelayL2:0.118+0.151*roomCurve,
      wrapDelayR2:0.137+0.176*roomCurve,
      wrapGain1:0.58*wrapCurve,
      wrapGain2:0.38*wrapCurve,
      wrapCutoff:Math.max(550,Math.min(tone*0.72,7200))
    };
  }

  function appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled){
    var p=calculate(spacePercent,angleDegrees,delayStretchPercent,headShadowHz,crossfeedPolarityPercent);
    var d=calculateDepth(depthPercent,roomScalePercent,reflectionToneHz,roomWrapPercent);
    var active=!!enabled;
    var farGain=active?p.farGain:0;
    var directGain=active?p.directGain:1;
    var refl1Gain=active?d.refl1Gain:0;
    var refl2Gain=active?d.refl2Gain:0;
    var wrapGain1=active?d.wrapGain1:0;
    var wrapGain2=active?d.wrapGain2:0;
    var worstCaseSum=Math.abs(directGain)+Math.abs(farGain)+Math.abs(refl1Gain)+Math.abs(refl2Gain)+Math.abs(wrapGain1)+Math.abs(wrapGain2);
    var masterGain=active?Math.min(0.90,0.78/Math.max(1,worstCaseSum)):1;

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
      wrapRaw:d.wrapRaw,
      wrapDelayL1:d.wrapDelayL1,
      wrapDelayR1:d.wrapDelayR1,
      wrapDelayL2:d.wrapDelayL2,
      wrapDelayR2:d.wrapDelayR2,
      wrapGain1:wrapGain1,
      wrapGain2:wrapGain2,
      wrapCutoff:d.wrapCutoff,
      masterGain:masterGain
    };
  }

  function readouts(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled){
    var t=appliedTargets(spacePercent,angleDegrees,depthPercent,delayStretchPercent,headShadowHz,roomScalePercent,reflectionToneHz,crossfeedPolarityPercent,roomWrapPercent,enabled);
    return{
      spaceText:Math.round(Number(spacePercent)||0)+'% → '+Math.round(t.wet*100)+'%',
      angleText:Math.round(t.deg)+'° → '+(t.delaySeconds*1000).toFixed(2)+' ms',
      depthText:Math.round(Number(depthPercent)||0)+'% → '+Math.round(t.depth*100)+'%',
      delayStretchText:Math.round(t.delayStretch*100)+'%',
      headShadowText:Math.round(t.cutoffHz)+' Hz',
      roomScaleText:Math.round(Number(roomScalePercent)||0)+'% → '+t.roomScale.toFixed(2)+'×',
      reflectionToneText:Math.round(t.reflCutoff)+' Hz',
      polarityText:(t.polarity<0?'INVERTED ':'NORMAL ')+Math.round(Math.abs(t.polarity)*100)+'%',
      roomWrapText:Math.round(Number(roomWrapPercent)||0)+'% → '+Math.round(t.wrapGain1*100)+'%',
      delayText:(t.delaySeconds*1000).toFixed(2)+' ms',
      cutoffText:Math.round(t.cutoffHz)+' Hz',
      farText:(t.farGain<0?'-':'')+Math.round(Math.abs(t.farGain)*100)+'%',
      directText:Math.round(t.directGain*100)+'%',
      reflectionTimesText:Math.round(t.refl1DelayL*1000)+'/'+Math.round(t.refl1DelayR*1000)+' · '+Math.round(t.refl2DelayL*1000)+'/'+Math.round(t.refl2DelayR*1000)+' ms',
      reflectionGainText:(t.refl1Gain*100).toFixed(1)+'% / '+(t.refl2Gain*100).toFixed(1)+'%',
      wrapTimesText:Math.round(t.wrapDelayL1*1000)+'/'+Math.round(t.wrapDelayR1*1000)+' · '+Math.round(t.wrapDelayL2*1000)+'/'+Math.round(t.wrapDelayR2*1000)+' ms',
      wrapGainText:(t.wrapGain1*100).toFixed(1)+'% / '+(t.wrapGain2*100).toFixed(1)+'%',
      reflectionCutoffText:Math.round(t.reflCutoff)+' Hz',
      masterText:Math.round(t.masterGain*100)+'%'
    };
  }

  return{calculate:calculate,calculateDepth:calculateDepth,appliedTargets:appliedTargets,readouts:readouts};
}));

(function(){
  'use strict';
  if(typeof document==='undefined')return;
  var build='20260907-playback-fix-1';
  function versioned(src){return src+'?v='+build;}
  function load(src,next){var script=document.createElement('script');script.src=versioned(src);script.async=false;if(next)script.onload=next;document.head.appendChild(script);}
  load('pocket-spatial-commons-buffered.js',function(){load('pocket-spatial-single-playback.js',function(){load('pocket-spatial-buffered-catalog.js',function(){load('pocket-spatial-audius-catalog.js',function(){load('pocket-spatial-buffer-probe.js');});});});});
}());