canvas.addEventListener('pointerdown',e=>{
  canvas.setPointerCapture?.(e.pointerId);pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});let n=hit(e.clientX,e.clientY);
  if(pointers.size===1&&connectMode&&n){gesture={type:'select',id:e.pointerId,x:e.clientX,y:e.clientY,node:n,moved:false};return}
  if(pointers.size===1&&n){let p=screenToWorld(e.clientX,e.clientY);dragNode=n;selected=n;n.pinned=true;n.vx=n.vy=0;dragSample={x:p.x,y:p.y,t:performance.now()};gesture={type:'node',id:e.pointerId,moved:false};kick(1);draw();return}
  if(pointers.size===1){gesture={type:'pan',x:e.clientX,y:e.clientY,vx:view.x,vy:view.y,moved:false};return}
  if(pointers.size===2){if(dragNode){dragNode.pinned=false;dragNode=null}let a=[...pointers.values()],dx=a[1].x-a[0].x,dy=a[1].y-a[0].y,mx=(a[0].x+a[1].x)/2,my=(a[0].y+a[1].y)/2,w=screenToWorld(mx,my);gesture={type:'pinch',d:Math.hypot(dx,dy)||1,k:view.k,w}}
});
canvas.addEventListener('pointermove',e=>{
  if(!pointers.has(e.pointerId))return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.size>=2){let a=[...pointers.values()].slice(0,2),dx=a[1].x-a[0].x,dy=a[1].y-a[0].y,mx=(a[0].x+a[1].x)/2,my=(a[0].y+a[1].y)/2;if(gesture?.type!=='pinch'){let w=screenToWorld(mx,my);gesture={type:'pinch',d:Math.hypot(dx,dy)||1,k:view.k,w}}let k=Math.max(.002,Math.min(250,gesture.k*Math.hypot(dx,dy)/gesture.d)),r=canvas.getBoundingClientRect();view.k=k;view.x=(mx-r.left)-gesture.w.x*k;view.y=(my-r.top)-gesture.w.y*k;setView();return}
  if(gesture?.type==='select'){if(Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)>7)gesture.moved=true;return}
  if(gesture?.type==='node'&&dragNode){let p=screenToWorld(e.clientX,e.clientY),now=performance.now(),dt=Math.max(8,now-(dragSample?.t||now));dragNode.vx=(p.x-(dragSample?.x||p.x))/(dt/16.67);dragNode.vy=(p.y-(dragSample?.y||p.y))/(dt/16.67);dragNode.x=p.x;dragNode.y=p.y;dragSample={x:p.x,y:p.y,t:now};gesture.moved=true;kick(1);draw();return}
  if(gesture?.type==='pan'){view.x=gesture.vx+e.clientX-gesture.x;view.y=gesture.vy+e.clientY-gesture.y;if(Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y)>4)gesture.moved=true;setView()}
});
