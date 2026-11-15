async function sprout(root,seed,lim=44){
  let a=await concepts(root.k),n=0;
  for(const c of a.slice(0,lim)){
    let existed=!!byK(c.k),q=node(c.l,seed,root);
    if(!existed){placeChild(q,root);n++}
    edge(root,q,c.r,seed.id,c.src)
  }
  render();return n
}
function prepState(seed){let st=state(seed);if(!st.cursor)st.cursor=new Map();if(!Number.isFinite(st.turn))st.turn=0;return st}
async function expand(seed,target=28){
  let st=prepState(seed),added=0,visits=0,maxVisits=Math.max(20,Math.min(72,st.q.length*3||20));
  while(added<target&&visits<maxVisits&&st.q.length){
    if(st.turn>=st.q.length)st.turn=0;
    let k=st.q[st.turn++],p=byK(k);visits++;if(!p)continue;
    let a=await concepts(k),cur=st.cursor.get(k)||0;
    if(cur>=a.length){st.done.add(k);continue}
    let batch=a.slice(cur,cur+12);st.cursor.set(k,cur+batch.length);
    if(cur+batch.length>=a.length)st.done.add(k);else st.done.delete(k);
    for(const c of batch){
      let ex=byK(c.k),had=ex?.owners?.has(seed.id),q=node(c.l,seed,p);
      if(!ex)placeChild(q,p);
      edge(p,q,c.r,seed.id,c.src);
      if(!had)added++;
      if(added>=target)break
    }
  }
  return added
}
function pairs(){let a=[];for(let i=0;i<seeds.length;i++)for(let j=i+1;j<seeds.length;j++)a.push([seeds[i],seeds[j]]);return a}
function touching(a,b){return N.some(n=>n.owners?.has(a.id)&&n.owners?.has(b.id))}
function path(a,b){
  let adj=new Map();
  for(const e of L){let x=e.source.id||e.source,y=e.target.id||e.target;if(!adj.has(x))adj.set(x,[]);if(!adj.has(y))adj.set(y,[]);adj.get(x).push(y);adj.get(y).push(x)}
  let q=[[a,[a]]],seen=new Set([a]),head=0;
  while(head<q.length){let[c,p]=q[head++];if(c===b)return p;for(const n of adj.get(c)||[])if(!seen.has(n)){seen.add(n);q.push([n,[...p,n]])}}
  return null
}
function territoryMap(seed){let m=new Map();for(const n of N)if(n.owners?.has(seed.id))m.set(n.k,n);return m}
function bridgeSources(seed,limit=18){
  let st=state(seed),out=[],seen=new Set(),add=k=>{let n=byK(k);if(n&&n.owners?.has(seed.id)&&!seen.has(k)){seen.add(k);out.push(n)}};
  let root=seed.root?nById(seed.root):null;if(root)add(root.k);
  for(const k of st.q.slice(-10).reverse())add(k);
  for(const k of st.q.slice(0,8))add(k);
  let deg=new Map();for(const e of L){let a=e.source.id||e.source,b=e.target.id||e.target;deg.set(a,(deg.get(a)||0)+1);deg.set(b,(deg.get(b)||0)+1)}
  let ranked=N.filter(n=>n.owners?.has(seed.id)).sort((a,b)=>(deg.get(b.id)||0)-(deg.get(a.id)||0));
  for(const n of ranked)add(n.k);
  return out.slice(0,limit)
}
async function loadNeighborhood(nodes,branch=28){
  let lists=await Promise.all(nodes.map(async n=>({source:n,cands:(await concepts(n.k)).slice(0,branch)})));
  return lists
}
function markBridge(a,b,n){own(n,a);own(n,b);lastBridge={a:a.id,b:b.id,node:n.id};kick(1);render()}
function connectExisting(source,target,cand,a,b){
  edge(source,target,cand.r,a.id,cand.src);
  markBridge(a,b,target);
  return 1
}
function connectSharedCandidate(hitA,hitB,a,b){
  let pa=hitA.source,pb=hitB.source,x=hitA.cand,q=byK(x.k);
  if(!q){q=node(x.l);q.x=(pa.x+pb.x)/2+(Math.random()-.5)*30;q.y=(pa.y+pb.y)/2+(Math.random()-.5)*30;q.depth=Math.max(pa.depth||0,pb.depth||0)+1;q.parentId=pa.id;q.vx=q.vy=0;q.pinned=false}
  own(q,a);own(q,b);
  edge(pa,q,hitA.cand.r,a.id,hitA.cand.src);
  edge(pb,q,hitB.cand.r,b.id,hitB.cand.src);
  lastBridge={a:a.id,b:b.id,node:q.id};kick(1);render();return 1
}
async function quickBridgePair(a,b){
  if(touching(a,b))return 0;
  let A=bridgeSources(a,12),B=bridgeSources(b,12),mapA=territoryMap(a),mapB=territoryMap(b);
  let [na,nb]=await Promise.all([loadNeighborhood(A,26),loadNeighborhood(B,26)]);
  for(const row of na)for(const c of row.cands){let t=mapB.get(c.k);if(t)return connectExisting(row.source,t,c,a,b)}
  for(const row of nb)for(const c of row.cands){let t=mapA.get(c.k);if(t)return connectExisting(row.source,t,c,b,a)}
  let seenA=new Map();
  for(const row of na)for(const c of row.cands){let old=seenA.get(c.k);if(!old||c.score>(old.cand.score||0))seenA.set(c.k,{source:row.source,cand:c})}
  for(const row of nb)for(const c of row.cands){let z=seenA.get(c.k);if(z)return connectSharedCandidate(z,{source:row.source,cand:c},a,b)}
  return 0
}
async function searchToward(fromSeed,toSeed,maxDepth=3,beam=10,branch=22){
  let targets=territoryMap(toSeed),starts=bridgeSources(fromSeed,20);
  for(const s of starts)if(targets.has(s.k))return{start:s,end:targets.get(s.k),steps:[]};
  let frontier=starts.map(n=>({k:n.k,start:n,steps:[],score:9999})),visited=new Set(frontier.map(x=>x.k));
  for(let depth=0;depth<maxDepth&&frontier.length;depth++){
    frontier=frontier.sort((a,b)=>b.score-a.score).slice(0,beam);
    let rows=await Promise.all(frontier.map(async st=>({st,cands:(await concepts(st.k)).slice(0,branch)})));
    let next=new Map();
    for(const {st,cands} of rows){
      for(const c of cands){
        let step={k:c.k,l:c.l,r:c.r,src:c.src,score:c.score||0};
        let target=targets.get(c.k);
        if(target)return{start:st.start,end:target,steps:[...st.steps,step]};
        if(visited.has(c.k))continue;
        let ns={k:c.k,start:st.start,steps:[...st.steps,step],score:(c.score||0)-depth*8};
        let old=next.get(c.k);if(!old||ns.score>old.score)next.set(c.k,ns)
      }
    }
    frontier=[...next.values()];for(const x of frontier)visited.add(x.k)
  }
  return null
}
function materializeSearch(result,fromSeed,toSeed){
  if(!result)return 0;
  let start=result.start,end=result.end,prev=start,total=result.steps.length;
  if(!total){markBridge(fromSeed,toSeed,start);return 1}
  for(let i=0;i<total;i++){
    let s=result.steps[i],final=i===total-1&&s.k===end.k,q=final?end:byK(s.k);
    if(!q){q=node(s.l);let t=(i+1)/(total+1);q.x=start.x+(end.x-start.x)*t+(Math.random()-.5)*35;q.y=start.y+(end.y-start.y)*t+(Math.random()-.5)*35;q.depth=Math.max(start.depth||0,end.depth||0)+i+1;q.parentId=prev.id;q.vx=q.vy=0;q.pinned=false}
    own(q,fromSeed);own(q,toSeed);edge(prev,q,s.r,fromSeed.id,s.src);prev=q
  }
  own(end,fromSeed);own(end,toSeed);lastBridge={a:fromSeed.id,b:toSeed.id,node:end.id};kick(1);render();return 1
}
async function deepBridgePair(a,b){
  if(touching(a,b))return 0;
  let z=await searchToward(a,b,3,10,22);if(z)return materializeSearch(z,a,b);
  z=await searchToward(b,a,3,10,22);if(z)return materializeSearch(z,b,a);
  return 0
}
async function bridge(){
  for(const[a,b]of pairs()){if(touching(a,b))continue;let z=await quickBridgePair(a,b);if(z)return z}
  return 0
}
async function step(){
  if(busy||!seeds.length)return 0;busy=true;round++;think(true,'Concept round '+round+'…');let total=0,parts=[];
  try{
    let perf=N.length>2500?.28:N.length>1400?.52:1,base=seeds.length<=2?30:seeds.length<=4?20:13,target=Math.max(5,Math.round(base*perf));
    for(let i=0;i<seeds.length;i++){let z=await expand(seeds[i],target);total+=z;parts.push(`${seedLetter(i)}+${z}`)}
    if(seeds.length>1)total+=await bridge();stalls=total?0:stalls+1;ui(`Round ${round} · ${parts.join(' ')}${total?'':' · widening'}`);
    if(!total&&stalls%3===0){cache.clear();for(const s of states.values()){s.done.clear();if(s.cursor)s.cursor.clear();s.turn=0}toast('Widening the conceptual search — Auto-grow stays on.')}
    render();return total
  }finally{busy=false;think(false)}
}
async function addThing(t){
  let k=key(t);if(!k)return;if(seeds.some(s=>s.k===k))return toast('That idea is already a starting territory');
  let existing=byK(k),seed={id:'s'+nid(),k,label:cap(t),index:seeds.length,root:null};seeds.push(seed);let r=node(t,seed);seed.root=r.id;
  if(!existing)placeSeed(r,seed);reflowSeedIslands();state(seed);indexAll();render();think(true,'Opening a broad floating territory…');
  try{await sprout(r,seed,44)}catch(e){toast('Seed added — outside sources are slow, built-in growth still works.')}finally{think(false)}
  round=stalls=0;render();setTimeout(fit,300)
}
async function loop(t){while(auto&&t===token){let z=await step(),delay=N.length>2200?1700:N.length>1200?1050:z?560:Math.min(4500,1100+stalls*300);await new Promise(r=>setTimeout(r,delay))}}
function toggle(){if(auto){auto=false;token++;$('#auto').classList.remove('on');$('#auto').textContent='Auto-grow: off';return}if(!seeds.length)return toast('Add an idea first');auto=true;stalls=0;let t=++token;$('#auto').classList.add('on');$('#auto').textContent='Auto-grow: on';loop(t)}
async function findBridge(){
  if(seeds.length<2)return toast('Add at least two ideas');
  let before=sharedCount();$('#bridge').disabled=true;think(true,'Searching multi-step conceptual paths…');
  try{
    for(const[a,b]of pairs()){if(touching(a,b))continue;if(await quickBridgePair(a,b)){explain();return}if(await deepBridgePair(a,b)){explain();return}}
    for(let pass=0;pass<3&&sharedCount()===before;pass++){
      await step();
      for(const[a,b]of pairs()){if(touching(a,b))continue;if(await deepBridgePair(a,b)){explain();return}}
    }
    sharedCount()>before?explain():toast('No bridge found within a 3-step conceptual search yet — Auto-grow can keep widening.')
  }finally{$('#bridge').disabled=false;think(false)}
}
function bestPair(){if(lastBridge){let a=seedById(lastBridge.a),b=seedById(lastBridge.b);if(a&&b)return[a,b]}for(const[a,b]of pairs())if(touching(a,b))return[a,b];return null}
function explain(){
  let p=bestPair();if(!p)return toast('No connected territories yet');let[a,b]=p,ids=path(a.root,b.root)||[],ns=ids.map(byId),li='';
  for(let i=0;i<ns.length-1;i++){let e=L.find(e=>{let x=e.source.id||e.source,y=e.target.id||e.target;return(x===ns[i].id&&y===ns[i+1].id)||(y===ns[i].id&&x===ns[i+1].id)});li+=`<li><b>${ns[i].l}</b> — ${e?.rel||'connects to'} → <b>${ns[i+1].l}</b></li>`}
  $('#rb').innerHTML=`<h2>${a.label} ↔ ${b.label}</h2><div class="box"><strong>Conceptual chain</strong><ul>${li}</ul></div><div class="box"><p>Every visible step is an explicit conceptual relationship. v21 searches direct overlaps, shared conceptual neighborhoods, and short multi-step paths instead of requiring the same immediate candidate on both sides.</p></div>`;$('#reader').classList.add('open')
}
function reset(){auto=false;token++;N=[];L=[];seeds=[];round=stalls=0;cache.clear();states.clear();childCounts.clear();nodeIndex.clear();edgeKeys.clear();lastBridge=null;selected=null;dragNode=null;energy=0;view={x:0,y:0,k:1};$('#auto').classList.remove('on');$('#auto').textContent='Auto-grow: off';render();ui('Ready')}
function resize(){let r=$('#stage').getBoundingClientRect();width=Math.max(1,r.width);height=Math.max(1,r.height);dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);canvas.style.width=width+'px';canvas.style.height=height+'px';draw()}
function hit(clientX,clientY){let p=screenToWorld(clientX,clientY),tol=Math.max(8/view.k,4),best=null,d=Infinity;for(const n of N){let q=Math.hypot(n.x-p.x,n.y-p.y);if(q<tol&&q<d){best=n;d=q}}return best}
