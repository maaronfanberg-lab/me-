function pointerUp(e){let was=gesture;pointers.delete(e.pointerId);if(was?.type==='node'&&dragNode){dragNode.pinned=false;dragNode=null;dragSample=null;kick(1);toast('Released — neighborhood resettling')}
  if(pointers.size===1){let p=[...pointers.values()][0];gesture={type:'pan',x:p.x,y:p.y,vx:view.x,vy:view.y,moved:false}}else if(!pointers.size){if(was?.type==='pan'&&!was.moved){selected=hit(e.clientX,e.clientY);draw()}gesture=null}}
canvas.addEventListener('pointerup',pointerUp);canvas.addEventListener('pointercancel',pointerUp);
canvas.addEventListener('dblclick',e=>setZoomAt(view.k*1.8,e.clientX,e.clientY));
function updateHeight(){let h=window.visualViewport?.height||window.innerHeight;document.documentElement.style.setProperty('--h',h+'px');resize()}
window.addEventListener('resize',updateHeight);window.visualViewport?.addEventListener('resize',updateHeight);window.visualViewport?.addEventListener('scroll',updateHeight);
updateHeight();ui('Ready');draw();
