'use strict';
const CLUSTER_REPO='maaronfanberg-lab/me-';
const CLUSTER_RESULT_ROOT='https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/cluster/jobs/';
const CLUSTER_PENDING_KEY='things-universe-cluster-pending-v1';
let clusterPollToken=0;
function clusterJobId(){return `discovery-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,9)}`}
function bytesB64(obj){let bytes=new TextEncoder().encode(JSON.stringify(obj)),s='';for(let i=0;i<bytes.length;i++)s+=String.fromCharCode(bytes[i]);return btoa(s)}
function queueUrl(jobId,terms){
  let payload=bytesB64({terms,max_depth:6}),body=['CLUSTER_JOB',`job_id: ${jobId}`,'project: discovery','task: conceptual_bridge',`payload_b64: ${payload}`].join('\n');
  let title=`[cluster-job] Discovery bridge ${jobId}`;
  return `https://github.com/${CLUSTER_REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`
}
function setClusterPending(p){localStorage.setItem(CLUSTER_PENDING_KEY,JSON.stringify(p))}
function getClusterPending(){try{return JSON.parse(localStorage.getItem(CLUSTER_PENDING_KEY)||'null')}catch{return null}}
function cancelClusterPending(){clusterPollToken++;localStorage.removeItem(CLUSTER_PENDING_KEY);think(false)}
function findSeed(label){return seeds.find(s=>key(s.label)===key(label))}
function materializeClusterPath(pair){
  let path=pair?.best;if(!path?.edges?.length)return;
  let sa=findSeed(pair.from),sb=findSeed(pair.to),ra=sa?nById(sa.root):byK(key(pair.from)),rb=sb?nById(sb.root):byK(key(pair.to));
  if(!ra||!rb)return;
  let total=path.edges.length;
  path.edges.forEach((e,i)=>{
    let a=byK(key(e.a)),b=byK(key(e.b));
    if(!a){a=node(e.a);let t=i/(total+1);a.x=ra.x+(rb.x-ra.x)*t;a.y=ra.y+(rb.y-ra.y)*t;a.vx=a.vy=0}
    if(!b){b=node(e.b);let t=(i+1)/(total+1);b.x=ra.x+(rb.x-ra.x)*t;b.y=ra.y+(rb.y-ra.y)*t;b.vx=b.vy=0}
    if(sa&&a!==ra&&a!==rb)own(a,sa);if(sb&&a!==ra&&a!==rb)own(a,sb);
    if(sa&&b!==ra&&b!==rb)own(b,sa);if(sb&&b!==ra&&b!==rb)own(b,sb);
    edge(a,b,e.rel,sa?.id||'',e.source||'Shared Supercomputer')
  });
  if(sa&&sb){let mid=path.edges[Math.floor(path.edges.length/2)],n=byK(key(mid?.b||pair.to));if(n)lastBridge={a:sa.id,b:sb.id,node:n.id}}
  kick(1);render();setTimeout(fit,260)
}
function clusterPathHTML(pair){
  let p=pair?.best;if(!p?.edges?.length)return `<div class="box"><strong>${pair.from} ↔ ${pair.to}</strong><p>The 12-node search did not find a defensible short-to-medium conceptual chain from the current sources.</p></div>`;
  let li=p.edges.map(e=>`<li><b>${e.a}</b> — ${e.rel} → <b>${e.b}</b> <span class="src">(${e.source||'source'})</span></li>`).join('');
  return `<div class="box"><strong>${pair.from} ↔ ${pair.to}</strong><ul>${li}</ul><p>Best route came from the <b>${p.lens||'distributed'}</b> search lens. The aggregator compared independent paths from the 12 cluster nodes and rejected weaker duplicates.</p></div>`
}
function showClusterResult(summary,pending){
  let result=summary?.result;if(result?.status!=='complete')return false;
  let pairs=result.pairs||[],good=pairs.filter(p=>p.best?.edges?.length);
  if(pending.mode==='seeds')for(const p of good)materializeClusterPath(p);
  let intro=good.length?`The Shared Supercomputer found ${good.length} defensible connection${good.length===1?'':'s'} using ${summary.workers||12} parallel nodes.`:`All ${summary.workers||12} nodes completed, but none produced a defensible path from the current sources.`;
  $('#rb').innerHTML=`<h2>${(result.terms||pending.terms).join(' ↔ ')}</h2><div class="box"><p>${intro}</p><p>This result came from the GitHub Supercomputer, not the phone. Different nodes searched through different conceptual lenses before the aggregator ranked the routes.</p></div>${pairs.map(clusterPathHTML).join('')}`;
  $('#reader').classList.add('open');ui(`Supercomputer · ${good.length} connection${good.length===1?'':'s'}`);toast('12-node Discovery result received');return true
}
async function pollCluster(pending){
  let my=++clusterPollToken,started=Date.now();think(true,'Waiting for 12-node Supercomputer…');ui('Supercomputer job queued');
  while(my===clusterPollToken&&Date.now()-started<20*60*1000){
    try{
      let r=await fetch(CLUSTER_RESULT_ROOT+encodeURIComponent(pending.jobId)+'.json?fresh='+Date.now(),{cache:'no-store'});
      if(r.ok){let j=await r.json();if(j.job_id===pending.jobId&&showClusterResult(j,pending)){localStorage.removeItem(CLUSTER_PENDING_KEY);think(false);return}}
    }catch{}
    await new Promise(r=>setTimeout(r,4000))
  }
  if(my===clusterPollToken){think(false);ui('Supercomputer result not received yet');toast('The cluster job is still pending or was not submitted.')}
}
function submitClusterDiscovery(terms,mode='selected'){
  terms=[...new Set((terms||[]).map(x=>String(x).trim()).filter(Boolean))].slice(0,4);
  if(terms.length<2)return toast('Choose at least two ideas');
  let jobId=clusterJobId(),pending={jobId,terms,mode,createdAt:Date.now()};setClusterPending(pending);
  let w=window.open(queueUrl(jobId,terms),'_blank','noopener');
  if(!w)toast('Allow the GitHub job tab to open');else toast('Submit the prefilled GitHub job, then come back here.');
  pollCluster(pending)
}
function findBridge(){if(seeds.length<2)return toast('Add at least two ideas');submitClusterDiscovery(seeds.slice(0,4).map(s=>s.label),'seeds')}
function resumeClusterPending(){let p=getClusterPending();if(p?.jobId&&Array.isArray(p.terms)&&Date.now()-(p.createdAt||0)<20*60*1000)pollCluster(p)}
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){let p=getClusterPending();if(p?.jobId)pollCluster(p)}});
setTimeout(resumeClusterPending,500);
