(function(root){
'use strict';

var player=root.PocketSpatialBufferedPlayer||root.PocketSpatialBufferedCommons;
var activeControl=null;
var activeDiagnostic=null;
var activePageId=null;
var originalToggle;

if(!player||typeof player.toggle!=='function')return;
originalToggle=player.toggle;

function clearActive(){
  activeControl=null;
  activeDiagnostic=null;
  activePageId=null;
}

function resetPrevious(){
  if(activeControl){
    activeControl.disabled=false;
    activeControl.textContent='BUFFER + PLAY IMMERSIVE';
  }
  if(activeDiagnostic){
    activeDiagnostic.textContent='Stopped because another track started.';
    activeDiagnostic.className='status';
  }
}

player.toggle=function(track,control,diagnostic){
  var pageId=track&&track.pageid;
  if(activeControl&&activeControl!==control)resetPrevious();
  originalToggle.call(player,track,control,diagnostic);
  if(control&&control.textContent==='BUFFER + PLAY IMMERSIVE'){
    clearActive();
    return;
  }
  activeControl=control||null;
  activeDiagnostic=diagnostic||null;
  activePageId=pageId==null?null:pageId;
};

player.singlePlaybackState=function(){
  return{pageid:activePageId,hasControl:!!activeControl,hasDiagnostic:!!activeDiagnostic};
};

}(this));
