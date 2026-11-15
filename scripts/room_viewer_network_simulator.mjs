import fs from 'node:fs';
import vm from 'node:vm';

const HTML = fs.readFileSync('room/index.html', 'utf8');
const SCRIPT_MATCH = HTML.match(/<script>\s*([\s\S]*?)<\/script>/i);
if (!SCRIPT_MATCH) throw new Error('room/index.html has no executable script');
const VIEWER_SCRIPT = SCRIPT_MATCH[1];

const RELAY = 'https://room-live-mirror.dfp6k69dw5.workers.dev/api/feed';
const RAW = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/feed.json';
const API = 'https://api.github.com/repos/maaronfanberg-lab/me-/contents/room/feed.json';
const HISTORY_RAW = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/conversation.json';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const nowIso = offset => new Date(Date.now() + offset * 1000).toISOString();

function beatMessages(beat, prefix='VM') {
  return ['sarah','mara','owen','jules'].map((speaker,i)=>({
    id:`${prefix.toLowerCase()}-${beat}-${speaker}`,
    speaker,
    text:`${prefix} BEAT ${beat} ${speaker.toUpperCase()}`,
    at:nowIso(i * .01),
    beat_id:`${prefix.toLowerCase()}-beat-${beat}`,
  }));
}

function feed(beat,{offset=0,prefix='VM',conversation=null}={}) {
  return {
    generated_at:nowIso(offset),
    state:{cycle:beat,last_run:nowIso(offset),beat_message_count:4},
    minds:{entities:{sarah:{name:'Sarah'},mara:{name:'Mara'},owen:{name:'Owen'},jules:{name:'Jules'}}},
    conversation:conversation || beatMessages(beat,prefix),
  };
}

function history(prefix='VM') {
  const out=[];
  for(let i=1;i<=996;i++) out.push({
    id:`${prefix.toLowerCase()}-history-${i}`,
    speaker:['sarah','mara','owen','jules'][i%4],
    text:`${prefix} retained ${i}`,
    at:new Date(Date.now()-(1400-i)*1000).toISOString(),
    beat_id:`${prefix.toLowerCase()}-history-beat-${Math.floor(i/4)}`,
  });
  out.push(...beatMessages(100,prefix));
  return out;
}

function apiPayload(data) {
  return {content:Buffer.from(JSON.stringify(data),'utf8').toString('base64'),encoding:'base64',type:'file'};
}

class FakeNode {
  constructor(tag='div', registry=null) {
    this.tagName=tag.toUpperCase();
    this.registry=registry;
    this.children=[];
    this.parentNode=null;
    this.textContent='';
    this.className='';
    this.disabled=false;
    this.classList={toggle:(name,on)=>{
      const set=new Set(String(this.className||'').split(/\s+/).filter(Boolean));
      if(on)set.add(name);else set.delete(name);
      this.className=[...set].join(' ');
    }};
  }
  appendChild(child){
    if(child?.isFragment){for(const c of [...child.children])this.appendChild(c);return child;}
    if(child){child.parentNode=this;this.children.push(child);}return child;
  }
  append(...items){for(const item of items){if(item instanceof FakeNode)this.appendChild(item);else this.textContent+=String(item ?? '');}}
  replaceChildren(...items){for(const c of this.children)c.parentNode=null;this.children=[];for(const item of items)this.appendChild(item);}
  querySelector(selector){return walk(this).find(n=>matches(n,selector))||null;}
  querySelectorAll(selector){return walk(this).filter(n=>matches(n,selector));}
  remove(){if(!this.parentNode)return;const p=this.parentNode;p.children=p.children.filter(c=>c!==this);this.parentNode=null;}
}

function walk(root){const out=[];for(const c of root.children||[]){out.push(c,...walk(c));}return out;}
function matches(node,selector){if(selector.startsWith('.'))return String(node.className||'').split(/\s+/).includes(selector.slice(1));return false;}
function deepText(node){return [node.textContent||'',...(node.children||[]).map(deepText)].join(' ');}

function makeDom(){
  const ids={status:new FakeNode('button'),people:new FakeNode('div'),chat:new FakeNode('main'),meta:new FakeNode('div')};
  const empty=new FakeNode('div');empty.className='empty';empty.textContent='Loading the room…';ids.chat.appendChild(empty);
  const document={
    visibilityState:'visible',
    documentElement:{scrollHeight:10000},
    querySelector(sel){return sel.startsWith('#')?ids[sel.slice(1)]||null:null;},
    createElement(tag){return new FakeNode(tag);},
    createDocumentFragment(){const n=new FakeNode('fragment');n.isFragment=true;return n;},
    addEventListener(){},
  };
  const window={scrollY:0,innerHeight:844,scrollTo(){},addEventListener(){}};
  return {ids,document,window};
}

function response(data,status=200){return {ok:status>=200&&status<300,status,async json(){return data;}};}
function unsafeHeaders(opts={}){
  const headers=opts.headers||{};
  const entries=headers instanceof Headers?[...headers.entries()]:Object.entries(headers);
  return entries.map(([k])=>String(k).toLowerCase()).filter(k=>k==='cache-control'||k==='pragma');
}

async function runViewer(fetchImpl){
  const {ids,document,window}=makeDom();
  const intervals=[];
  const fetchRecords=[];
  const wrappedFetch=async(url,opts={})=>{
    fetchRecords.push({url:String(url),headers:opts.headers||{},unsafe:unsafeHeaders(opts)});
    return fetchImpl(String(url),opts);
  };
  const context=vm.createContext({
    document,window,fetch:wrappedFetch,
    AbortController,Uint8Array,TextDecoder,atob,Math,Date,Promise,Set,Object,Array,String,Number,JSON,
    console,
    setTimeout,
    clearTimeout,
    setInterval(fn){intervals.push(fn);return intervals.length;},
    clearInterval(){},
  });
  vm.runInContext(VIEWER_SCRIPT,context,{filename:'room/index.html'});
  await sleep(80);
  return {ids,intervals,fetchRecords,async tick(times=1){for(let i=0;i<times;i++){for(const fn of intervals)await fn();await sleep(40);}}};
}

function countMessages(chat){return chat.querySelectorAll('.msg').length;}
function statusBeat(status){const m=String(status.textContent||'').match(/beat\s+(\d+)/i);return m?Number(m[1]):null;}

async function fallbackScenario(){
  const retained=history('FALLBACK');
  let apiCalls=0;
  const runner=await runViewer(async(url,opts)=>{
    if(url.startsWith(RELAY)||url.startsWith(RAW))throw new TypeError('simulated live transport failure');
    if(url.startsWith(API)){
      apiCalls++;
      const catchup=feed(103,{prefix:'FALLBACK',conversation:[...beatMessages(101,'FALLBACK'),...beatMessages(102,'FALLBACK'),...beatMessages(103,'FALLBACK')]});
      return response(apiPayload(catchup));
    }
    if(url.startsWith(HISTORY_RAW)||url.startsWith('conversation.json'))return response(retained);
    if(url.startsWith('feed.json'))return response(feed(100,{offset:-300,prefix:'FALLBACK'}));
    throw new Error('unexpected URL '+url);
  });
  await runner.tick(2);
  const text=deepText(runner.ids.chat);
  const beat=statusBeat(runner.ids.status);
  const unsafe=runner.fetchRecords.flatMap(r=>r.unsafe);
  return {
    pass:beat>=103&&countMessages(runner.ids.chat)>=1000&&[101,102,103].every(n=>text.includes(`FALLBACK BEAT ${n}`))&&apiCalls>=1&&unsafe.length===0,
    observed_beat:beat,
    messages:countMessages(runner.ids.chat),
    meta:runner.ids.meta.textContent,
    api_calls:apiCalls,
    unsafe_request_headers:unsafe,
  };
}

async function simpleGetScenario(){
  const retained=history('LIVE');
  let liveBeat=100;
  const methods=[];
  const runner=await runViewer(async(url,opts)=>{
    if(url.startsWith(RELAY)){
      const unsafe=unsafeHeaders(opts);
      if(unsafe.length)throw new TypeError('simulated preflight rejection for '+unsafe.join(','));
      methods.push('GET');
      liveBeat=Math.min(103,liveBeat+1);
      return response(feed(liveBeat,{prefix:'LIVE'}));
    }
    if(url.startsWith(RAW))throw new Error('raw should not be needed while relay is fresh');
    if(url.startsWith(API))throw new Error('API should not be needed while relay is fresh');
    if(url.startsWith(HISTORY_RAW)||url.startsWith('conversation.json')){
      const unsafe=unsafeHeaders(opts);
      if(unsafe.length)throw new TypeError('simulated history preflight rejection');
      return response(retained);
    }
    if(url.startsWith('feed.json'))return response(feed(100,{offset:-300,prefix:'LIVE'}));
    throw new Error('unexpected URL '+url);
  });
  await runner.tick(2);
  const text=deepText(runner.ids.chat);
  const beat=statusBeat(runner.ids.status);
  const unsafe=runner.fetchRecords.flatMap(r=>r.unsafe);
  return {
    pass:beat>=103&&[101,102,103].every(n=>text.includes(`LIVE BEAT ${n}`))&&unsafe.length===0&&methods.length>=3,
    observed_beat:beat,
    messages:countMessages(runner.ids.chat),
    meta:runner.ids.meta.textContent,
    relay_gets:methods.length,
    unsafe_request_headers:unsafe,
  };
}

async function monotonicScenario(){
  const retained=history('MONO');
  let call=0;
  const runner=await runViewer(async(url)=>{
    if(url.startsWith(RELAY)){
      call++;
      if(call===1)return response(feed(103,{prefix:'MONO'}));
      return response(feed(102,{offset:-20,prefix:'MONO'}));
    }
    if(url.startsWith(HISTORY_RAW)||url.startsWith('conversation.json'))return response(retained);
    if(url.startsWith(RAW))throw new Error('raw should not be needed');
    if(url.startsWith(API))throw new Error('API should not be needed');
    if(url.startsWith('feed.json'))return response(feed(100,{offset:-300,prefix:'MONO'}));
    throw new Error('unexpected URL '+url);
  });
  await runner.tick(2);
  const beat=statusBeat(runner.ids.status);
  return {pass:beat===103,observed_beat:beat,relay_calls:call,meta:runner.ids.meta.textContent};
}

const scenarios={
  stale_pages_api_catchup:await fallbackScenario(),
  simple_cross_origin_gets:await simpleGetScenario(),
  monotonic_no_regression:await monotonicScenario(),
};
const pass=Object.values(scenarios).every(x=>x.pass);
const out={checked_at:new Date().toISOString(),pass,source:'actual room/index.html script executed in Node VM',scenarios};
fs.writeFileSync('room/viewer-fast-simulator-diagnostic.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
if(!pass)process.exit(1);
