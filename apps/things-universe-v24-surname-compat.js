'use strict';

// Small compatibility layer for names returned with dates/annotations. Keep the
// main v24 family engine untouched; this only makes surname recognition tolerant.
const v24SurnameKeyBeforeCompat=v24SurnameKey;

function v24NameCore(label=''){
  let s=String(label||'').trim();
  // Genealogy/record sources often append lifespan or record notes after a name.
  // Remove trailing annotations without changing the visible node label.
  s=s.replace(/\s*[\[(][^\])]*[\])]\s*$/g,'').trim();
  s=s.replace(/\s+[–—-]\s*\d{3,4}\s*$/g,'').trim();
  let parts=s.split(/\s+/).filter(Boolean);
  while(parts.length>1&&/^(jr\.?|sr\.?|ii|iii|iv|v)$/i.test(parts[parts.length-1]))parts.pop();
  return parts.join(' ')
}

v24SurnameKey=function(label=''){
  let s=v24NameCore(label),parts=s.split(/\s+/).filter(Boolean);
  if(parts.length<2||parts.length>8)return'';
  // Permit middle initials and punctuation, but not embedded numbers/URLs.
  if(parts.some(x=>/\d|https?:|[@/]/i.test(x)))return'';
  if(!parts.every(x=>/^[A-Za-zÀ-ÖØ-öø-ÿ'’.-]+$/.test(x)))return'';
  return key(parts[parts.length-1])
};

// A syntactically name-like phrase is not enough to establish personhood. Learned
// surname evidence promotes a key here. Two explicitly added full-name roots may
// also establish their shared surname immediately, preserving the intended manual
// Daniel Fanberg + Matthew Fanberg behavior without turning Akita Range into a person.
const v24KnownSurnameKeys=new Set();

function v24ExplicitRootNode(n){
  return !!n&&seeds.some(s=>s?.root===n.id)
}
function v24SurnameEvidenceOnGraph(sk){
  if(!sk)return false;
  if(v24KnownSurnameKeys.has(sk))return true;
  return L.some(e=>{
    let rel=String(e?.rel||''),src=String(e?.src||''),kind=String(e?.kind||'').toLowerCase();
    if(kind!=='surname'&&!V24_SURNAME_RE.test(rel))return false;
    if(/exact surname match/i.test(src))return false;
    let a=e.source?.l||nById(e.source?.id||e.source)?.l||'',b=e.target?.l||nById(e.target?.id||e.target)?.l||'';
    return key(a)===sk||key(b)===sk||v24SurnameKey(a)===sk||v24SurnameKey(b)===sk
  })
}
function v24ExplicitRootSurnamePair(n,sk){
  if(!v24ExplicitRootNode(n)||!sk)return false;
  return N.some(x=>x!==n&&v24ExplicitRootNode(x)&&v24SurnameKey(x.l)===sk)
}

const v24ProgressRowsBeforeSurnameEvidence=v24ProgressRows;
v24ProgressRows=function(data,term){
  for(const row of data?.relations||[]){
    let rel=String(row?.relation||''),kind=String(row?.kind||'').toLowerCase();
    if(kind==='surname'||V24_SURNAME_RE.test(rel)){
      let tk=key(term);
      if(tk&&!tk.includes(' '))v24KnownSurnameKeys.add(tk)
    }
  }
  return v24ProgressRowsBeforeSurnameEvidence(data,term)
};

const v24EnsureSurnameHubBeforeCompat=v24EnsureSurnameHubForNode;
v24EnsureSurnameHubForNode=function(n,seed=null){
  let sk=v24SurnameKey(n?.l);
  if(!sk)return;
  if(!v24SurnameEvidenceOnGraph(sk)&&!v24ExplicitRootSurnamePair(n,sk))return;
  return v24EnsureSurnameHubBeforeCompat(n,seed)
};

const v24AttachExistingPeopleBeforeCompat=v24AttachExistingPeopleToSurname;
v24AttachExistingPeopleToSurname=function(hub,seed=null){
  let sk=key(hub?.l||hub?.k||'');
  if(!sk||sk.includes(' '))return;
  let explicitRoots=N.filter(n=>v24ExplicitRootNode(n)&&v24SurnameKey(n.l)===sk);
  if(!v24SurnameEvidenceOnGraph(sk)&&explicitRoots.length<2)return;
  return v24AttachExistingPeopleBeforeCompat(hub,seed)
};

function v24SharedSurnameCompat(a,b){
  if(!a||!b||a===b)return'';
  let sa=v24SurnameKey(a.l),sb=v24SurnameKey(b.l);
  if(sa&&sb&&sa===sb){
    if(v24SurnameEvidenceOnGraph(sa)||(v24ExplicitRootNode(a)&&v24ExplicitRootNode(b)))return sa;
    return''
  }

  // Also recognize surname-hub ↔ person directly, e.g. Fanberg ↔ Oscar Fanberg,
  // but only after the graph actually knows the one-word node is a surname.
  let ak=key(a.l),bk=key(b.l),aSingle=!String(v24NameCore(a.l)).includes(' '),bSingle=!String(v24NameCore(b.l)).includes(' ');
  if(sa&&bSingle&&bk===sa&&v24SurnameEvidenceOnGraph(sa))return sa;
  if(sb&&aSingle&&ak===sb&&v24SurnameEvidenceOnGraph(sb))return sb;
  return''
}

const v24ConceptualPathBeforeSurnameCompat=conceptualPathBetween;
conceptualPathBetween=async function(a,b,...args){
  let surname=v24SharedSurnameCompat(a,b);
  if(surname){
    // Re-run the normal hub attachment with the tolerant surname parser.
    try{v24EnsureSurnameHubForNode(a,null)}catch{}
    try{v24EnsureSurnameHubForNode(b,null)}catch{}
    let ids=pathIds(a.id,b.id);
    if(ids){render();return{kind:'visible',ids}}
    // The examiner must still recognize the relationship even if an edge has not
    // materialized yet. Specific kinship can refine this later.
    return{kind:'surname-direct',surname}
  }
  return v24ConceptualPathBeforeSurnameCompat(a,b,...args)
};

const V24_UNAMBIGUOUS_KIN_RE=/\b(father|mother|son|daughter|sibling|brother|sister|spouse|husband|wife|aunt|uncle|niece|nephew|cousin|grandfather|grandmother|grandparent|in-law|by marriage|married)\b/i;
const V24_STRUCTURED_FAMILY_SRC_RE=/\b(family evidence|WikiTree|FamilySearch|Geneanet|kinship)\b/i;
const V24_AMBIGUOUS_HIERARCHY_RE=/\b(parent|child|ancestor|descendant|member)\b/i;

// In Things Universe, exact surname sharing is baseline family relatedness.
// Family still accepts generic parent/ancestor wording when it came from a
// structured family source, but not when the same words describe geography/taxonomy.
const v24EdgeMatchesBeforeSurnameCompat=v24EdgeMatches;
v24EdgeMatches=function(e,filter=v24ResultFilter){
  if(filter==='family'){
    let rel=String(e?.rel||''),src=String(e?.src||''),cls=v24RelationClass(rel,src,e?.kind);
    if(cls==='surname')return true;
    if(V24_PLACE_RE.test(rel))return false;
    if(V24_UNAMBIGUOUS_KIN_RE.test(rel))return true;
    if(V24_AMBIGUOUS_HIERARCHY_RE.test(rel))return V24_STRUCTURED_FAMILY_SRC_RE.test(src);
  }
  return v24EdgeMatchesBeforeSurnameCompat(e,filter)
};

// A source being about research, books, or records does not make every entity in
// that source a human. Ambiguous hierarchy words are deliberately excluded here.
const V24_PERSON_REL_EVIDENCE_RE=/\b(person|human|author|researcher|scholar|scientist|writer|poet|artist|actor|actress|director|composer|musician|politician|engineer|physician|doctor|professor|teacher|employee|founder|student|alumn(?:us|a|i)?|occupation|works at|affiliated with|married|husband|wife|spouse|father|mother|son|daughter|sibling|brother|sister|aunt|uncle|niece|nephew|cousin|grandparent|surname|family name)\b/i;
const v24EdgeMatchesBeforePeopleCompat=v24EdgeMatches;
v24EdgeMatches=function(e,filter=v24ResultFilter){
  if(filter==='people'){
    let rel=String(e?.rel||''),src=String(e?.src||''),cls=v24RelationClass(rel,src,e?.kind);
    if(V24_PLACE_RE.test(rel))return false;
    if(cls==='surname'){
      let a=e.source?.l||nById(e.source?.id||e.source)?.l||'',b=e.target?.l||nById(e.target?.id||e.target)?.l||'';
      let sk=v24SurnameKey(a)||v24SurnameKey(b)||key(a)||key(b);
      return v24SurnameEvidenceOnGraph(sk)||(!/exact surname match/i.test(src)&&V24_SURNAME_RE.test(rel))
    }
    if(V24_UNAMBIGUOUS_KIN_RE.test(rel))return true;
    if(V24_AMBIGUOUS_HIERARCHY_RE.test(rel))return V24_STRUCTURED_FAMILY_SRC_RE.test(src);
    return V24_PERSON_REL_EVIDENCE_RE.test(rel)
  }
  return v24EdgeMatchesBeforePeopleCompat(e,filter)
};
