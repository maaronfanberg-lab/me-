function refs(){
  return[
    namedPattern('prime numbers'),namedPattern('fibonacci'),namedPattern('golden angle'),
    namedPattern('sine wave'),namedPattern('logistic chaos'),namedPattern('random walk')
  ].filter(Boolean).map(x=>{x.isReference=true;return x})
}
function pairKey(a,b,kind){return[a.id,b.id].sort().join('|')+'|'+kind}
function consider(a,b,rel){
  if(!a||!b||a.id===b.id)return;
  let key=pairKey(a,b,rel.kind),old=relationships.find(x=>x.key===key);
  let item={key,a,b,...rel,weird:rel.score+(a.domain!==b.domain?.06:0)+(((a.chain?.length||0)||(b.chain?.length||0))?.025:0)};
  if(old)Object.assign(old,item);else relationships.push(item)
}
function compareNew(p){
  let pool=patterns.filter(x=>x.id!==p.id);
  if(pool.length>420){
    let sameRoot=pool.filter(x=>x.root===p.root).slice(-60),cross=pool.filter(x=>x.root!==p.root).slice(-300);
    pool=[...cross,...sameRoot]
  }
  for(const other of pool){
    if(p.root===other.root&&((p.chain?.length||0)+(other.chain?.length||0)<2))continue;
    let r=relation(p,other);
    if(r.score>=.61)consider(p,other,r)
  }
}
function displayTitle(p){return p.root||p.title}
function chainText(p){return p.chain?.length?p.chain.join(' → '):''}
function render(){
  let userRoots=new Set(originals.map(x=>x.root));
  let ranked=relationships.filter(r=>!userRoots.size||userRoots.has(r.a.root)||userRoots.has(r.b.root))
    .sort((x,y)=>(y.weird+(userRoots.has(y.a.root)&&userRoots.has(y.b.root)?.035:0))-(x.weird+(userRoots.has(x.a.root)&&userRoots.has(x.b.root)?.035:0)));
  let seen=new Set(),top=[];
  for(const r of ranked){
    let roots=[displayTitle(r.a),displayTitle(r.b)].sort().join('|');
    if(seen.has(roots))continue;
    seen.add(roots);top.push(r);if(top.length>=7)break
  }
  $('#results').innerHTML=top.map(r=>{
    let ac=chainText(r.a),bc=chainText(r.b),transformNote=[ac?`${esc(displayTitle(r.a))}: ${esc(ac)}`:'',bc?`${esc(displayTitle(r.b))}: ${esc(bc)}`:''].filter(Boolean).join(' · ');
    return`<article class="card">
      <div class="cardTop"><div class="pair">${esc(displayTitle(r.a))} ↔ ${esc(displayTitle(r.b))}</div><div class="score">${Math.round(r.score*100)}%</div></div>
      <div class="kind">${esc(r.label)}</div>
      <p class="why">${esc(r.why)}</p>
      <div class="shared">Closest shared traits: ${esc(r.shared)}${transformNote?`<br>Found after: ${transformNote}`:''}</div>
      <div class="caveat">Exploratory structural similarity only — not evidence that the subjects cause or explain one another.</div>
    </article>`
  }).join('');
  $('#empty').style.display=!top.length&&!busy?'block':'none';
}
const TRANSFORMS=[
  {name:'reverse',fn:a=>[...a].reverse()},
  {name:'inverse',fn:a=>normalize(a).map(x=>-x)},
  {name:'complement',fn:a=>minmax(a).map(x=>1-x)},
  {name:'difference',fn:a=>a.slice(1).map((x,i)=>x-a[i])},
  {name:'cumulative',fn:a=>{let s=0;return a.map(x=>(s+=x))}},
  {name:'rank',fn:a=>{let s=[...a].sort((x,y)=>x-y);return a.map(x=>s.indexOf(x)/Math.max(1,a.length-1))}},
  {name:'absolute',fn:a=>normalize(a).map(Math.abs)},
  {name:'spectrum',fn:a=>spectrum(a,Math.max(10,Math.min(40,a.length)))},
  {name:'smooth',fn:a=>a.map((_,i)=>mean(a.slice(Math.max(0,i-3),i+1)))},
  {name:'shift',fn:a=>a.length?a.map((_,i)=>a[(i+Math.max(1,(wanderStep%17)))%a.length]):a}
];
function derive(parent){
  if(!parent?.sequence?.length)return null;
  let t=TRANSFORMS[(hash(parent.id+':'+wanderStep)+wanderStep)%TRANSFORMS.length],seq=t.fn(parent.sequence);
  if(seq.length<3)return null;
  let p=makePattern(parent.title,parent.domain,seq,features(seq),`Derived by ${t.name}.`,parent.root,[...(parent.chain||[]),t.name]);
  p.isDerived=true;patterns.push(p);compareNew(p);return p
}
function startWander(){
  clearInterval(wanderTimer);
  wanderTimer=setInterval(()=>{
    if(!patterns.length||busy)return;
    wanderStep++;
    let candidates=patterns.filter(x=>x.sequence?.length>2);
    let p=candidates[(hash(String(wanderStep)) + wanderStep*17)%candidates.length];
    derive(p);
    $('#statusText').textContent=`Still looking… ${patterns.length} pattern versions tried`;
    render()
  },2800)
}
function splitInputs(text){
  let lines=text.split(/\n+/).map(x=>x.trim()).filter(Boolean);
  if(lines.length===1&&/\s+vs\.?\s+/i.test(lines[0]))lines=lines[0].split(/\s+vs\.?\s+/i).map(x=>x.trim()).filter(Boolean);
  return lines.slice(0,12)
}
async function buildOriginal(line){
  let d=detect(line);
  if(d.kind==='ready')return d.pattern;
  if(d.kind==='language')return await languagePattern(d.name,d.code);
  if(d.kind==='text'){
    if(wordTokens(line).length<=6)return await topicPattern(line,d.label);
    return analyzeText(line,d.label,'text')
  }
}
async function addLanguageRefsIfHelpful(){
  let existing=new Set(originals.filter(x=>x.domain==='language').map(x=>x.title.toLowerCase()));
  let jobs=[['English','en'],['Finnish','fi'],['Japanese','ja'],['Spanish','es']].filter(([n])=>!existing.has(n.toLowerCase()));
  let got=await Promise.allSettled(jobs.map(([n,c])=>languagePattern(n,c)));
  for(const x of got)if(x.status==='fulfilled'){x.value.isReference=true;patterns.push(x.value);compareNew(x.value)}
}
async function run(){
  if(busy)return;
  busy=true;clearInterval(wanderTimer);originals=[];patterns=[];relationships=[];wanderStep=0;render();
  let lines=splitInputs($('#input').value);
  if(!lines.length){busy=false;$('#empty').style.display='block';return}
  $('#goBtn').disabled=true;$('#goBtn').textContent='Finding…';$('#status').classList.add('show');$('#statusText').textContent='Turning each thing into a structural pattern…';
  try{
    let built=await Promise.allSettled(lines.map(buildOriginal));
    originals=built.filter(x=>x.status==='fulfilled'&&x.value).map(x=>x.value);
    patterns=[...originals,...refs()];
    for(const p of patterns)compareNew(p);
    if(originals.length===1||!originals.some(x=>x.domain==='language')){
      $('#statusText').textContent='Checking a few language patterns too…';
      await addLanguageRefsIfHelpful()
    }
    let userIds=new Set(originals.map(x=>x.id));
    relationships=relationships.filter(r=>userIds.has(r.a.id)||userIds.has(r.b.id)||r.a.root===r.b.root||originals.some(o=>o.root===r.a.root||o.root===r.b.root));
    render();startWander();
    $('#statusText').textContent=`Still looking… ${patterns.length} pattern versions tried`;
  }catch(e){
    $('#statusText').textContent='Some sources failed, but local comparisons are still available.';
    render();startWander()
  }finally{
    busy=false;$('#goBtn').disabled=false;$('#goBtn').textContent='Find weird relationships';
    try{localStorage.setItem('pattern-finder-v6-input',$('#input').value)}catch(e){}
  }
}
function reset(){
  clearInterval(wanderTimer);busy=false;originals=[];patterns=[];relationships=[];wanderStep=0;
  $('#input').value='';$('#results').innerHTML='';$('#status').classList.remove('show');$('#empty').style.display='none';$('#goBtn').disabled=false;$('#goBtn').textContent='Find weird relationships';
  try{localStorage.removeItem('pattern-finder-v6-input')}catch(e){}
}
$('#goBtn').onclick=run;
$('#resetBtn').onclick=reset;
$('#input').addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter')run()});
try{let saved=localStorage.getItem('pattern-finder-v6-input');if(saved)$('#input').value=saved}catch(e){}
