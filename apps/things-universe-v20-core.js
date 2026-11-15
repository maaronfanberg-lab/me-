'use strict';
const canvas=$('#canvas'),ctx=canvas.getContext('2d',{alpha:true});
let width=1,height=1,dpr=1,view={x:0,y:0,k:1},pointers=new Map(),gesture=null,selected=null;
let raf=0,energy=0,lastFrame=0,dragNode=null,dragSample=null;
const GOLDEN=2.399963229728653,childCounts=new Map();
const nodeIndex=new Map(),edgeKeys=new Set();

function hash(s){let h=2166136261;for(let i=0;i<String(s).length;i++){h^=String(s).charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function indexAll(){nodeIndex.clear();for(const n of N)nodeIndex.set(n.id,n)}
function nById(id){return nodeIndex.get(id)||byId(id)}
function rebuildEdgeKeys(){edgeKeys.clear();for(const e of L){let a=e.source?.id||e.source,b=e.target?.id||e.target;edgeKeys.add(a<b?a+'|'+b:b+'|'+a)}}
function setView(){ $('#zoomPct').textContent=Math.round(view.k*100)+'%'; draw(); }
function screenToWorld(x,y){let r=canvas.getBoundingClientRect();return{x:(x-r.left-view.x)/view.k,y:(y-r.top-view.y)/view.k}}
function setZoomAt(k,cx,cy){k=Math.max(.002,Math.min(250,k));let r=canvas.getBoundingClientRect(),sx=cx-r.left,sy=cy-r.top,wx=(sx-view.x)/view.k,wy=(sy-view.y)/view.k;view.k=k;view.x=sx-wx*k;view.y=sy-wy*k;setView()}
function nodeColor(n){if(n.owners.size>1)return'#b7a0ff';let s=seedById([...n.owners][0]);return COLORS[(s?.index||0)%COLORS.length]}
function seedPosition(seed){
  if(seeds.length===1)return{x:width/2,y:height/2};
  if(seeds.length===2)return seed.index?{x:width*.79,y:height*.54}:{x:width*.21,y:height*.46};
  let a=-Math.PI/2+2*Math.PI*seed.index/seeds.length,rx=Math.max(280,Math.min(width*.46,760)),ry=Math.max(220,Math.min(height*.42,560));
  return{x:width/2+Math.cos(a)*rx,y:height/2+Math.sin(a)*ry}
}
function ownerAnchor(n){let ss=[...n.owners].map(seedById).filter(Boolean);if(!ss.length)return{x:width/2,y:height/2};let ps=ss.map(seedPosition);return{x:ps.reduce((a,p)=>a+p.x,0)/ps.length,y:ps.reduce((a,p)=>a+p.y,0)/ps.length}}
function placeSeed(n,seed){let p=seedPosition(seed);n.x=p.x;n.y=p.y;n.depth=0;n.parentId=null;n.vx=0;n.vy=0;n.pinned=false}
function reflowSeedIslands(){
  for(const s of seeds){let r=s.root?nById(s.root):null;if(!r||r.owners.size>1)continue;let p=seedPosition(s),dx=p.x-r.x,dy=p.y-r.y;if(!dx&&!dy)continue;for(const n of N)if(n.owners?.size===1&&n.owners.has(s.id)&&!n.pinned){n.x+=dx;n.y+=dy}if(!r.pinned){r.x=p.x;r.y=p.y}}
  kick(.45)
}
function branchAngle(parent,n,siblings){
  let g=parent.parentId?nById(parent.parentId):null,base;
  if(g)base=Math.atan2(parent.y-g.y,parent.x-g.x);else{let s=seedById([...parent.owners][0]);base=s?(-Math.PI/2+GOLDEN*s.index):((hash(parent.k)%6283)/1000)}
  let jitter=((hash((n.k||n.l)+'|'+parent.id)%10000)/10000-.5)*1.95,fan=(siblings%9-4)*.15;
  return base+jitter+fan
}
function placeChild(n,parent){let siblings=childCounts.get(parent.id)||0;childCounts.set(parent.id,siblings+1);let depth=(parent.depth||0)+1,angle=branchAngle(parent,n,siblings),r=86+Math.min(250,depth*17)+Math.sqrt(Math.max(1,siblings))*10;n.parentId=parent.id;n.depth=depth;n.x=parent.x+Math.cos(angle)*r;n.y=parent.y+Math.sin(angle)*r;n.vx=(Math.random()-.5)*.8;n.vy=(Math.random()-.5)*.8;n.pinned=false}
function linkEnds(e){return[typeof e.source==='object'?e.source:nById(e.source),typeof e.target==='object'?e.target:nById(e.target)]}
function hasEdge(a,b){let x=a.id<b.id?a.id+'|'+b.id:b.id+'|'+a.id;return edgeKeys.has(x)}
function rootIdSet(){return new Set(seeds.map(s=>s.root))}

function draw(){
  if(!ctx)return;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);ctx.translate(view.x,view.y);ctx.scale(view.k,view.k);
  let k=view.k,margin=150/k,minX=(-view.x)/k-margin,maxX=(width-view.x)/k+margin,minY=(-view.y)/k-margin,maxY=(height-view.y)/k+margin;
  let visible=new Set(N.filter(n=>n.x>=minX&&n.x<=maxX&&n.y>=minY&&n.y<=maxY).map(n=>n.id)),roots=rootIdSet();ctx.lineCap='round';
  for(const e of L){let[a,b]=linkEnds(e);if(!a||!b||(!visible.has(a.id)&&!visible.has(b.id)))continue;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);let shared=e.bridge||a.owners.size>1||b.owners.size>1;ctx.strokeStyle=shared?'rgba(219,201,139,.34)':'rgba(120,229,221,.14)';ctx.lineWidth=(shared?.8:.38)/Math.max(.34,Math.sqrt(k));if(shared)ctx.setLineDash([4/k,6/k]);else ctx.setLineDash([]);ctx.stroke()}
  ctx.setLineDash([]);let showLabels=N.length<90?k>.44:N.length<350?k>.76:k>1.08,showEdgeLabels=k>2.5&&N.length<400;
  if(showEdgeLabels){ctx.font='5.5px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif';ctx.fillStyle='rgba(185,198,219,.62)';for(const e of L){let[a,b]=linkEnds(e);if(!a||!b||(!visible.has(a.id)&&!visible.has(b.id)))continue;let txt=(e.rel||'').slice(0,26);ctx.strokeStyle='rgba(7,16,24,.96)';ctx.lineWidth=2/k;ctx.strokeText(txt,(a.x+b.x)/2,(a.y+b.y)/2);ctx.fillText(txt,(a.x+b.x)/2,(a.y+b.y)/2)}}
  for(const n of N){if(!visible.has(n.id))continue;let root=roots.has(n.id),r=root?6.2:n.owners.size>1?3.3:1.75;ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);ctx.fillStyle=nodeColor(n);ctx.globalAlpha=n===selected||n===dragNode?1:.9;ctx.fill();if(n===selected||n===dragNode){ctx.strokeStyle='#fff';ctx.lineWidth=1.1/k;ctx.stroke()}ctx.globalAlpha=1;if(showLabels||root||n===selected||n===dragNode){let fs=Math.max(5.8,Math.min(9.5,7.5/Math.sqrt(Math.max(.32,k)))),txt=n.l.length>36?n.l.slice(0,34)+'…':n.l;ctx.font=`${fs}px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif`;ctx.strokeStyle='rgba(7,16,24,.98)';ctx.lineWidth=2.6/k;ctx.fillStyle='#eaf2ff';ctx.strokeText(txt,n.x+r+2.7,n.y+2.5);ctx.fillText(txt,n.x+r+2.7,n.y+2.5)}}
  ctx.setTransform(dpr,0,0,dpr,0,0)
}
function render(){indexAll();rebuildEdgeKeys();ui();draw();kick(.5)}
function fit(){if(!N.length)return;let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;for(const n of N){minX=Math.min(minX,n.x);maxX=Math.max(maxX,n.x);minY=Math.min(minY,n.y);maxY=Math.max(maxY,n.y)}let bw=Math.max(100,maxX-minX),bh=Math.max(100,maxY-minY),k=Math.max(.002,Math.min(12,.84/Math.max(bw/width,bh/height))),cx=(minX+maxX)/2,cy=(minY+maxY)/2;view={k,x:width/2-cx*k,y:height/2-cy*k};setView()}

function kick(v=.7){energy=Math.max(energy,v);if(!raf){lastFrame=performance.now();raf=requestAnimationFrame(physicsFrame)}}
function physicsFrame(now){raf=0;let dt=Math.min(2.2,Math.max(.45,(now-lastFrame)/16.67));lastFrame=now;if(!N.length){energy=0;draw();return}
  let a=Math.max(.012,energy),roots=rootIdSet();
  // link springs: soft and deliberately long so each topic breathes
  for(const e of L){let[x,y]=linkEnds(e);if(!x||!y)continue;let dx=y.x-x.x,dy=y.y-x.y,d=Math.hypot(dx,dy)||1,shared=e.bridge||x.owners.size>1||y.owners.size>1,want=shared?185:125+Math.min(55,Math.max(x.depth||0,y.depth||0)*4),f=(d-want)*.0042*a,fx=dx/d*f,fy=dy/d*f;if(!x.pinned){x.vx=(x.vx||0)+fx;x.vy=(x.vy||0)+fy}if(!y.pinned){y.vx=(y.vx||0)-fx;y.vy=(y.vy||0)-fy}}
  // weak territorial pull; enough to separate topics, not enough to collapse them
  for(const n of N){if(n.pinned)continue;let p=ownerAnchor(n),root=roots.has(n.id),strength=root?.0018:.00028;n.vx=(n.vx||0)+(p.x-n.x)*strength*a;n.vy=(n.vy||0)+(p.y-n.y)*strength*a}
  // repulsion/collision. exact for small graphs; sampled for big graphs.
  const repel=(x,y)=>{let dx=y.x-x.x,dy=y.y-x.y,d2=dx*dx+dy*dy+12;if(d2>520*520)return;let d=Math.sqrt(d2),min=24,f=(d<min?(min-d)*.055:Math.min(.75,1500/d2))*a,fx=dx/d*f,fy=dy/d*f;if(!x.pinned){x.vx-=fx;x.vy-=fy}if(!y.pinned){y.vx+=fx;y.vy+=fy}};
  let n=N.length;if(n<420){for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)repel(N[i],N[j])}else{let tries=Math.min(22000,n*30);for(let q=0;q<tries;q++){let i=(Math.random()*n)|0,j=(Math.random()*n)|0;if(i!==j)repel(N[i],N[j])}}
  // tiny low-frequency drift gives the early "floating" feel while active
  let t=now*.00035;for(const n of N){if(n.pinned)continue;let h=hash(n.id)%1000;n.vx+=(Math.sin(t+h)*.0025)*a;n.vy+=(Math.cos(t*.87+h*.37)*.0025)*a;let damp=Math.pow(.91,dt);n.vx=(n.vx||0)*damp;n.vy=(n.vy||0)*damp;n.x+=n.vx*dt;n.y+=n.vy*dt}
  energy*=Math.pow(auto?0.992:0.978,dt);draw();if(energy>.008||dragNode){raf=requestAnimationFrame(physicsFrame)}else energy=0
}
