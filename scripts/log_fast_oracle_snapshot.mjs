import fs from 'node:fs';
import path from 'node:path';

const MOD = 1000003n;
const FIXED_ROOTS = 4;
const MARKETS = ['ES=F','NQ=F','GC=F','CL=F','BTC-USD','ETH-USD'];
const STREAM = 'https://stream.wikimedia.org/v2/stream/recentchange';
const MARKET = 'https://room-live-mirror.dfp6k69dw5.workers.dev/api/market';
const USGS = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson';
const SWPC = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json';
const HN = 'https://hacker-news.firebaseio.com/v0/maxitem.json';
const clamp = (x,a,b) => Math.max(a,Math.min(b,x));
const SNAPSHOT_MS = 30000;
const MIN_INTERVAL_MS = 5*60*1000;
const HISTORY_DIR = path.join('room','oracle-history');
const LOCK_DIR = path.join('.room_model','fast-oracle-recorder.lock');

function fixedRoots(exact){
  let r = Number(exact);
  for(let i=0;i<FIXED_ROOTS;i++) r = Math.sqrt(r);
  return {r,roots:FIXED_ROOTS};
}

function alex(seed){
  let x = BigInt(Math.abs(Math.trunc(seed))) % MOD;
  let sumSquares = 0n;
  for(let i=1n;i<=1000n;i++){
    const tri = i*(i+1n)/2n;
    x = (x + i*x*x + x*tri) % MOD;
    sumSquares += x*x;
  }
  const exact = sumSquares*sumSquares;
  const transformed = fixedRoots(exact);
  return {r:transformed.r,rootCount:transformed.roots,rRawExact:exact.toString(),sumSquaresExact:sumSquares.toString()};
}

function mean(values){
  const v=values.filter(Number.isFinite);
  return v.length?v.reduce((a,b)=>a+b,0)/v.length:null;
}

function quakeSource(j){
  const f=Array.isArray(j?.features)?j.features:[];
  const mags=f.map(v=>Number(v?.properties?.mag)).filter(Number.isFinite);
  const count=f.length,maxMag=mags.length?Math.max(...mags):0;
  const countScore=clamp((count-20)/30,-1,1);
  const magScore=clamp((maxMag-2.5)/3,-1,1);
  return {count,maxMag,score:(countScore+magScore)/2};
}

function kpSource(j){
  if(!Array.isArray(j)) return {kp:null,score:null};
  let kp=NaN;
  for(let i=j.length-1;i>=0;i--){
    const row=j[i],v=Array.isArray(row)?Number(row[1]):NaN;
    if(Number.isFinite(v)){kp=v;break}
  }
  return Number.isFinite(kp)?{kp,score:clamp((kp-2.5)/4.5,-1,1)}:{kp:null,score:null};
}

function wikiSource(events){
  const rate=events.length*2;
  return {rate,score:Math.tanh((rate-600)/900)};
}

function hnSource(startId,endId,startMs,endMs){
  if(!Number.isFinite(startId)||!Number.isFinite(endId)||endMs<=startMs) return {startId,endId,rate:null,score:null};
  const mins=(endMs-startMs)/60000;
  const rate=Math.max(0,(endId-startId)/mins);
  return {startId,endId,rate,score:clamp((rate-120)/180,-1,1)};
}

function buildOracle(events,quake,kp,hn){
  if(!Array.isArray(events) || events.length < 8) throw new Error('not enough Wikimedia events');
  const wiki=wikiSource(events);
  const physical=mean([quake.score,kp.score]);
  const human=mean([wiki.score,hn.score]);
  if(!Number.isFinite(physical)||!Number.isFinite(human)) throw new Error('both composite buckets are required');
  const combined=(physical+human)/2;
  const seed=Math.round(((clamp(combined,-1,1)+1)/2)*1000002);
  const value=alex(seed);
  return {
    r:value.r,
    rootCount:value.rootCount,
    rRawExact:value.rRawExact,
    sumSquaresExact:value.sumSquaresExact,
    seed,
    scores:{physical,human,combined},
    sources:{quake,kp,wiki,hn},
  };
}

function latestRecordTime(){
  if(!fs.existsSync(HISTORY_DIR)) return NaN;
  const files=fs.readdirSync(HISTORY_DIR).filter(v=>/^\d{4}-\d{2}-\d{2}\.jsonl$/.test(v)).sort();
  if(!files.length) return NaN;
  const text=fs.readFileSync(path.join(HISTORY_DIR,files.at(-1)),'utf8').trim();
  if(!text) return NaN;
  try{return Date.parse(JSON.parse(text.split('\n').filter(Boolean).at(-1)).at||'')}catch{return NaN}
}

function acquireLock(){
  fs.mkdirSync('.room_model',{recursive:true});
  try{
    fs.mkdirSync(LOCK_DIR);
    fs.writeFileSync(path.join(LOCK_DIR,'pid'),String(process.pid));
    return true;
  }catch(e){
    if(e?.code!=='EEXIST') throw e;
    try{
      const pid=Number(fs.readFileSync(path.join(LOCK_DIR,'pid'),'utf8'));
      if(Number.isInteger(pid)&&pid>0){process.kill(pid,0);return false}
    }catch{}
    fs.rmSync(LOCK_DIR,{recursive:true,force:true});
    fs.mkdirSync(LOCK_DIR);
    fs.writeFileSync(path.join(LOCK_DIR,'pid'),String(process.pid));
    return true;
  }
}

function releaseLock(){try{fs.rmSync(LOCK_DIR,{recursive:true,force:true})}catch{}}

async function requestJson(url,ms=10000){
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),ms);
  try{
    const r=await fetch(url,{headers:{accept:'application/json'},signal:ctl.signal});
    if(!r.ok) throw new Error(`${url} ${r.status}`);
    return await r.json();
  } finally {clearTimeout(timer)}
}

async function wikiStreamSample(ms=SNAPSHOT_MS){
  const ctl=new AbortController();
  const timer=setTimeout(()=>ctl.abort(),ms);
  const events=[];
  const sampleStart=new Date();
  try{
    const r=await fetch(STREAM,{headers:{accept:'text/event-stream','user-agent':'FastOracleRecorder/9.0'},signal:ctl.signal});
    if(!r.ok) throw new Error(`wiki stream ${r.status}`);
    if(!r.body) throw new Error('wiki stream has no body');
    const reader=r.body.getReader(),dec=new TextDecoder();
    let buf='';
    while(true){
      let part;
      try{part=await reader.read()}catch(e){if(ctl.signal.aborted) break;throw e}
      if(part.done) break;
      buf=(buf+dec.decode(part.value,{stream:true})).replace(/\r\n/g,'\n');
      let cut;
      while((cut=buf.indexOf('\n\n'))>=0){
        const block=buf.slice(0,cut);buf=buf.slice(cut+2);
        for(const line of block.split('\n')){
          if(!line.startsWith('data:')) continue;
          try{const j=JSON.parse(line.slice(5).trim());events.push({bot:!!j.bot,minor:!!j.minor,type:String(j.type||'')})}catch{}
        }
      }
      if(ctl.signal.aborted) break;
    }
  } finally {clearTimeout(timer);ctl.abort()}
  return {events,sampleStart:sampleStart.toISOString(),sampleEnd:new Date().toISOString()};
}

async function yahoo(symbol){
  const u=new URL(MARKET);
  u.searchParams.set('symbol',symbol);u.searchParams.set('interval','1m');u.searchParams.set('range','1d');u.searchParams.set('prepost','1');u.searchParams.set('fresh',Date.now().toString());
  const j=await requestJson(u.toString());
  const c=j?.payload?.chart?.result?.[0],times=c?.timestamp||[],closes=c?.indicators?.quote?.[0]?.close||[];
  for(let i=Math.min(times.length,closes.length)-1;i>=0;i--){const ts=Number(times[i]),p=Number(closes[i]);if(Number.isFinite(ts)&&Number.isFinite(p)&&p>0)return{price:p,marketTs:ts}}
  const p=Number(c?.meta?.regularMarketPrice);
  return Number.isFinite(p)&&p>0?{price:p,marketTs:null}:null;
}

fs.mkdirSync(HISTORY_DIR,{recursive:true});
const lastAt=latestRecordTime(),now=Date.now();
if(Number.isFinite(lastAt)&&now-lastAt<MIN_INTERVAL_MS){console.log(JSON.stringify({skipped:true,reason:'interval',ageMs:now-lastAt}));process.exit(0)}
if(!acquireLock()){console.log(JSON.stringify({skipped:true,reason:'sampling-in-progress'}));process.exit(0)}

try{
  const hnStartAt=Date.now();
  const hnStart=Number(await requestJson(HN));
  const sample=await wikiStreamSample();
  const hnEndAt=Date.now();
  const [hnEndRaw,quakeRaw,kpRaw,...marketResults]=await Promise.all([
    requestJson(HN),requestJson(USGS),requestJson(SWPC),...MARKETS.map(s=>yahoo(s).catch(e=>({error:String(e?.message||e)})))
  ]);
  const hn=hnSource(hnStart,Number(hnEndRaw),hnStartAt,hnEndAt);
  const quake=quakeSource(quakeRaw),kp=kpSource(kpRaw);
  const oracle=buildOracle(sample.events,quake,kp,hn);
  const markets={};
  marketResults.forEach((v,i)=>{markets[MARKETS[i]]=v&&v.price?v:{error:v?.error||'no positive market price'}});
  const at=new Date();
  const record={
    at:at.toISOString(),sampleStart:sample.sampleStart,sampleEnd:sample.sampleEnd,
    model:'nonmarket-r-v9-world-human-event-wiki-fixed-four-roots',oracle,markets,
  };
  const file=path.join(HISTORY_DIR,`${at.toISOString().slice(0,10)}.jsonl`);
  fs.appendFileSync(file,JSON.stringify(record)+'\n');
  console.log(JSON.stringify({at:record.at,r:oracle.r,seed:oracle.seed,scores:oracle.scores,sources:oracle.sources,events:sample.events.length,markets},null,2));
} finally {releaseLock()}
