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
    var masterGain=1-(0.06*wet);
    return{
      wet:wet,
      deg:deg,
      itd:itd,
      cutoff:cutoff,
      farGain:farGain,
      directGain:directGain,
      masterGain:masterGain
    };
  }

  function appliedTargets(spacePercent,angleDegrees,enabled){
    var p=calculate(spacePercent,angleDegrees);
    return{
      wet:p.wet,
      deg:p.deg,
      delaySeconds:p.itd,
      cutoffHz:p.cutoff,
      farGain:enabled?p.farGain:0,
      directGain:enabled?p.directGain:1,
      masterGain:enabled?p.masterGain:1
    };
  }

  function readouts(spacePercent,angleDegrees,enabled){
    var t=appliedTargets(spacePercent,angleDegrees,enabled);
    return{
      spaceText:Math.round(t.wet*100)+'%',
      angleText:Math.round(t.deg)+'°',
      delayText:(t.delaySeconds*1000).toFixed(2)+' ms',
      cutoffText:Math.round(t.cutoffHz)+' Hz',
      farText:Math.round(t.farGain*100)+'%',
      directText:Math.round(t.directGain*100)+'%',
      masterText:Math.round(t.masterGain*100)+'%'
    };
  }

  return{
    calculate:calculate,
    appliedTargets:appliedTargets,
    readouts:readouts
  };
}));
