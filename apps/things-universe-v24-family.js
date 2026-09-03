'use strict';

// v24 family/relationship layer. It changes what can be learned and what can be
// temporarily shown, but deliberately leaves the existing motion/physics intact.
let v24ResultFilter='all';

const V24_FAMILY_RE=/\b(father|mother|parent|child|son|daughter|sibling|brother|sister|spouse|husband|wife|aunt|uncle|niece|nephew|cousin|grandfather|grandmother|grandparent|ancestor|descendant|in-law|by marriage|married)\b/i;
const V24_SURNAME_RE=/\b(surname|family name|last name|patronym|matronym|name variant|variant spelling|related through surname)\b/i;
const V24_PLACE_RE=/\b(location|place|country|city|town|village|county|region|geograph|born|birthplace|died|death place|originated in|from)\b/i;
const V24_PERSON_SRC_RE=/\b(WikiTree|FamilySearch|Geneanet|Geni|OpenAlex|Crossref|Open Library)\b/i;
const V24_HUMAN_REL_RE=/\b(person|human|author|researcher|genealog|born|died|father|mother|parent|child|son|daughter|sibling|brother|sister|spouse|husband|wife|aunt|uncle|niece|nephew|cousin|ancestor|descendant|surname|family name)\b/i;

function v24RelationClass(rel='',src='',kind=''){
  let k=String(kind||'').toLowerCase(),r=String(rel||''),s=String(src||'');
  if(k==='family'||V24_FAMILY_RE.test(r))return'family';
  if(k==='surname'||V24_SURNAME_RE.test(r))return'surname';
  if(k==='place'||V24_PLACE_RE.test(r))return'places';
  if(k==='people'||(V24_PERSON_SRC_RE.test(s)&&V24_HUMAN_REL_RE.test(r)))return'people';
  return'other'
}
function v24RelationStrength(rel='',src='',kind=''){
  let cls=v24RelationClass(rel,src,kind),r=String(rel||'').toLowerCase();
  if(cls==='family'){
    if(/\b(father|mother|son|daughter)\b/.test(r))return 100;
    if(/\b(parent|child|sibling|brother|sister|spouse|husband|wife)\b/.test(r))return 94;
    if(/\b(grand|great-|ancestor|descendant|aunt|uncle|niece|nephew|cousin|in-law|by marriage)\b/.test(r))return 90;
    return 86
  }
  if(cls==='surname')return /related through surname/.test(r)?76:/has surname|family name/.test(r)?72:68;
  if(cls==='people')return 40;
  if(cls==='places')return 35;
  return 20
}
function v24FindEdge(a,b){
  return L.find(e=>{let x=e.source?.id||e.source,y=e.target?.id||e.target;return(x===a.id&&y===b.id)||(x===b.id&&y===a.id)})
}
function v24IsSeedRoot(n){return !!n&&seeds.some(s=>s.root===n.id)}
function v24LooksLikePersonLabel(label=''){
  let s=String(label||'').trim(),parts=s.split(/\s+/).filter(Boolean);
  if(parts.length<2||parts.length>7)return false;
  if(parts.some(x=>/\d|https?:|[@/]/i.test(x)))return false;
  return parts.every(x=>/^[A-Za-zÀ-ÖØ-öø-ÿ'’.-]+$/.test(x))
}
function v24SurnameKey(label=''){
  if(!v24LooksLikePersonLabel(label))return'';
  let parts=String(label).trim().split(/\s+/);return key(parts[parts.length-1])
}
function v24MarkHuman(n,surname=''){
  if(!n)return n;n.v24Human=true;
  let sk=key(surname||'');if(sk)n.v24Surname=sk;
  else if(!n.v24Surname&&v24LooksLikePersonLabel(n.l))n.v24Surname=v24SurnameKey(n.l);
  return n
}
function v24MarkSurnameHub(n){if(n)n.v24SurnameHub=true;return n}
function v24IsSurnameHub(n){return !!n&&(n.v24SurnameHub||L.some(e=>v24RelationClass(e.rel,e.src,e.kind)==='surname'&&((e.source?.id||e.source)===n.id||(e.target?.id||e.target)===n.id)&&!v24LooksLikePersonLabel(n.l)))}
function v24IsHumanNode(n){
  if(!n)return false;if(n.v24Human)return true;
  for(const e of L){let cls=v24RelationClass(e.rel,e.src,e.kind),a=e.source?.id||e.source,b=e.target?.id||e.target;if(a!==n.id&&b!==n.id)continue;
    if(cls==='family')return true;
    if(cls==='surname'&&!v24IsSurnameHub(n)&&v24LooksLikePersonLabel(n.l))return true
  }
  return false
}
function v24TrustedPerson(n,hub=null,cohort=[]){
  if(!n||!v24LooksLikePersonLabel(n.l))return false;
  if(n.v24Human)return true;
  if(hub&&(hub.v24SurnameHub||v24IsSeedRoot(hub)))return true;
  return v24IsSeedRoot(n)&&cohort.some(x=>x!==n&&v24IsSeedRoot(x)&&v24LooksLikePersonLabel(x.l))
}

const v24EdgeBase=edge;
edge=function(a,b,r,seedId='',src='',kind=''){
  if(!a||!b||a===b)return;
  let before=v24FindEdge(a,b),oldStrength=before?v24RelationStrength(before.rel,before.src,before.kind):-1;
  v24EdgeBase(a,b,r,seedId,src);
  let e=v24FindEdge(a,b);if(!e)return;
  let newKind=kind||v24RelationClass(r,src,''),newStrength=v24RelationStrength(r,src,newKind);
  if(newKind==='family'){v24MarkHuman(a);v24MarkHuman(b)}
  if(newKind==='surname'){
    let ap=v24LooksLikePersonLabel(a.l),bp=v24LooksLikePersonLabel(b.l);
    if(ap&&!bp){v24MarkHuman(a,b.k);v24MarkSurnameHub(b)}
    else if(bp&&!ap){v24MarkHuman(b,a.k);v24MarkSurnameHub(a)}
    else if(ap&&bp){v24MarkHuman(a);v24MarkHuman(b)}
  }
  if(!Array.isArray(e.altRelations))e.altRelations=[];
  let alt={rel:String(r||''),src:String(src||''),kind:newKind};
  if(alt.rel&&!e.altRelations.some(x=>x.rel===alt.rel&&x.src===alt.src))e.altRelations.push(alt);
  if(!before||newStrength>oldStrength){e.rel=r;e.src=src;e.seedId=seedId||e.seedId;e.kind=newKind}
  else if(kind&&!e.kind)e.kind=kind
};

function v24SeedsForNodes(nodes=[],fallback=null){
  let out=[],seen=new Set();
  if(fallback?.id){seen.add(fallback.id);out.push(fallback)}
  for(const n of nodes)for(const id of n?.owners||[]){if(seen.has(id))continue;let s=seedById(id);if(s){seen.add(id);out.push(s)}}
  return out
}
function v24EnsureSurnameHubForNode(n,seed=null){
  if(!n)return;
  let sk=n.v24Surname||v24SurnameKey(n.l);if(!sk||sk===n.k)return;
  let hub=byK(sk),rawCohort=N.filter(x=>x!==n&&(x.v24Surname||v24SurnameKey(x.l))===sk);
  if(!v24TrustedPerson(n,hub,rawCohort))return;
  v24MarkHuman(n,sk);
  let cohort=rawCohort.filter(x=>v24TrustedPerson(x,hub,rawCohort));

  // A surname hub is created only from actual human/surname context. Ordinary
  // two-word concepts no longer get mistaken for people merely because they have
  // a last token that looks like a surname.
  if(!hub&&cohort.length){
    let anchorNode=cohort[0]||n,seedsForHub=v24SeedsForNodes([n,...cohort],seed),primary=seedsForHub[0]||seed||null;
    hub=v24NodeBase(cap(sk),primary,anchorNode);v24MarkSurnameHub(hub);
    if(hub&&!hub.parentId&&typeof placeChild==='function')placeChild(hub,anchorNode);
    for(const s of seedsForHub)own(hub,s)
    try{if(typeof v24ProgressiveFalcon==='function')v24ProgressiveFalcon(hub.k)}catch{}
  }
  if(!hub||hub===n)return;
  v24MarkSurnameHub(hub);
  for(const s of v24SeedsForNodes([n],seed))own(hub,s);
  edge(n,hub,'related through surname',seed?.id||[...n.owners||[]][0]||'','exact surname match','surname');
  for(const person of cohort){v24MarkHuman(person,sk);edge(person,hub,'related through surname',[...person.owners||[]][0]||'','exact surname match','surname')}
}
function v24AttachExistingPeopleToSurname(hub,seed=null){
  if(!hub||String(hub.k||'').includes(' '))return;
  let candidates=N.filter(n=>n!==hub&&(n.v24Surname||v24SurnameKey(n.l))===hub.k);
  let trusted=candidates.filter(n=>n.v24Human||v24IsSeedRoot(n));
  if(!trusted.length&&!hub.v24SurnameHub)return;
  v24MarkSurnameHub(hub);
  for(const n of trusted){v24MarkHuman(n,hub.k);if(seed)own(n,seed);edge(n,hub,'related through surname',seed?.id||'','exact surname match','surname')}
}
const v24NodeBase=node;
node=function(term,seed=null,p=null){
  let n=v24NodeBase(term,seed,p);
  v24EnsureSurnameHubForNode(n,seed);
  if(n&&String(n.k||'').indexOf(' ')<0)v24AttachExistingPeopleToSurname(n,seed);
  return n
};

function v24EdgeMatches(e,filter=v24ResultFilter){
  if(filter==='all')return true;
  let cls=v24RelationClass(e?.rel,e?.src,e?.kind),a=nById(e.source?.id||e.source),b=nById(e.target?.id||e.target);
  if(filter==='surname')return cls==='surname';
  if(filter==='family')return cls==='family';
  if(filter==='people'){
    let ah=v24IsHumanNode(a),bh=v24IsHumanNode(b),ash=v24IsSurnameHub(a),bsh=v24IsSurnameHub(b);
    return (ah&&bh)||(cls==='family')||(cls==='surname'&&((ah&&bsh)||(bh&&ash)))
  }
  if(filter==='other')return !['family','surname','places','people'].includes(cls);
  return cls===filter
}

function v24VisibleIds(){
  if(v24ResultFilter==='all')return null;
  let ids=new Set();
  if(v24ResultFilter==='people'){
    for(const n of N)if(v24IsHumanNode(n))ids.add(n.id);
    for(const e of L)if(v24EdgeMatches(e,'people')){let a=e.source?.id||e.source,b=e.target?.id||e.target;ids.add(a);ids.add(b)}
    return ids
  }
  if(v24ResultFilter==='surname'||v24ResultFilter==='family'){
    for(const e of L)if(v24EdgeMatches(e)){let a=e.source?.id||e.source,b=e.target?.id||e.target;if(a)ids.add(a);if(b)ids.add(b)}
    return ids
  }
  for(const s of seeds)if(s.root)ids.add(s.root);
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
  N=allN.filter(n=>ids.has(n.id));L=allL.filter(e=>v24EdgeMatches(e)&&ids.has(e.source?.id||e.source)&&ids.has(e.target?.id||e.target));
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
  select.innerHTML='<option value="all">Filter: All</option><option value="family">Family only</option><option value="surname">Surname only</option><option value="people">Humans only</option><option value="places">Places</option><option value="other">Sources / other</option>';
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
  return out.slice(0,240)
};

const v24MergeProgressBase=v24MergeProgressCache;
v24MergeProgressCache=function(term,rows){
  let direct=(rows||[]).filter(x=>!x.from||key(x.from)===key(term));
  return v24MergeProgressBase(term,direct)
};

v24ScheduleProgress=function(parent,seed,rows){
  let watchKey=`${seed.id}|${parent.id}`,seen=v24ProgressWatches.get(watchKey);if(!seen)return;
  let fresh=[];
  for(const c of rows||[]){let rk=`${key(c.from||parent.k)}|${c.k}|${c.r}`;if(seen.has(rk))continue;seen.add(rk);fresh.push(c)}
  fresh.slice(0,240).forEach((c,i)=>setTimeout(()=>{
    let liveParent=nById(parent.id),liveSeed=seedById(seed.id);if(!liveParent||!liveSeed||!liveParent.owners?.has(liveSeed.id))return;
    let sourceNode=liveParent,sourceKey=key(c.from||liveParent.k),sourceWas=false;
    if(sourceKey&&sourceKey!==key(liveParent.k)){
      sourceNode=byK(sourceKey);sourceWas=!!sourceNode;
      if(!sourceNode){sourceNode=node(c.from,liveSeed,liveParent);placeChild(sourceNode,liveParent)}else own(sourceNode,liveSeed)
    }
    let q=byK(c.k),targetWas=!!q;
    if(!q){q=node(c.l,liveSeed,sourceNode);placeChild(q,sourceNode)}else own(q,liveSeed);
    if(sourceNode===q)return;

    if(c.kind==='family'){v24MarkHuman(sourceNode);v24MarkHuman(q)}
    else if(c.kind==='surname'){
      if(sourceKey&&!sourceKey.includes(' ')&&v24LooksLikePersonLabel(q.l)){v24MarkSurnameHub(sourceNode);v24MarkHuman(q,sourceKey)}
      else if(q.k&&!q.k.includes(' ')&&v24LooksLikePersonLabel(sourceNode.l)){v24MarkSurnameHub(q);v24MarkHuman(sourceNode,q.k)}
      else {if(v24LooksLikePersonLabel(sourceNode.l))v24MarkHuman(sourceNode);if(v24LooksLikePersonLabel(q.l))v24MarkHuman(q)}
    }else if(c.kind==='people'&&V24_HUMAN_REL_RE.test(c.r)){if(v24LooksLikePersonLabel(q.l))v24MarkHuman(q);if(V24_FAMILY_RE.test(c.r)&&v24LooksLikePersonLabel(sourceNode.l))v24MarkHuman(sourceNode)}

    v24EnsureSurnameHubForNode(sourceNode,liveSeed);v24EnsureSurnameHubForNode(q,liveSeed);
    let before=v24FindEdge(sourceNode,q),oldRel=before?.rel||'',oldKind=before?.kind||'';
    edge(sourceNode,q,c.r,liveSeed.id,c.src,c.kind);
    let after=v24FindEdge(sourceNode,q),upgraded=after&&(after.rel!==oldRel||after.kind!==oldKind);
    if(!sourceWas||!targetWas||!before||upgraded)render()
  },i*420))
};

if(typeof conceptualPathBetween==='function'){
  const v24ConceptualPathBase=conceptualPathBetween;
  conceptualPathBetween=async function(a,b,...args){
    let sa=(a?.v24Surname||v24SurnameKey(a?.l)),sb=(b?.v24Surname||v24SurnameKey(b?.l));
    let trustedA=v24IsHumanNode(a)||v24IsSeedRoot(a),trustedB=v24IsHumanNode(b)||v24IsSeedRoot(b);
    if(sa&&sa===sb&&a!==b&&trustedA&&trustedB){
      v24MarkHuman(a,sa);v24MarkHuman(b,sb);v24EnsureSurnameHubForNode(a,null);v24EnsureSurnameHubForNode(b,null);
      let ids=pathIds(a.id,b.id);
      if(ids){render();return{kind:'visible',ids}}
      return{kind:'surname-direct',surname:sa}
    }
    return v24ConceptualPathBase(a,b,...args)
  }
}
if(typeof describeSearchedPath==='function'){
  const v24DescribeSearchedBase=describeSearchedPath;
  describeSearchedPath=function(a,b,res){
    if(res?.kind==='surname-direct'){
      let surname=cap(res.surname||a?.v24Surname||v24SurnameKey(a?.l)||'');
      return{html:`<div class="box"><strong>${a.l} ↔ ${b.l}</strong><ul><li><b>${a.l}</b> — related through surname → <b>${surname}</b></li><li><b>${b.l}</b> — related through surname → <b>${surname}</b></li></ul><p>Why they connect: they share the exact surname <b>${surname}</b>, which Things Universe treats as relatedness.</p></div>`,intermediates:[surname]}
    }
    return v24DescribeSearchedBase(a,b,res)
  }
}
if(typeof relationKind==='function'){
  const v24RelationKindBase=relationKind;
  relationKind=function(rel){let c=v24RelationClass(rel,'','');if(c==='family'||c==='surname')return c;return v24RelationKindBase(rel)}
}
if(typeof whySentence==='function'){
  const v24WhyBase=whySentence;
  whySentence=function(steps){
    let kinds=[...new Set((steps||[]).map(s=>relationKind(s.rel||s.r)))];
    if(kinds.includes('family'))return'Why they connect: this chain includes a more specific family relationship. Shared-surname relatedness remains underneath it.';
    if(kinds.includes('surname'))return'Why they connect: they share the same surname, which Things Universe treats as relatedness. More specific family connections can replace this general link when they are found.';
    return v24WhyBase(steps)
  }
}

v24InstallFilter();