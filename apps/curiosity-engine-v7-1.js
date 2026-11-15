'use strict';
const $=s=>document.querySelector(s);
const COLORS={seed:'#78e5dd',derived:'#b7a0ff',feature:'#dbc98b'};
const FEATURE_KEYS=['entropy','recurrence','alternation','periodicity','trend','roughness','symmetry','inverseSymmetry','longTail','predictability'];
const LANGS={english:'en',finnish:'fi',spanish:'es',german:'de',french:'fr',italian:'it',portuguese:'pt',swedish:'sv',norwegian:'no',danish:'da',dutch:'nl',polish:'pl',czech:'cs',hungarian:'hu',estonian:'et',japanese:'ja',korean:'ko',chinese:'zh',russian:'ru',greek:'el',turkish:'tr',arabic:'ar',hebrew:'he',hindi:'hi'};
let nodes=[],links=[],matches=[],pairA=null,pairB=null,selected=null,wanderTimer=null,wanderStep=0,busy=false;
let canvas,ctx,W=1,H=1,DPR=1,view={x:0,y:0,k:1},raf=0,lastTime=0;
const pointers=new Map();let gesture=null,downInfo=null;
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const sd=a=>{if(!a.length)return 0;let m=mean(a);return Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/a.length)};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
function uid(){return 'n'+Math.random().toString(36).slice(2,10)}
function normalize(a){if(!a.length)return[0];let m=mean(a),s=sd(a)||1;return a.map(x=>(x-m)/s)}
function minmax(a){if(!a.length)return[0];let lo=Math.min(...a),hi=Math.max(...a),d=hi-lo||1;return a.map(x=>(x-lo)/d)}
function resample(a,n=64){if(!a.length)return Array(n).fill(0);if(a.length===1)return Array(n).fill(a[0]);let out=[];for(let i=0;i<n;i++){let p=i*(a.length-1)/(n-1),j=Math.floor(p),f=p-j;out.push(a[j]*(1-f)+a[Math.min(a.length-1,j+1)]*f)}return out}
function corr(a,b){a=normalize(resample(a));b=normalize(resample(b));let d=Math.sqrt(a.reduce((s,x)=>s+x*x,0)*b.reduce((s,x)=>s+x*x,0))||1;return a.reduce((s,x,i)=>s+x*b[i],0)/d}
function entropy(vals,bins=12){if(!vals.length)return 0;let v=minmax(vals),c=Array(bins).fill(0);for(const x of v)c[Math.min(bins-1,Math.floor(x*bins))]++;let h=0;for(const q of c){if(!q)continue;let p=q/v.length;h-=p*Math.log2(p)}return h/Math.log2(bins)}
function autocorr(a,lag){return a.length<lag+3?0:corr(a.slice(0,-lag),a.slice(lag))}
function turningRate(a){if(a.length<3)return 0;let c=0;for(let i=1;i<a.length-1;i++)if((a[i]-a[i-1])*(a[i+1]-a[i])<0)c++;return c/(a.length-2)}
function zeroCross(a){a=normalize(a);if(a.length<2)return 0;let c=0;for(let i=1;i<a.length;i++)if((a[i]>=0)!==(a[i-1]>=0))c++;return c/(a.length-1)}
function symmetry(a){return a.length<3?0:clamp((corr(a,[...a].reverse())+1)/2)}
function inverseSymmetry(a){return a.length<3?0:clamp((corr(a,[...a].reverse().map(x=>-x))+1)/2)}
function trend(a){if(a.length<3)return 0;return clamp(Math.abs(corr(a,a.map((_,i)=>i))))}
function recurrence(a){if(a.length<4)return 0;let q=minmax(a).map(x=>Math.round(x*8)),sum=0,n=0;for(let lag=1;lag<=Math.min(12,Math.floor(q.length/2));lag++){let c=0;for(let i=lag;i<q.length;i++)if(q[i]===q[i-lag])c++;sum+=c/(q.length-lag);n++}return n?sum/n:0}
function periodicity(a){let best=0;for(let lag=1;lag<=Math.min(20,Math.floor(a.length/2));lag++)best=Math.max(best,Math.abs(autocorr(a,lag)));return clamp(best)}
function predictability(a){if(a.length<5)return 0;let d=a.slice(1).map((x,i)=>x-a[i]);return clamp(1/(1+sd(normalize(d))))}
function spectrum(a,n=28){a=normalize(resample(a,64));let out=[];for(let k=1;k<=n;k++){let re=0,im=0;for(let t=0;t<a.length;t++){let ang=2*Math.PI*k*t/a.length;re+=a[t]*Math.cos(ang);im-=a[t]*Math.sin(ang)}out.push(Math.sqrt(re*re+im*im)/a.length)}return out}
function longTail(counts){let a=[...counts].filter(x=>x>0).sort((x,y)=>y-x);if(a.length<4)return 0;let total=a.reduce((s,x)=>s+x,0),top=a[0]/total,tail=a.slice(Math.ceil(a.length/2)).reduce((s,x)=>s+x,0)/total;return clamp(top*2+(1-tail)*.35)}
function features(seq,extra={}){let sp=spectrum(seq);return{entropy:entropy(seq),recurrence:recurrence(seq),alternation:clamp(extra.alternation??zeroCross(seq)),periodicity:periodicity(seq),trend:trend(seq),roughness:turningRate(seq),symmetry:symmetry(seq),inverseSymmetry:inverseSymmetry(seq),longTail:clamp(extra.longTail??longTail(sp.map(x=>Math.round(x*100)+1))),predictability:predictability(seq)}}
function wordTokens(text){return text.toLocaleLowerCase().match(/[\p{L}\p{M}]+/gu)||[]}
function analyzeText(text,label,domain='text'){let words=wordTokens(text),seq=words.map(w=>[...w].length);if(seq.length<4)seq=[...text].map(c=>/\p{L}/u.test(c)?1:/\d/.test(c)?2:/\s/.test(c)?0:3);if(!seq.length)seq=[0];let freq=new Map();words.forEach(w=>freq.set(w,(freq.get(w)||0)+1));let letters=[...text.toLocaleLowerCase()].filter(c=>/\p{L}/u.test(c));let vowels=new Set([..."aeiouyåäöáéíóúàèìòùâêîôûãõæøаеёиоуыэюяαεηιουω"]);let alt=0;for(let i=1;i<letters.length;i++)if(vowels.has(letters[i])!==vowels.has(letters[i-1]))alt++;return{label,domain,sequence:seq,features:features(seq,{alternation:letters.length>1?alt/(letters.length-1):0,longTail:longTail([...freq.values()])}),description:`${words.length} words reduced to lengths, recurrence, alternation and frequency shape.`}}
function analyzeNumbers(seq,label){return{label,domain:'numbers',sequence:seq,features:features(seq),description:`${seq.length} values reduced to recurrence, trend, symmetry, roughness and frequency structure.`}}
function analyzeEquation(expr,label){let tokens=expr.match(/sin|cos|tan|log|exp|sqrt|[A-Za-zα-ωΑ-Ω]+|\d+(?:\.\d+)?|[+\-*/^=()]|π|∞/g)||[expr];let cat=t=>/^\d/.test(t)?1:/^(sin|cos|tan|log|exp|sqrt)$/.test(t)?5:/^[A-Za-zα-ωΑ-Ωπ]+$/.test(t)?2:/^[+\-]$/.test(t)?-1:/^[*/]$/.test(t)?3:t==='^'?4:t==='('?6:t===')'?-6:0;let seq=tokens.map(cat),f=features(seq);if(/sin|cos|tan/i.test(expr))f.periodicity=Math.max(f.periodicity,.88);return{label,domain:'equation',sequence:seq,features:f,description:`${tokens.length} symbolic tokens reduced to operator rhythm, repetition and hierarchy.`}}
async function languageSample(name){let code=LANGS[name.toLowerCase()];if(!code)return null;let url=`https://${code}.wikipedia.org/w/api.php?action=query&generator=random&grnnamespace=0&prop=extracts&explaintext=1&exintro=1&format=json&origin=*`;let ctrl=new AbortController(),to=setTimeout(()=>ctrl.abort(),6500);try{let r=await fetch(url,{signal:ctrl.signal});let j=await r.json(),p=Object.values(j.query?.pages||{})[0];if(!p?.extract)throw Error('No language sample returned');let a=analyzeText(p.extract,name,'language');a.description=`Native ${name} sample analyzed as word-length, alternation, recurrence and frequency structure.`;return a}finally{clearTimeout(to)}}
function detectInput(text){let low=text.trim().toLowerCase();if(LANGS[low])return'language';let nums=text.trim().split(/[\s,;]+/).map(Number).filter(Number.isFinite);if(nums.length>=4&&nums.length>=text.trim().split(/[\s,;]+/).filter(Boolean).length*.7)return'numbers';if(/[=^]|\b(sin|cos|tan|log|exp|sqrt)\b|π/.test(text))return'equation';return'text'}
function hashAngle(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return (h>>>0)/4294967296*Math.PI*2}