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
 * Receiver-first deliberately parks layers that were masking the baseline:
 * the old headphone/room virtualization and the adaptive pseudo-object overlay.
 * It also keeps bass/front-center material out of unnecessary additive matrix
 * reinforcement by using the receiver's natural L+R center decode instead.
 */

function byId(id){return document.getElementById(id);}
function setValue(id,value){var n=byId(id);if(n)n.value=String(value);}
function setText(id,value){var n=byId(id);if(n)n.textContent=value;}
function fireInput(id){
  var n=byId(id);if(!n)return;
  try{n.dispatchEvent(new Event('input',{bubbles:true}));}catch(e){}
}
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
  /* Use the full fixed receiver-tested matrix, never the 35% adaptive base. */
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
function forceMusicMatrixBaseline(){
  /*
   * Bass protection:
   * 1) Do not add the broadband Center Anchor copy. Ordinary in-phase L+R
   *    already decodes to center in a matrix receiver; the extra copy was also
   *    reinforcing centered bass and could drive the output limiter harder.
   * 2) Raise separation to the encoder's 0.96 cross ceiling. This makes the
   *    surround extraction much closer to a pure L-R difference, so common
   *    kick/bass energy largely stays out of the phase-shifted rear branch.
   *
   * The empirically proven rear output coefficients themselves are untouched.
   */
  setValue('centerAnchor',0);
  setValue('steerSep',126);
  fireInput('centerAnchor');
  fireInput('steerSep');
}
function applyReceiverFirstUI(){
  forceNeutralPreMatrix();
  forceFixedMatrix();
  forceMusicMatrixBaseline();
  /* Retry once in case the main inline script finished a fraction later. */
  root.setTimeout(function(){forceNeutralPreMatrix();forceFixedMatrix();forceMusicMatrixBaseline();},50);

  var lab=document.querySelector('.dangerZone');
  if(lab)lab.style.display='none';

  var sub=document.querySelector('.sub');
  if(sub)sub.textContent='Clean stereo in · bass-protected receiver matrix · no masking layers';

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
    adaptiveStatus.textContent='Adaptive overlay parked. Bass protection is active: no extra broadband center copy, and rear extraction is near-pure L-R difference.';
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
    engineCard.innerHTML='<b>RECEIVER-FIRST MATRIX:</b> Clean stereo goes to the full fixed receiver-tested matrix. Bass/front-center material is protected from unnecessary additive encoding, while the proven rear phase/polarity coefficients remain untouched.';
  }

  root.PocketSpatialReceiverFirst={
    version:'20260908-receiver-first-3',
    cleanPreMatrix:true,
    fixedMatrixOnly:true,
    bassProtected:true,
    neutralize:forceNeutralPreMatrix,
    forceFixedMatrix:forceFixedMatrix,
    forceMusicMatrixBaseline:forceMusicMatrixBaseline
  };
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',applyReceiverFirstUI,{once:true});
else applyReceiverFirstUI();

}(window));
