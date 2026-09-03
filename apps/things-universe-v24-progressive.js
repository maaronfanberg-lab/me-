'use strict';

// v24 progressive enrichment: preserve the existing graph behavior, but never block
// ordinary growth on the slower multi-source/Falcon pass. Evidence and later Falcon
// relations join the same graph through the existing node/edge/placeChild physics.

const v24ProgressRuns=new Map();
const v24ProgressWatches=new Map();
let v24ProgressEpoch=0;

function v24ProgressRows(data,term){
  let out=[],phase=data?.phase==='evidence'?'multi-source evidence':'Falcon synthesis';
  for(const row of data?.relations||[]){
    let lab=String(row?.label||'').trim(),rel=String(row?.relation||'').trim(),sources=Array.isArray(row?.sources)?row.sources.map(String).filter(Boolean).slice(0,4):[];
    let confidence=Number(row?.confidence);if(!Number.isFinite(confidence))confidence=.5;
    if(confidence<.5||!lab||!rel||!sources.length||!candidateAllowed(lab,term,phase))continue;
    let q=key(lab);if(!q||q===key(term))continue;
    out.push({k:q,l:cap(lab),r:rel,score:170+Math.round(Math.max(0,Math.min(1,confidence))*140),src:`${phase} · ${sources.join(' + ')}`,from:term});
  }
  return out.slice(0,14)
}

function v24MergeProgressCache(term,rows){
  let k=key(term),m=new Map();
  for(const x of cache.get(k)||[])add(m,x);
  for(const x of rows||[])add(m,x);
  let out=[...m.values()].filter(x=>x.k!==k).sort((a,b)=>b.score-a.score);
  cache.set(k,out);return out
}

function v24NotifyProgress(run,rows){
  if(!rows?.length||run.epoch!==v24ProgressEpoch)return;
  run.rows=rows;
  v24MergeProgressCache(run.term,rows);
  for(const fn of run.listeners)try{fn(rows)}catch{}
}

function v24ProgressiveFalcon(term){
  let k=key(term);if(!k)return null;
  let existing=v24ProgressRuns.get(k);
  if(existing){
    if(existing.done&&existing.rows.length)v24MergeProgressCache(term,existing.rows);
    return existing
  }
  let run={k,term:String(term),listeners:new Set(),rows:[],done:false,lastSig:'',epoch:v24ProgressEpoch};
  v24ProgressRuns.set(k,run);
  (async()=>{
    try{
      let context=[];
      try{if(typeof N!=='undefined'&&Array.isArray(N))context=N.slice(-12).map(n=>n?.l).filter(Boolean).slice(0,12)}catch{}
      let start=await postjson(`${THINGS_RELAY}/api/things/enrich`,{term:String(term).slice(0,80),context},5000);
      if(run.epoch!==v24ProgressEpoch)return;
      if(start?.result){
        let rows=v24ProgressRows(start.result,term),sig=JSON.stringify(rows.map(x=>[x.k,x.r,x.src]));
        if(sig&&sig!==run.lastSig){run.lastSig=sig;v24NotifyProgress(run,rows)}
      }
      let id=start?.id;if(!id){run.done=true;return}
      for(let i=0;i<300&&run.epoch===v24ProgressEpoch;i++){
        await nap(i?1800:350);
        let result=await json(`${THINGS_RELAY}/api/things/result?id=${encodeURIComponent(id)}`,4500);
        if(!result)continue;
        if(result?.result){
          let rows=v24ProgressRows(result.result,term),sig=JSON.stringify(rows.map(x=>[x.k,x.r,x.src]));
          if(sig&&sig!==run.lastSig){run.lastSig=sig;v24NotifyProgress(run,rows)}
        }
        if(result?.status==='done'){run.done=true;break}
        if(result?.status==='error'||result?.status==='missing'){run.done=true;break}
      }
    }catch{}finally{run.done=true}
  })();
  return run
}

function v24SubscribeProgress(term,fn){
  let run=v24ProgressRuns.get(key(term));if(!run)return false;
  run.listeners.add(fn);
  if(run.rows.length)queueMicrotask(()=>{if(run.epoch===v24ProgressEpoch)fn(run.rows)});
  return true
}

// Replace only the source orchestration. The original CN/Wikidata/Wikipedia functions,
// ranking, filtering and cache are unchanged; the expensive pass simply stops blocking.
concepts=async function(term){
  let k=key(term);if(cache.has(k))return cache.get(k);
  let m=new Map();
  for(const x of localCommon(k))add(m,x);
  for(const x of G.get(k)||[])add(m,{...x,from:term});
  let c=await cn(k);for(const x of c)add(m,x);
  if(m.size<28){let w=await wd(k);for(const x of w)add(m,x)}
  if(m.size<34){let w=await wiki(k);for(const x of w)add(m,x)}
  let sparse=m.size<34,out=[...m.values()].filter(x=>x.k!==k).sort((a,b)=>b.score-a.score);
  cache.set(k,out);
  if(sparse)v24ProgressiveFalcon(term);
  return out
};

function v24ScheduleProgress(parent,seed,rows){
  let watchKey=`${seed.id}|${parent.id}`,seen=v24ProgressWatches.get(watchKey);if(!seen)return;
  let fresh=[];
  for(const c of rows||[]){let rk=`${c.k}|${c.r}`;if(seen.has(rk))continue;seen.add(rk);fresh.push(c)}
  fresh.slice(0,12).forEach((c,i)=>setTimeout(()=>{
    let liveParent=nById(parent.id),liveSeed=seedById(seed.id);if(!liveParent||!liveSeed||!liveParent.owners?.has(liveSeed.id))return;
    let existed=!!byK(c.k),q=node(c.l,liveSeed,liveParent),wasLinked=hasEdge(liveParent,q);
    if(!existed)placeChild(q,liveParent);
    edge(liveParent,q,c.r,liveSeed.id,c.src);
    if(!existed||!wasLinked)render()
  },i*520))
}

function v24WatchProgress(parent,seed){
  if(!parent||!seed)return false;
  let run=v24ProgressRuns.get(key(parent.k));if(!run)return false;
  let watchKey=`${seed.id}|${parent.id}`;
  if(v24ProgressWatches.has(watchKey))return true;
  v24ProgressWatches.set(watchKey,new Set());
  return v24SubscribeProgress(parent.k,rows=>v24ScheduleProgress(parent,seed,rows))
}

const v24OriginalSprout=sprout;
sprout=async function(root,seed,lim=44){
  let n=await v24OriginalSprout(root,seed,lim);
  v24WatchProgress(root,seed);
  return n
};

const v24OriginalExpand=expand;
expand=async function(seed,target=28){
  let n=await v24OriginalExpand(seed,target);
  // Subscribe only to enrichment jobs already started by concepts() for nodes this
  // territory owns. Nothing here changes traversal, placement, scoring or physics.
  for(const [k] of v24ProgressRuns){let p=byK(k);if(p?.owners?.has(seed.id))v24WatchProgress(p,seed)}
  return n
};

const v24OriginalReset=reset;
reset=function(){
  v24ProgressEpoch++;
  v24ProgressRuns.clear();
  v24ProgressWatches.clear();
  return v24OriginalReset()
};
