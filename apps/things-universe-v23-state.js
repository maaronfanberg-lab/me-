'use strict';
let N=[],L=[],seeds=[],round=0,auto=false,busy=false,token=0,stalls=0,cache=new Map(),states=new Map(),lastBridge=null;
const nid=()=>Math.random().toString(36).slice(2),byK=k=>N.find(n=>n.k===k),byId=i=>N.find(n=>n.id===i),seedById=id=>seeds.find(s=>s.id===id),owners=n=>n.owners||new Set();
function seedLetter(i){return i<26?String.fromCharCode(65+i):String(i+1)}
function sharedCount(){return N.filter(n=>owners(n).size>1).length}
function toast(t){let x=$('#toast');x.textContent=t;x.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>x.classList.remove('show'),2200)}
function think(on,t='Thinking…'){$('#think').textContent=t;$('#think').classList.toggle('show',on)}
function summary(){return seeds.length?seeds.map((s,i)=>`${seedLetter(i)}: <b>${s.label}</b>`).join(' · '):'No starting ideas'}
function ui(t){if(t)$('#status').textContent=t;$('#count').textContent=N.length+' nodes';$('#bc').textContent=sharedCount()+' shared';$('#empty').style.display=N.length?'none':'grid';$('#pair').innerHTML=summary();$('#q').placeholder=seeds.length?'Add another idea':'Type the first idea'}
function state(seed){if(!states.has(seed.id))states.set(seed.id,{q:[],seen:new Set(),done:new Set()});return states.get(seed.id)}
function own(n,seed){let st=state(seed),before=n.owners.size;n.owners.add(seed.id);if(!st.seen.has(n.k)){st.seen.add(n.k);st.q.push(n.k)}if(before&&n.owners.size>before){let o=[...n.owners].find(x=>x!==seed.id);lastBridge={a:o,b:seed.id,node:n.id}}}
function anchor(seed,w,h){let n=seeds.length;if(n===1)return{x:w*.5,y:h*.5};if(n===2)return seed.index?{x:w*.74,y:h*.5}:{x:w*.26,y:h*.5};let a=-Math.PI/2+2*Math.PI*seed.index/n,rx=Math.min(w*.34,360),ry=Math.min(h*.30,260);return{x:w/2+Math.cos(a)*rx,y:h/2+Math.sin(a)*ry}}
function node(term,seed=null,p=null){let k=key(term),n=byK(k);if(!n){let w=$('#stage').clientWidth||700,h=$('#stage').clientHeight||600,a=seed?anchor(seed,w,h):{x:w/2,y:h/2};n={id:nid(),k,l:cap(term),owners:new Set(),x:p?p.x+(Math.random()-.5)*150:a.x,y:p?p.y+(Math.random()-.5)*150:a.y};N.push(n)}if(seed)own(n,seed);return n}
function edge(a,b,r,seedId='',src=''){if(!a||!b||a===b)return;let e=L.find(e=>{let x=e.source.id||e.source,y=e.target.id||e.target;return(x===a.id&&y===b.id)||(x===b.id&&y===a.id)});if(!e){L.push({source:a.id,target:b.id,rel:r,seedId,bridge:a.owners.size>1||b.owners.size>1,src})}else if(a.owners.size>1||b.owners.size>1)e.bridge=true}
