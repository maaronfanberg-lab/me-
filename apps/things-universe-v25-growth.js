'use strict';
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
function territoryMap(seed){let m=new Map();for(const n of N)if(n.owners?.has(seed.id))m.set(n.k,n);return m}
async function step(){
  if(busy||!seeds.length)return 0;busy=true;round++;think(true,'Concept round '+round+'…');let total=0,parts=[];
  try{
    let perf=N.length>2500?.28:N.length>1400?.52:1,base=seeds.length<=2?30:seeds.length<=4?20:13,target=Math.max(5,Math.round(base*perf));
    for(let i=0;i<seeds.length;i++){let z=await expand(seeds[i],target);total+=z;parts.push(`${seedLetter(i)}+${z}`)}
    stalls=total?0:stalls+1;ui(`Round ${round} · ${parts.join(' ')}${total?'':' · widening'}`);
    if(!total&&stalls%3===0){cache.clear();for(const s of states.values()){s.done.clear();if(s.cursor)s.cursor.clear();s.turn=0}toast('Widening the conceptual territories — Auto-grow stays on.')}
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
function reset(){auto=false;token++;N=[];L=[];seeds=[];round=stalls=0;cache.clear();states.clear();childCounts.clear();nodeIndex.clear();edgeKeys.clear();lastBridge=null;selected=null;dragNode=null;energy=0;view={x:0,y:0,k:1};$('#auto').classList.remove('on');$('#auto').textContent='Auto-grow: off';render();ui('Ready')}
function resize(){let r=$('#stage').getBoundingClientRect();width=Math.max(1,r.width);height=Math.max(1,r.height);dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);canvas.style.width=width+'px';canvas.style.height=height+'px';draw()}
function hit(clientX,clientY){let p=screenToWorld(clientX,clientY),tol=Math.max(8/view.k,4),best=null,d=Infinity;for(const n of N){let q=Math.hypot(n.x-p.x,n.y-p.y);if(q<tol&&q<d){best=n;d=q}}return best}
