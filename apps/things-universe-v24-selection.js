'use strict';
let connectMode=false, connectSelection=[];
function selNodes(){return connectSelection.map(byId).filter(Boolean)}
function isConnectSelected(n){return !!n&&connectSelection.includes(n.id)}
function renderSelectionMarks(){
  let host=$('#selmarks');if(!host)return;let ns=selNodes();
  while(host.children.length<ns.length){let d=document.createElement('div');d.className='selmark';host.appendChild(d)}
  while(host.children.length>ns.length)host.lastChild.remove();
  ns.forEach((n,i)=>{let d=host.children[i],x=view.x+n.x*view.k,y=view.y+n.y*view.k;d.textContent=String(i+1);d.style.transform=`translate(${x-13}px,${y-13}px)`});
}
function selectionAnimation(){renderSelectionMarks();requestAnimationFrame(selectionAnimation)}
function updateConnectUI(){
  let btn=$('#connect'),bar=$('#selectbar'),txt=$('#seltext'),go=$('#selExplain');
  if(btn){btn.classList.toggle('on',connectMode);btn.textContent=connectMode?`Connect: ${connectSelection.length}/4`:'Connect mode'}
  if(bar)bar.classList.toggle('showbar',connectMode||connectSelection.length>0);
  if(txt){let ns=selNodes();txt.textContent=ns.length?ns.map((n,i)=>`${i+1}. ${n.l}`).join('  ·  '):'Tap 2–4 nodes'}
  if(go)go.disabled=connectSelection.length<2;
  let h=$('#hint');if(h)h.textContent=connectMode?'Tap nodes to select · tap again to remove':'Drag a node to move it';
  draw();
}
function toggleConnectMode(){connectMode=!connectMode;if(connectMode)toast('Connect mode: tap 2–4 nodes');updateConnectUI()}
function toggleConnectNode(n){
  if(!n)return;
  let i=connectSelection.indexOf(n.id);
  if(i>=0)connectSelection.splice(i,1);
  else if(connectSelection.length<4)connectSelection.push(n.id);
  else return toast('You can compare up to 4 nodes');
  selected=n;updateConnectUI();
}
function clearConnectSelection(){connectSelection=[];selected=null;updateConnectUI()}
function edgeBetween(a,b){return L.find(e=>{let x=e.source?.id||e.source,y=e.target?.id||e.target;return(x===a.id&&y===b.id)||(x===b.id&&y===a.id)})}
function pathIds(a,b){
  if(a===b)return[a];let adj=new Map();
  for(const e of L){let x=e.source?.id||e.source,y=e.target?.id||e.target;if(!adj.has(x))adj.set(x,[]);if(!adj.has(y))adj.set(y,[]);adj.get(x).push(y);adj.get(y).push(x)}
  let q=[[a,[a]]],seen=new Set([a]),head=0;
  while(head<q.length){let[c,p]=q[head++];for(const n of adj.get(c)||[]){if(seen.has(n))continue;let np=[...p,n];if(n===b)return np;seen.add(n);q.push([n,np])}}
  return null
}
function pathDetail(ids){
  let ns=(ids||[]).map(byId).filter(Boolean),steps=[];
  for(let i=0;i<ns.length-1;i++){let e=edgeBetween(ns[i],ns[i+1]);steps.push({a:ns[i],b:ns[i+1],rel:e?.rel||'connects to',src:e?.src||''})}
  return{nodes:ns,steps}
}
async function conceptualPathBetween(a,b,maxDepth=3,beam=12,branch=24){
  let direct=pathIds(a.id,b.id);if(direct)return{kind:'visible',ids:direct};
  let frontier=[{k:a.k,steps:[],score:9999}],visited=new Set([a.k]);
  for(let depth=0;depth<maxDepth&&frontier.length;depth++){
    frontier=frontier.sort((x,y)=>y.score-x.score).slice(0,beam);
    let rows=await Promise.all(frontier.map(async st=>({st,cands:(await concepts(st.k)).slice(0,branch)}))),next=new Map();
    for(const {st,cands} of rows)for(const c of cands){
      let step={k:c.k,l:c.l,r:c.r,src:c.src,score:c.score||0};
      if(c.k===b.k)return{kind:'searched',steps:[...st.steps,step]};
      if(visited.has(c.k))continue;let ns={k:c.k,steps:[...st.steps,step],score:(c.score||0)-depth*8},old=next.get(c.k);if(!old||ns.score>old.score)next.set(c.k,ns)
    }
    frontier=[...next.values()];for(const x of frontier)visited.add(x.k)
  }
  return null
}
function relationKind(rel){let r=String(rel||'').toLowerCase();if(/cause|produce|result|lead/.test(r))return'causal';if(/part|contain|include|kind|subtype|has/.test(r))return'structural';if(/use|require|prerequisite|support/.test(r))return'functional';if(/study|field|discipline/.test(r))return'disciplinary';if(/property|quality|describe|symbol/.test(r))return'descriptive';return'conceptual'}
function whySentence(steps){let kinds=[...new Set(steps.map(s=>relationKind(s.rel||s.r)))];if(!kinds.length)return'The connection is supported by explicit conceptual links.';return`Why they connect: this chain is mainly ${kinds.slice(0,3).join(', ')} — the concepts are linked by what they are, what they do, what they belong to, or what they influence rather than by screen proximity.`}
function describeVisiblePath(a,b,res){
  let d=pathDetail(res.ids),lis=d.steps.map(s=>`<li><b>${s.a.l}</b> — ${s.rel} → <b>${s.b.l}</b>${s.src?` <span class="src">(${s.src})</span>`:''}</li>`).join('');
  return{html:`<div class="box"><strong>${a.l} ↔ ${b.l}</strong><ul>${lis}</ul><p>${whySentence(d.steps)}</p></div>`,intermediates:d.nodes.slice(1,-1).map(n=>n.l)}
}
function describeSearchedPath(a,b,res){
  let cur=a.l,lis='',ints=[];
  for(const s of res.steps){lis+=`<li><b>${cur}</b> — ${s.r} → <b>${s.l}</b>${s.src?` <span class="src">(${s.src})</span>`:''}</li>`;cur=s.l;if(s.k!==b.k)ints.push(s.l)}
  return{html:`<div class="box"><strong>${a.l} ↔ ${b.l}</strong><ul>${lis}</ul><p>${whySentence(res.steps)}</p><p>This chain was found by a short conceptual search; it may not yet be drawn in the visible graph.</p></div>`,intermediates:ints}
}
async function explainSelected(){
  let ns=selNodes();if(ns.length<2)return toast('Select at least 2 nodes');
  think(true,'Examining selected concepts…');$('#selExplain').disabled=true;
  try{
    let pairs=[];for(let i=0;i<ns.length;i++)for(let j=i+1;j<ns.length;j++)pairs.push([ns[i],ns[j]]);
    let results=[];
    for(const [a,b] of pairs){let r=await conceptualPathBetween(a,b,3,12,24);if(r){let d=r.kind==='visible'?describeVisiblePath(a,b,r):describeSearchedPath(a,b,r);results.push({a,b,...d,length:r.kind==='visible'?(r.ids.length-1):r.steps.length})}}
    if(!results.length){$('#rb').innerHTML=`<h2>${ns.map(n=>n.l).join(' · ')}</h2><div class="box"><p>I could not find a defensible connection within three conceptual steps. That means the current knowledge sources do not support a short explanation yet — not that the concepts are unrelated.</p></div>`;$('#reader').classList.add('open');return}
    let counts=new Map();for(const r of results)for(const x of r.intermediates)counts.set(x,(counts.get(x)||0)+1);
    let hubs=[...counts].filter(([,c])=>c>1).sort((a,b)=>b[1]-a[1]).slice(0,4).map(x=>x[0]);
    let intro=ns.length===2?`The shortest defensible connection I found between <b>${ns[0].l}</b> and <b>${ns[1].l}</b> is shown below.`:`These ${ns.length} concepts are not being compared by screen distance. I traced explicit conceptual relationships between them and looked for recurring intermediate ideas.`;
    let why=hubs.length?`The strongest common meeting ideas are <b>${hubs.join(', ')}</b>. They recur across more than one selected-pair path, which makes them useful conceptual hubs.`:`The selected concepts connect through different chains rather than one obvious common hub.`;
    let best=results.sort((a,b)=>a.length-b.length).slice(0,Math.max(1,ns.length===2?1:Math.min(5,results.length)));
    $('#rb').innerHTML=`<h2>${ns.map(n=>n.l).join(' ↔ ')}</h2><div class="box"><p>${intro}</p><p>${why}</p></div>${best.map(r=>r.html).join('')}<div class="box"><p><strong>How to read this:</strong> each arrow is an explicit relationship from the graph or the same conceptual sources used to grow it. The explanation does not treat visual closeness as evidence.</p></div>`;
    $('#reader').classList.add('open')
  }finally{think(false);$('#selExplain').disabled=connectSelection.length<2}
}
selectionAnimation();
