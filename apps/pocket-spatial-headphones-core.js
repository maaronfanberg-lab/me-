(function(root,factory){
  var api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.PocketSpatialHeadphonesCore=api;
}(typeof window!=='undefined'?window:this,function(){
  'use strict';

  function clamp(v,min,max){return Math.max(min,Math.min(max,Number(v)||0));}
  function curve01(v,p){v=clamp(v,0,1);return Math.pow(v,Math.max(.05,Number(p)||1));}

  function calculate(values){
    values=values||{};
    var externalize=clamp(values.externalize==null?58:values.externalize,0,100)/100;
    var width=clamp(values.width==null?38:values.width,0,100)/100;
    var depth=clamp(values.depth==null?42:values.depth,0,100)/100;
    var room=clamp(values.room==null?40:values.room,0,100)/100;
    var shadow=clamp(values.headShadow==null?3200:values.headShadow,900,7000);

    var e=curve01(externalize,.78);
    var w=curve01(width,.82);
    var d=curve01(depth,.95);
    var r=curve01(room,1.0);

    /*
      Listening-test v2: the first build proved the Web Audio path worked,
      but its enhancement sends were too conservative to be perceptually
      distinct on Alex's PXC 550-II. Keep the direct stereo broadband and
      bass-safe, but make the side/cross-ear/reflection ratios clearly audible.
    */
    var directGain=.72;
    var crossGain=.025+.145*e;
    var widthGain=.165*w;
    var refl1Gain=.095*d;
    var refl2Gain=.060*d;
    var worstCaseSum=directGain+crossGain+widthGain+refl1Gain+refl2Gain;
    var masterGain=Math.min(.90,.78/Math.max(.78,worstCaseSum));

    return {
      externalize:externalize,
      width:width,
      depth:depth,
      room:room,
      crossHighpassHz:140,
      sideHighpassHz:240,
      directGain:directGain,
      crossGain:crossGain,
      crossDelaySeconds:(.00020+.00052*e),
      headShadowHz:shadow,
      widthGain:widthGain,
      refl1Gain:refl1Gain,
      refl2Gain:refl2Gain,
      refl1DelayL:.012+.018*r,
      refl1DelayR:.018+.021*r,
      refl2DelayL:.026+.030*r,
      refl2DelayR:.034+.032*r,
      reflCutoffHz:Math.max(1700,Math.min(6000,shadow*1.15)),
      masterGain:masterGain,
      worstCaseSum:worstCaseSum,
      outputBudget:worstCaseSum*masterGain,
      compressor:{threshold:-6,knee:8,ratio:4,attack:.005,release:.12}
    };
  }

  return {calculate:calculate,clamp:clamp};
}));
