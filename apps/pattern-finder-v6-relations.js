function namedPattern(text){
  let t=text.trim().toLowerCase();
  if(/^prime numbers?$/.test(t)){let a=[];for(let n=2;a.length<80;n++){let ok=true;for(let d=2;d*d<=n;d++)if(n%d===0){ok=false;break}if(ok)a.push(n)}return analyzeNumbers(a,'Prime numbers')}
  if(/fibonacci/.test(t)){let a=[1,1];while(a.length<80)a.push(a.at(-1)+a.at(-2));return analyzeNumbers(a,'Fibonacci sequence')}
  if(/powers? of two|power of 2/.test(t))return analyzeNumbers(Array.from({length:50},(_,i)=>2**(i/5)),'Powers of two');
  if(/golden angle|golden spiral/.test(t)){let phi=(1+Math.sqrt(5))/2;return analyzeNumbers(Array.from({length:120},(_,i)=>(i*360/(phi*phi))%360),'Golden-angle phase')}
  if(/sine wave|sinusoid/.test(t))return analyzeNumbers(Array.from({length:160},(_,i)=>Math.sin(i*.23)),'Sine wave');
  if(/logistic|chaos/.test(t)){let x=.231,a=[];for(let i=0;i<180;i++){x=3.91*x*(1-x);a.push(x)}return analyzeNumbers(a,'Logistic chaos')}
  if(/random walk/.test(t)){let x=0,a=[],z=123456789;for(let i=0;i<180;i++){z=(1664525*z+1013904223)>>>0;x+=(z&1)?1:-1;a.push(x)}return analyzeNumbers(a,'Random walk')}
  return null
}
function detect(text){
  let t=text.trim(),np=namedPattern(t);if(np)return{kind:'ready',pattern:np};
  let langKey=t.toLowerCase().replace(/^language\s*:\s*/,'').replace(/\s+language$/,'').trim(),lang=LANGS[langKey];
  if(lang)return{kind:'language',name:langKey[0].toUpperCase()+langKey.slice(1),code:lang};
  let nums=t.split(/[\s,;]+/).filter(Boolean).map(Number);if(nums.length>=4&&nums.filter(Number.isFinite).length/nums.length>.85)return{kind:'ready',pattern:analyzeNumbers(nums.filter(Number.isFinite),t.slice(0,42))};
  if(/[=^]|(?:^|[^a-z])(sin|cos|tan|exp|log|sqrt)(?:[^a-z]|$)|[π∞]/i.test(t))return{kind:'ready',pattern:analyzeEquation(t,t.slice(0,46))};
  return{kind:'text',text:t,label:t.length>44?t.slice(0,41)+'…':t};
}
async function languagePattern(name,code){
  let api=`https://${code}.wikipedia.org/w/api.php?origin=*&action=query&format=json&generator=random&grnnamespace=0&grnlimit=4&prop=extracts&explaintext=1&exintro=1&exsentences=7`;
  let c=new AbortController(),timer=setTimeout(()=>c.abort(),9000);
  try{
    let r=await fetch(api,{signal:c.signal});if(!r.ok)throw Error('source '+r.status);
    let j=await r.json(),pages=Object.values(j.query?.pages||{}),text=pages.map(p=>p.extract||'').join(' ');
    if(text.length<120)throw Error('sample too short');
    let p=analyzeText(text,name,'language');p.description=`Random ${name} encyclopedia text. `+p.description;return p
  }finally{clearTimeout(timer)}
}
async function topicPattern(text,label){
  let api='https://en.wikipedia.org/w/api.php?origin=*&action=query&format=json&generator=search&gsrsearch='+encodeURIComponent(text)+'&gsrlimit=1&prop=extracts&explaintext=1&exintro=1&exsentences=8';
  let c=new AbortController(),timer=setTimeout(()=>c.abort(),7000);
  try{
    let r=await fetch(api,{signal:c.signal});if(!r.ok)throw Error('source');
    let j=await r.json(),p=Object.values(j.query?.pages||{})[0],body=p?.extract||'';
    if(body.length<90)throw Error('short');
    let out=analyzeText(body,label,'topic text');out.description=`Public encyclopedia description of “${label}”. `+out.description;return out
  }catch(e){
    let out=analyzeText(text,label,'typed text');out.description='Only the text you typed was analyzed; no outside dataset was found.';return out
  }finally{clearTimeout(timer)}
}
function featureSimilarity(a,b){
  let d=Math.sqrt(FEATURE_KEYS.reduce((s,k)=>s+((a.features[k]||0)-(b.features[k]||0))**2,0)/FEATURE_KEYS.length);
  return clamp(1-d)
}
function transformed(seq){
  let z=normalize(resample(seq,64)),sp=normalize(resample(spectrum(z),64));
  return{
    direct:z,
    reverse:[...z].reverse(),
    inverse:z.map(x=>-x),
    reverseInverse:[...z].reverse().map(x=>-x),
    spectral:sp,
    difference:normalize(resample(z.slice(1).map((x,i)=>x-z[i]),64))
  }
}
function relation(a,b){
  let A=normalize(resample(a.sequence,64)),B=transformed(b.sequence);
  let As=normalize(resample(spectrum(A),64));
  let cands=[
    ['direct',corr(A,B.direct)],
    ['reverse',corr(A,B.reverse)],
    ['inverse',corr(A,B.inverse)],
    ['reverseInverse',corr(A,B.reverseInverse)],
    ['spectral',corr(As,B.spectral)],
    ['difference',corr(normalize(resample(A.slice(1).map((x,i)=>x-A[i]),64)),B.difference)]
  ].sort((x,y)=>y[1]-x[1]);
  let [kind,shapeRaw]=cands[0],shape=clamp((shapeRaw+1)/2),fSim=featureSimilarity(a,b);
  let cross=a.domain!==b.domain?.045:0;
  let score=clamp(shape*.55+fSim*.45+cross);
  let closest=FEATURE_KEYS.map(k=>({k,d:Math.abs((a.features[k]||0)-(b.features[k]||0)),av:a.features[k]||0,bv:b.features[k]||0})).sort((x,y)=>x.d-y.d).slice(0,3);
  let labels={direct:'direct pattern',reverse:'reversed pattern',inverse:'inverse pattern',reverseInverse:'reversed + inverse',spectral:'rhythmic / spectral',difference:'change-pattern'};
  let why={
    direct:'Their rises, falls and repeated local shapes line up without a major transformation.',
    reverse:'They become more alike when one pattern is read backward.',
    inverse:'Peaks in one line up with troughs in the other after inversion.',
    reverseInverse:'The strongest alignment appears after both reversing and inverting one pattern.',
    spectral:'The raw sequences differ, but their repeating frequencies have a similar shape.',
    difference:'Their levels differ, but the pattern of change from one step to the next is similar.'
  };
  return{score,kind,label:labels[kind],why:why[kind],shared:closest.map(x=>x.k).join(', '),shape,fSim}
}
