'use strict';
const fs=require('fs'),assert=require('assert');
const html=fs.readFileSync('apps/omef-exclusive.html','utf8');
function section(a,b){const i=html.indexOf(a),j=html.indexOf(b,i+a.length);assert(i>=0&&j>i,'Missing section: '+a);return html.slice(i,j);}
const secondScript=html.indexOf("<script>(function(){'use strict';");
assert(secondScript>=0,'Coupled OMEF source script not located');
const coreStart=html.indexOf('const macros=[',secondScript),coreEnd=html.indexOf('let evolutionOn=true',coreStart);
assert(coreStart>0&&coreEnd>coreStart,'Coupled full engine source was not isolated');
const core=html.slice(coreStart,coreEnd);
const profile=section('function sampleVisualProfile(','function candidateLinks(');
const evolution=section('// Explore the full governing system','function evolutionSearch(force){');
assert(evolution.includes('function fullSpectrumProposal('));
assert(evolution.includes('function paintEvolvingControls('));
assert(profile.includes('function structuralDistance('));
const header="\nconst clamp=(v,a,b)=>Math.max(a,Math.min(b,v));\nconst performance={now:()=>1000};\nlet evolutionAccepted=0,evolutionRejected=0,evolutionOn=true;\nconst store={twinDepth:{value:5},twinMorphDuration:{value:3.6},\n points:{value:250000},ink:{value:9},size:{value:1},twinSpeed:{value:5},twinPersistence:{value:100}};\nconst $=id=>(store[id]||(store[id]={value:0,textContent:'',min:0,max:4,step:.05}));\nconst hot=k=>Array.from({length:6},(_,i)=>i===+k?1:0);\nconst evolutionSeconds=()=>2,evolutionStatus=()=>{},liveRetarget=()=>{},refreshTwinLinkCaptions=()=>{};\n";
const harness="\nconst cfg={global:.4,seed:1,mix:.7,interference:.16,projection:5,links:twinDefaults.map(x=>({...x})),focus:null};\nlet liveState={targetA:presetRaw('A'),targetB:presetRaw('B'),targetCfg:cfg,\n requested:cfg.links.map(x=>({...x})),targetWeights:hot(5),\n A:presetRaw('A'),B:presetRaw('B'),edges:cfg.links.map(x=>({...x})),\n evolutionCycle:0,detailUntil:0};\nactiveEngine='twin';stopped=false;\nconst protectedIds=['points','ink','size','twinSpeed','twinPersistence'];\nconst protectedBefore=Object.fromEntries(protectedIds.map(k=>[k,$(k).value]));\nfor(const d of allDefs)for(const side of ['A','B']){\n const id='tw'+side+'_'+d[0];\n store[id]={value:side==='A'?liveState.targetA[d[0]]:liveState.targetB[d[0]],\n  min:d[2],max:d[3],step:d[4]};\n}\nfor(let i=0;i<8;i++)for(const key of ['source','from','to','strength','lag','offset','gate']){\n const l=cfg.links[i],ranges={strength:[-2,2,.05],lag:[1,144,1],offset:[0,315,5]},\n   r=ranges[key]||[0,1,1];\n store['tl'+i+key]={value:l[key],min:r[0],max:r[1],step:r[2]};\n}\nconst cycles=[];\nfor(let i=0;i<9;i++){\n const beforeA={...liveState.targetA},beforeB={...liveState.targetB},\n  before=liveState.requested.map(x=>({...x})),beforeCfg={...liveState.targetCfg};\n const proposed=fullSpectrumProposal(liveState,+$('twinDepth').value,0);\n const proposedA=allDefs.filter(d=>proposed.A[d[0]]!==beforeA[d[0]]).length;\n const proposedB=allDefs.filter(d=>proposed.B[d[0]]!==beforeB[d[0]]).length;\n const proposedLinks=before.reduce((n,l,index)=>n+['strength','lag','offset'].filter(k=>l[k]!==proposed.edges[index][k]).length,0);\n const proposedGlobals=['global','seed','mix','interference','projection'].filter(k=>beforeCfg[k]!==proposed.cfg[k]).length;\n const ok=liveMutate();\n const changedA=allDefs.filter(d=>liveState.targetA[d[0]]!==beforeA[d[0]]).length;\n const changedB=allDefs.filter(d=>liveState.targetB[d[0]]!==beforeB[d[0]]).length;\n const changedLinks=before.reduce((n,l,index)=>n+['strength','lag','offset'].filter(k=>l[k]!==liveState.requested[index][k]).length,0);\n cycles.push({i,ok,proposedA,proposedB,proposedLinks,proposedGlobals,\n  changedA,changedB,changedLinks,shapeFamilies:liveState.shapeFamilies||0,\n  structuralDistance:liveState.lastNovelty||0});\n}\nconst afterProtected=Object.fromEntries(protectedIds.map(k=>[k,$(k).value]));\nreturn {allDefinitions:allDefs.length*2,cycles,accepted:evolutionAccepted,rejected:evolutionRejected,\n shapeFamilies:liveState.shapeFamilies||0,protectedInputsUnchanged:JSON.stringify(protectedBefore)===JSON.stringify(afterProtected),\n protectedBefore,afterProtected};\n";
const report=(new Function(header+core+profile+evolution+harness))();
assert(report.allDefinitions===122,'Expected 122 controllable equation parameters');
for(const c of report.cycles){
 assert(c.proposedA===61&&c.proposedB===61,'Every A/B formula slider must be included');
 assert(c.proposedLinks===24,'All 24 numerical link controls must move');
 assert(c.proposedGlobals===5,'Five global controls must change in each proposal');
 if(c.ok)assert(c.changedA===61&&c.changedB===61&&c.changedLinks===24,'Accepted candidate must update every math/coupling target');
}
assert(report.accepted>=5,'Evolution did not accept enough coherent states');
assert(report.protectedInputsUnchanged,'An excluded slider was modified');
fs.mkdirSync('audit-artifacts',{recursive:true});
fs.writeFileSync('audit-artifacts/full-spectrum-evolution.json',JSON.stringify(report,null,2));
console.log('FULL_SPECTRUM_AUDIT '+JSON.stringify({cycles:report.cycles.length,accepted:report.accepted,rejected:report.rejected,shapeFamilies:report.shapeFamilies,perCandidateEquationSliders:122,perCandidateLinkSliders:24,perCandidateGlobals:5,excludedControlsPreserved:report.protectedInputsUnchanged}));