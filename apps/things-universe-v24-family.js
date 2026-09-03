'use strict';

// v24 family/relationship layer. It changes what can be learned and what can be
// temporarily shown, but deliberately leaves the existing motion/physics intact.
let v24ResultFilter='all';

const V24_FAMILY_RE=/\b(father|mother|parent|child|son|daughter|sibling|brother|sister|spouse|husband|wife|aunt|uncle|niece|nephew|cousin|grandfather|grandmother|grandparent|ancestor|descendant|in-law|by marriage|married)\b/i;
const V24_SURNAME_RE=/\b(surname|family name|last name|patronym|matronym|name variant|variant spelling)\b/i;
const V24_PLACE_RE=/\b(location|place|country|city|town|village|county|region|geograph|born|birthplace|died|death place|originated in|from)\b/i;
const V24_PERSON_SRC_RE=/\b(WikiTree|FamilySearch|OpenAlex|Crossref|Open Library)\b/i;

function v24RelationClass(rel='',src='',kind=''){
  let k=String(kind||'').toLowerCase(),r=String(rel||''),s=String(src||'');
  if(k==='family'||V24_FAMILY_RE.test(r))return'family';
  if(k==='surname'||V24_SURNAME_RE.test(r))return'surname';
  if(k==='place'||V24_PLACE_RE.test(r))return'places';
  if(k==='people'||V24_PERSON_SRC_RE.test(s))return'people';
  return'other'
}

const v24EdgeBase=edge;
edge=function(a,b,r,seedId='',src='',kind=''){
  v24EdgeBase(a,b,r,seedId,src);
  if(!a||!b)return;
  let e=L.find(e=>{let x=e.source?.id||e.source,y=e.target?.id||e.target;return(x===a.id&&y===b.id)||(x===b.id&&y===a.id)});
  if(e&&kind)e.kind=kind
};

function v24EdgeMatches(e,filter=v24ResultFilter){
  if(filter==='all')return true;
  let cls=v24RelationClass(e?.rel,e?.src,e?.kind);
  if(filter==='people')return cls==='people'||cls==='family'||cls==='surname'||V24_PERSON_SRC_RE.test(String(e?.src||''));
  if(filter==='other')return !['family','surname','places','people'].includes(cls);
  return cls===filter
}

function v24VisibleIds(){
  if(v24ResultFilter==='all')return null;
  let ids=new Set(seeds.map(s=>s.root).filter(Boolean));
  for(const e of L)if(v24EdgeMatches(e)){let a=e.source?.id||e.source,b=e.target?.id||e.target;if(a)ids.add(a);if(b)ids.add(b)}
  return ids
}

const v24DrawBase=draw;
draw=function(){
  if(v24ResultFilter==='all')return v24DrawBase();
  let ids=v24VisibleIds(),allN=N,allL=L;
  N=allN.filter(n=>ids.has(n.id));L=allL.filter(e=>v24EdgeMatches(e)&&ids.has(e.source?.id||e.source)&&ids.has(e.target?.id||e.target));
  try{return v24DrawBase()}finally{N=allN;L=allL}
};

const v24FitBase=fit;
fit=function(){
  if(v24ResultFilter==='all')return v24FitBase();
  let ids=v24VisibleIds(),allN=N,allL=L;
  N=allN.filter(n=>ids.has(n.id));L=allL.filter(e=>v24EdgeMatches(e));
  try{return v24FitBase()}finally{N=allN;L=allL}
};

const v24HitBase=hit;
hit=function(clientX,clientY){
  if(v24ResultFilter==='all')return v24HitBase(clientX,clientY);
  let ids=v24VisibleIds(),p=screenToWorld(clientX,clientY),tol=Math.max(8/view.k,4),best=null,d=Infinity;
  for(const n of N){if(!ids.has(n.id))continue;let q=Math.hypot(n.x-p.x,n.y-p.y);if(q<tol&&q<d){best=n;d=q}}
  return best
};

if(typeof renderSelectionMarks==='function'){
  const v24MarksBase=renderSelectionMarks;
  renderSelectionMarks=function(){
    if(v24ResultFilter==='all')return v24MarksBase();
    let ids=v24VisibleIds(),all=connectSelection;connectSelection=all.filter(id=>ids.has(id));
    try{return v24MarksBase()}finally{connectSelection=all}
  }
}

function v24InstallFilter(){
  let tools=document.querySelector('.tools');if(!tools||document.querySelector('#resultFilter'))return;
  let select=document.createElement('select');select.id='resultFilter';select.className='btn';select.setAttribute('aria-label','Filter visible results');
  select.innerHTML='<option value="all">Filter: All</option><option value="family">Family</option><option value="surname">Surname</option><option value="people">People</option><option value="places">Places</option><option value="other">Sources / other</option>';
  select.addEventListener('change',()=>{v24ResultFilter=select.value||'all';selected=null;draw();toast(v24ResultFilter==='all'?'Showing all results':`Showing ${select.options[select.selectedIndex].text.toLowerCase()}`)});
  tools.appendChild(select)
}

// Preserve subject/object family facts from the relay. A row can now mean
// "Oscar Fanberg --father of--> Daniel Fanberg" even when the enrichment job
// itself was started from the surname Fanberg.
const v24RowsBase=v24ProgressRows;
v24ProgressRows=function(data,term){
  let out=[],phase=data?.phase==='evidence'?'multi-source evidence':data?.phase==='family'?'family evidence':'Falcon synthesis';
  for(const row of data?.relations||[]){
    let lab=String(row?.label||'').trim(),rel=String(row?.relation||'').trim(),subject=String(row?.subject||'').trim();
    let sources=Array.isArray(row?.sources)?row.sources.map(String).filter(Boolean).slice(0,4):[];
    let confidence=Number(row?.confidence);if(!Number.isFinite(confidence))confidence=.5;
    if(confidence<.5||!lab||!rel||!sources.length||!candidateAllowed(lab,term,phase))continue;
    let q=key(lab),from=subject||term;if(!q)continue;
    if(q===key(term)&&key(from)===key(term))continue;
    let kind=String(row?.kind||v24RelationClass(rel,sources.join(' + '),'')).toLowerCase();
    out.push({k:q,l:cap(lab),r:rel,score:170+Math.round(Math.max(0,Math.min(1,confidence))*140),src:`${phase} · ${sources.join(' + ')}`,from,origin:term,kind});
  }
  return out.slice(0,44)
};

const v24MergeProgressBase=v24MergeProgressCache;
v24MergeProgressCache=function(term,rows){
  // Pairwise family facts belong between their two people, not between the
  // original surname/search term and whichever endpoint happened to be returned.
  let direct=(rows||[]).filter(x=>!x.from||key(x.from)===key(term));
  return v24MergeProgressBase(term,direct)
};

v24ScheduleProgress=function(parent,seed,rows){
  let watchKey=`${seed.id}|${parent.id}`,seen=v24ProgressWatches.get(watchKey);if(!seen)return;
  let fresh=[];
  for(const c of rows||[]){let rk=`${key(c.from||parent.k)}|${c.k}|${c.r}`;if(seen.has(rk))continue;seen.add(rk);fresh.push(c)}
  fresh.slice(0,44).forEach((c,i)=>setTimeout(()=>{
    let liveParent=nById(parent.id),liveSeed=seedById(seed.id);if(!liveParent||!liveSeed||!liveParent.owners?.has(liveSeed.id))return;
    let sourceNode=liveParent,sourceKey=key(c.from||liveParent.k),sourceWas=false;
    if(sourceKey&&sourceKey!==key(liveParent.k)){
      sourceNode=byK(sourceKey);sourceWas=!!sourceNode;
      if(!sourceNode){sourceNode=node(c.from,liveSeed,liveParent);placeChild(sourceNode,liveParent)}else own(sourceNode,liveSeed)
    }
    let q=byK(c.k),targetWas=!!q;
    if(!q){q=node(c.l,liveSeed,sourceNode);placeChild(q,sourceNode)}else own(q,liveSeed);
    if(sourceNode===q)return;
    let wasLinked=hasEdge(sourceNode,q);edge(sourceNode,q,c.r,liveSeed.id,c.src,c.kind);
    if(!sourceWas||!targetWas||!wasLinked)render()
  },i*420))
};

if(typeof relationKind==='function'){
  const v24RelationKindBase=relationKind;
  relationKind=function(rel){let c=v24RelationClass(rel,'','');if(c==='family'||c==='surname')return c;return v24RelationKindBase(rel)}
}
if(typeof whySentence==='function'){
  const v24WhyBase=whySentence;
  whySentence=function(steps){
    let kinds=[...new Set((steps||[]).map(s=>relationKind(s.rel||s.r)))];
    if(kinds.includes('family'))return'Why they connect: this chain includes documented family relationships. Surname similarity is not being used as proof of biological relationship.';
    if(kinds.includes('surname'))return'Why they connect: this is surname or name-relatedness. Sharing a surname is meaningful here, but by itself it does not prove a common ancestor.';
    return v24WhyBase(steps)
  }
}

v24InstallFilter();
