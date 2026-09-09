(function(root){
'use strict';

/*
 * Receiver-first mode.
 *
 * This file remains in the historical Commons loader slot, but Commons playback
 * is gone. We use the slot for a deliberately small compatibility layer that
 * makes the main Pocket Spatial page feed clean stereo into the existing,
 * receiver-tested Lt/Rt-style matrix encoder.
 *
 * Receiver-first deliberately parks two layers that were masking the baseline:
 * the old headphone/room virtualization and the adaptive pseudo-object overlay.
 * The fixed receiver-tested matrix stays fully active and unchanged.
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
function forceFixedMatrix(){
  /*
   * The adaptive layer used to reduce the proven base rear matrix to 35% while
   * waiting for object confidence. Receiver-first removes that blocker entirely:
   * use the full fixed matrix first, then add adaptive ideas back only after the
   * baseline is audibly proven again.
   */
  if(root.PocketSpatialAdaptiveSteering&&typeof root.PocketSpatialAdaptiveSteering.setEnabled==='function'){
    root.PocketSpatialAdaptiveSteering.setEnabled(false);
    return true;
  }
  var adaptive=byId('adaptiveSteering');
  if(adaptive&&/ON/i.test(adaptive.textContent||'')){
    try{adaptive.click();return true;}catch(e){}
  }
  return false;
}
function applyReceiverFirstUI(){
  forceNeutralPreMatrix();
  forceFixedMatrix();
  /* Retry once in case the main inline script finished a fraction later. */
  root.setTimeout(function(){forceNeutralPreMatrix();forceFixedMatrix();},50);

  var lab=document.querySelector('.dangerZone');
  if(lab)lab.style.display='none';

  var sub=document.querySelector('.sub');
  if(sub)sub.textContent='Clean stereo in · full receiver-tested matrix encoding · no masking layers';

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

  var adaptiveButton=byId('adaptiveSteering');
  if(adaptiveButton)adaptiveButton.style.display='none';
  var adaptiveStatus=byId('adaptiveStatus');
  if(adaptiveStatus){
    adaptiveStatus.textContent='Adaptive overlay parked. Receiver-first is using the full fixed matrix with the receiver-tested rear phase/polarity coefficients.';
    adaptiveStatus.className='status good';
  }

  setText('status','Receiver-first baseline is ready. Turn Matrix Encoding on and leave the receiver in its Pro Logic / matrix-surround mode.');

  hideMetric('Pseudo-object engine');
  hideMetric('Program width');
  hideMetric('Voice/mid center confidence');
  hideMetric('Air/reverb surround confidence');
  hideMetric('L/R balance');
  hideMetric('Voice/mid center send');
  hideMetric('Air/reverb rear send');
  hideMetric('Presence front lock');
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
    engineCard.innerHTML='<b>RECEIVER-FIRST MATRIX:</b> Clean stereo goes straight to the full receiver-tested fixed matrix. The headphone-style immersion layer and adaptive pseudo-object attenuation are parked so nothing weakens the proven rear encoding.';
  }

  root.PocketSpatialReceiverFirst={
    version:'20260908-receiver-first-2',
    cleanPreMatrix:true,
    fixedMatrixOnly:true,
    neutralize:forceNeutralPreMatrix,
    forceFixedMatrix:forceFixedMatrix
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyReceiverFirstUI,{once:true});
else applyReceiverFirstUI();

}(window));
