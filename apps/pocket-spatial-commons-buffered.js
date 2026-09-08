(function(root){
'use strict';

/*
 * Receiver-first mode.
 *
 * This file remains in the historical Commons loader slot, but Commons playback
 * is gone.  We use the slot for a deliberately small compatibility layer that
 * makes the main Pocket Spatial page feed CLEAN stereo into the existing,
 * receiver-tested Lt/Rt-style matrix encoder.
 *
 * Important: this does not replace or monkey-patch the matrix DSP.  It simply
 * parks the old headphone/room-virtualization controls at neutral values and
 * hides them, so the receiver sees the original stereo program plus only the
 * intentional matrix encoding / pseudo-object cues.
 */

function byId(id){return document.getElementById(id);}
function setValue(id,value){var n=byId(id);if(n)n.value=String(value);}
function setText(id,value){var n=byId(id);if(n)n.textContent=value;}
function hideMetric(label){
  var spans=document.querySelectorAll('.metric span');
  for(var i=0;i<spans.length;i+=1){
    if((spans[i].textContent||'').toLowerCase()===label.toLowerCase()){
      var box=spans[i].parentNode;if(box&&box.style)box.style.display='none';
    }
  }
}
function forceNeutralPreMatrix(){
  /* No cross-ear injection, no synthetic reflections, no room-wrap copy. */
  setValue('space',0);
  setValue('angle',0);
  setValue('delayStretch',100);
  setValue('headShadow',3300);
  setValue('polarity',0);
  setValue('depth',0);
  setValue('roomScale',100);
  setValue('roomWrap',0);
  setValue('reflectionTone',3300);
}
function applyReceiverFirstUI(){
  forceNeutralPreMatrix();

  var lab=document.querySelector('.dangerZone');
  if(lab)lab.style.display='none';

  var sub=document.querySelector('.sub');
  if(sub)sub.textContent='Clean stereo in · receiver-first cinema matrix encoding · pseudo-object steering';

  var badge=byId('badge');
  if(badge&&/spatial/i.test(badge.textContent||''))badge.textContent='Matrix encoder off';

  var button=byId('spatial');
  if(button){
    var syncButton=function(){
      var isOn=byId('badge')&&byId('badge').className.indexOf(' on')!==-1;
      var wanted=isOn?'TURN MATRIX ENCODING OFF':'TURN MATRIX ENCODING ON';
      if(button.textContent!==wanted)button.textContent=wanted;
      if(badge){var bWanted=isOn?'Matrix encoder on':'Matrix encoder off';if(badge.textContent!==bWanted)badge.textContent=bWanted;}
    };
    syncButton();
    if(root.MutationObserver){
      var observer=new MutationObserver(syncButton);
      observer.observe(button,{childList:true,characterData:true,subtree:true});
      if(badge)observer.observe(badge,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:['class']});
    }
    button.addEventListener('click',function(){root.setTimeout(syncButton,0);});
  }

  setText('status','Receiver-first mode is ready. Turn Matrix Encoding on and leave the receiver in its Pro Logic / matrix-surround mode.');

  hideMetric('Cross-ear delay');
  hideMetric('Head-shadow LPF');
  hideMetric('Far-ear path');
  hideMetric('Direct path');
  hideMetric('Early arrivals');
  hideMetric('Early gains');
  hideMetric('Room-wrap arrivals');
  hideMetric('Room-wrap gains');
  hideMetric('Reflection LPF');
  hideMetric('Protective output trim');

  var matrixLabel=byId('matrixRead');
  if(matrixLabel&&matrixLabel.parentNode){
    var span=matrixLabel.parentNode.querySelector('span');
    if(span)span.textContent='Receiver matrix encoding';
  }

  var engineCard=document.querySelector('.card .status.good');
  if(engineCard){
    engineCard.innerHTML='<b>RECEIVER-FIRST MATRIX:</b> Pocket Spatial now leaves the incoming stereo program clean before encoding. The receiver, not a headphone-style spatializer, does the surround decoding. The tested rear phase/polarity coefficients and pseudo-object steering remain available.';
  }

  root.PocketSpatialReceiverFirst={
    version:'20260908-receiver-first-1',
    cleanPreMatrix:true,
    neutralize:forceNeutralPreMatrix
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyReceiverFirstUI,{once:true});
else applyReceiverFirstUI();

}(window));
