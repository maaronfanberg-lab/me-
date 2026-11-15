'use strict';

// v22: common-meaning first. Explicit conceptual sources only.
// Wikipedia is used only for cleaned conceptual fields; category members are never injected as nodes.
// v24 Falcon extension: sparse/ambiguous concepts can be enriched through the Community's
// Falcon3 10B engine, which synthesizes evidence from multiple independent public sources.

const ENTITY_DESC=/\b(song|single|album|ep\b|film|movie|television|tv series|episode|novel|book|comic|video game|game|band|musician|singer|actor|actress|artist|record label|company|organization|person|surname|given name|village|town|city|county|district|station|airport|ship|album by|song by|film by)\b/i;
const ENTITY_CAT=/\b(songs?|singles?|albums?|eps?|films?|movies?|television|episodes?|novels?|books?|comics?|video games?|musicians?|singers?|actors?|actresses?|artists?|record labels?|people|births|deaths|companies|organizations|cities|towns|villages|ships?)\b/i;
const FIELD_DROP=/\b(works by|discographies|filmographies|albums by|songs by|singles by|films by|people from|members of|establishments|introductions|events|awards|lists|articles|pages|wikipedia|templates|redirects|maintenance|tracking|stubs?)\b/i;
const EXPLICIT_ENTITY=/\b(song|single|album|film|movie|novel|book|episode|band|artist|actor|actress|company|city|country|\d{4})\b/i;
const COMMON_ABSTRACT=/\b(idea|ideas|thought|belief|emotion|feeling|love|fear|anger|joy|happy|happiness|sad|sadness|peace|truth|beauty|good|bad|ethics|morality|meaning|knowledge|reason|reasoning|judgment|decision|choice|risk|mistake|problem|solution|creativity|curiosity|trust|hope|justice|freedom|power|culture|society|language|science|mathematics|math|number|numbers|sound|music|fungus|fungi|universe|nature|life|death)\b/i;
const MEDIA_LABEL=/\b(album[- ]?equivalent|album|single release|music track|audio track|recording industry|greatest hits|extended play|record label|soundtrack|discography|musical work\/composition)\b/i;
const THINGS_RELAY='https://room-live-mirror.dfp6k69dw5.workers.dev';

const LOCAL_COMMON=new Map([
  ['idea',[
    ['thought','is a kind of'],['concept','can be expressed as'],['reasoning','can arise from'],['creativity','can generate'],['problem solving','can use'],['decision making','can influence'],['communication','can convey'],['belief','can become']
  ]],
  ['bad idea',[
    ['idea','is a kind of'],['judgment','can reflect poor'],['decision making','can result from'],['mistake','can lead to'],['risk','can create'],['consequence','can have'],['reasoning','can be evaluated by'],['critical thinking','can be challenged by'],['problem solving','can be improved through']
  ]],
  ['good idea',[
    ['idea','is a kind of'],['judgment','can reflect sound'],['decision making','can support'],['reasoning','can be supported by'],['critical thinking','can be evaluated by'],['problem solving','can improve'],['creativity','can arise from']
  ]],
  ['judgment',[
    ['decision making','guides'],['reasoning','depends on'],['evidence','can use'],['bias','can be distorted by'],['consequence','can be evaluated by'],['critical thinking','can improve']
  ]],
  ['decision making',[
    ['choice','produces'],['judgment','uses'],['reasoning','uses'],['risk','considers'],['consequence','considers'],['goal','can serve'],['uncertainty','can occur under']
  ]],
  ['reasoning',[
    ['logic','can use'],['evidence','can use'],['inference','produces'],['judgment','supports'],['critical thinking','is part of'],['problem solving','supports']
  ]],
  ['critical thinking',[
    ['reasoning','uses'],['evidence','evaluates'],['bias','can detect'],['judgment','can improve'],['problem solving','supports'],['decision making','can improve']
  ]],
  ['mistake',[
    ['error','is a kind of'],['decision making','can result from'],['learning','can lead to'],['consequence','can have'],['feedback','can reveal']
  ]],
  ['problem solving',[
    ['problem','starts with'],['goal','aims at'],['strategy','uses'],['reasoning','uses'],['creativity','can use'],['solution','produces'],['decision making','requires']
  ]]
]);

function isExplicitEntity(term){return EXPLICIT_ENTITY.test(raw(term))}
function prefersCommonMeaning(term){let s=raw(term);return COMMON_ABSTRACT.test(s)||LOCAL_COMMON.has(key(s))||G.has(key(s))}
function localCommon(term){
  let k=key(term),rows=LOCAL_COMMON.get(k)||[];
  return rows.map(([l,r],i)=>({k:key(l),l:cap(l),r,score:620-i,src:'common concept atlas'}));
}
function candidateAllowed(label,term,src=''){
  if(!label)return false;
  let l=String(label);
  if(BADTITLE.test(l)||l.length>70)return false;
  if(!isExplicitEntity(term)&&MEDIA_LABEL.test(l))return false;
  return true
}
async function json(url,ms=4500){let c=new AbortController(),t=setTimeout(()=>c.abort(),ms);try{let r=await fetch(url,{signal:c.signal});return r.ok?await r.json():null}catch{return null}finally{clearTimeout(t)}}
async function postjson(url,body,ms=5000){let c=new AbortController(),t=setTimeout(()=>c.abort(),ms);try{let r=await fetch(url,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body),signal:c.signal});return r.ok?await r.json():null}catch{return null}finally{clearTimeout(t)}}
const nap=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function add(m,c){if(!c?.k||!c?.l||!c?.r||!candidateAllowed(c.l,c.from||'',c.src))return;let o=m.get(c.k);if(!o||c.score>o.score)m.set(c.k,c)}

async function cn(term){
  let k=key(term),j=await json(`${CN}/query?node=${encodeURIComponent('/c/en/'+k.replace(/ /g,'_'))}&limit=220`),out=[];
  for(const e of j?.edges||[]){
    let rn=String(e.rel?.['@id']||'').split('/').pop(),rp=REL[rn];if(!rp)continue;
    let sk=key(e.start?.label),ek=key(e.end?.label),f=sk===k;if(!f&&ek!==k)continue;
    let o=f?e.end:e.start;if(!o?.['@id']?.startsWith('/c/en/')||!o.label)continue;
    let q=key(o.label);if(!q||q===k||!candidateAllowed(o.label,term,'ConceptNet'))continue;
    out.push({k:q,l:cap(o.label),r:f?rp[0]:rp[1],score:205,src:'ConceptNet',from:term})
  }
  return out
}

async function wd(term){
  let k=key(term),s=await json(`${WD}?origin=*&action=wbsearchentities&format=json&language=en&type=item&limit=8&search=${encodeURIComponent(term)}`),hits=s?.search||[];
  if(!hits.length)return[];
  let explicit=isExplicitEntity(term),common=prefersCommonMeaning(term);
  let viable=hits.filter(h=>{
    let exact=key(h.label)===k,desc=String(h.description||'');
    if(!candidateAllowed(h.label,term,'Wikidata'))return false;
    if(!explicit&&common&&ENTITY_DESC.test(desc))return false;
    return exact||!ENTITY_DESC.test(desc)||explicit
  });
  let hit=viable.find(h=>key(h.label)===k)||viable[0];if(!hit)return[];
  let id=hit.id,e=await json(`${WD}?origin=*&action=wbgetentities&format=json&languages=en&props=claims&ids=${id}`),claims=e?.entities?.[id]?.claims||{},refs=[];
  for(const[p,r]of Object.entries(WDREL))for(const c of(claims[p]||[]).slice(0,14)){let qid=c.mainsnak?.datavalue?.value?.id;if(qid)refs.push({qid,r})}
  let ids=[...new Set(refs.map(x=>x.qid))].slice(0,48);if(!ids.length)return[];
  let l=await json(`${WD}?origin=*&action=wbgetentities&format=json&languages=en&props=labels|descriptions&ids=${ids.join('|')}`),out=[];
  for(const x of refs){
    let ent=l?.entities?.[x.qid],lab=ent?.labels?.en?.value,desc=ent?.descriptions?.en?.value||'',q=key(lab);
    if(!lab||!q||q===k||!candidateAllowed(lab,term,'Wikidata'))continue;
    if(!explicit&&common&&ENTITY_DESC.test(desc))continue;
    out.push({k:q,l:lab,r:x.r,score:255,src:'Wikidata',from:term})
  }
  return out
}

function cleanCategory(name){
  let c=String(name||'').replace(/^Category:/,'').trim();
  c=c.replace(/\s+by (country|year|century|nationality|language)$/i,'').trim();
  return c
}
async function wiki(term){
  // v22 intentionally DOES NOT call categorymembers. We only expose conceptual fields of the page itself.
  let j=await json(`${WIKI}?origin=*&action=query&format=json&redirects=1&prop=categories|pageprops&cllimit=80&titles=${encodeURIComponent(term)}`),page=Object.values(j?.query?.pages||{})[0];
  if(!page||page.missing!==undefined||page.pageprops?.disambiguation!==undefined)return[];
  let cats=(page.categories||[]).map(x=>cleanCategory(x.title)).filter(Boolean);
  let explicit=isExplicitEntity(term),common=prefersCommonMeaning(term);
  if(!explicit&&common&&cats.some(c=>ENTITY_CAT.test(c)))return[];
  let out=[],seen=new Set();
  for(const cat of cats){
    if(BADCAT.test(cat)||FIELD_DROP.test(cat)||ENTITY_CAT.test(cat)||cat.length>65)continue;
    let q=key(cat);if(!q||q===key(term)||seen.has(q))continue;seen.add(q);
    out.push({k:q,l:cap(cat),r:'belongs to conceptual field',score:92,src:'Wikipedia conceptual field',from:term});
    if(out.length>=10)break
  }
  return out
}

function falconRows(data,term){
  let out=[];
  for(const row of data?.relations||[]){
    let lab=String(row?.label||'').trim(),rel=String(row?.relation||'').trim(),sources=Array.isArray(row?.sources)?row.sources.map(String).filter(Boolean).slice(0,4):[];
    let confidence=Number(row?.confidence);if(!Number.isFinite(confidence))confidence=.5;
    if(confidence<.5||!lab||!rel||!sources.length||!candidateAllowed(lab,term,'Falcon synthesis'))continue;
    let q=key(lab);if(!q||q===key(term))continue;
    out.push({k:q,l:cap(lab),r:rel,score:170+Math.round(Math.max(0,Math.min(1,confidence))*140),src:`Falcon synthesis · ${sources.join(' + ')}`,from:term});
  }
  return out.slice(0,14)
}

async function falcon(term){
  let context=[];
  try{if(typeof N!=='undefined'&&Array.isArray(N))context=N.slice(-12).map(n=>n?.l).filter(Boolean).slice(0,12)}catch{}
  let start=await postjson(`${THINGS_RELAY}/api/things/enrich`,{term:String(term).slice(0,80),context},5000);
  if(start?.result)return falconRows(start.result,term);
  let id=start?.id;if(!id)return[];
  for(let i=0;i<26;i++){
    await nap(i?1100:350);
    let result=await json(`${THINGS_RELAY}/api/things/result?id=${encodeURIComponent(id)}`,3500);
    if(result?.status==='done')return falconRows(result.result,term);
    if(result?.status==='error'||result?.status==='missing')return[];
  }
  return[]
}

async function concepts(term){
  let k=key(term);if(cache.has(k))return cache.get(k);
  let m=new Map();
  for(const x of localCommon(k))add(m,x);
  for(const x of G.get(k)||[])add(m,{...x,from:term});

  // Typed ConceptNet relationships are the main broad source.
  let c=await cn(k);for(const x of c)add(m,x);

  // Wikidata is accepted only when its entity sense is compatible with the common meaning.
  if(m.size<28){let w=await wd(k);for(const x of w)add(m,x)}

  // Wikipedia contributes only cleaned conceptual-field category names, never sibling pages/items.
  if(m.size<34){let w=await wiki(k);for(const x of w)add(m,x)}

  // Sparse concepts get the expensive pass. Falcon does not replace the explicit sources above;
  // it reconciles WikiTree, Wiktionary, Wikidata, ConceptNet, Wikipedia, DBpedia, OpenAlex,
  // Crossref, Open Library, and FamilySearch when an authenticated FamilySearch token is available.
  if(m.size<34){let f=await falcon(term);for(const x of f)add(m,x)}

  let out=[...m.values()].filter(x=>x.k!==k).sort((a,b)=>b.score-a.score);
  cache.set(k,out);return out
}
