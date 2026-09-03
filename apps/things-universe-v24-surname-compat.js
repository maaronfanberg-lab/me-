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

function v24SharedSurnameCompat(a,b){
  if(!a||!b||a===b)return'';
  let sa=v24SurnameKey(a.l),sb=v24SurnameKey(b.l);
  if(sa&&sb&&sa===sb)return sa;

  // Also recognize surname-hub ↔ person directly, e.g. Fanberg ↔ Oscar Fanberg.
  let ak=key(a.l),bk=key(b.l),aSingle=!String(v24NameCore(a.l)).includes(' '),bSingle=!String(v24NameCore(b.l)).includes(' ');
  if(sa&&bSingle&&bk===sa)return sa;
  if(sb&&aSingle&&ak===sb)return sb;
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
