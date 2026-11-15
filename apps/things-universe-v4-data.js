'use strict';
const $=s=>document.querySelector(s),DM='https://api.datamuse.com/words',CN='https://api.conceptnet.io';
const STOP=new Set('thing things something someone anything everything nothing person people object entity stuff make makes made use uses using get gets got have has had do does did good bad big small new old one two way kind type example word words'.split(' '));
const LOCAL={
math:[['mathematics','is another name for'],['numbers','works with'],['geometry','includes'],['pattern','studies'],['symmetry','studies'],['proportion','uses'],['logic','uses'],['science','supports'],['music','appears in'],['art','appears in']],
mathematics:[['numbers','studies'],['geometry','includes'],['pattern','studies'],['symmetry','studies'],['proportion','uses'],['logic','uses'],['science','supports'],['music','appears in'],['art','appears in']],
art:[['creativity','expresses'],['beauty','explores'],['aesthetics','belongs to'],['design','overlaps with'],['geometry','uses'],['pattern','uses'],['symmetry','uses'],['color','uses'],['music','relates to'],['philosophy','connects with'],['emotion','expresses']],
science:[['knowledge','builds'],['experiment','uses'],['evidence','depends on'],['mathematics','uses'],['nature','studies'],['technology','supports'],['measurement','uses'],['art','can intersect with']],
philosophy:[['meaning','asks about'],['ethics','includes'],['logic','uses'],['knowledge','asks about'],['beauty','asks about'],['aesthetics','includes'],['wonder','begins in'],['science','intersects with'],['art','intersects with']],
music:[['rhythm','uses'],['sound','organizes'],['pattern','uses'],['mathematics','relates to'],['emotion','expresses'],['art','is a form of'],['harmony','uses'],['symmetry','can use']],
love:[['attachment','involves'],['care','involves'],['trust','supports'],['emotion','is an'],['oxytocin','relates to'],['dopamine','relates to'],['bonding','relates to'],['peace','can support']],
peace:[['calm','includes'],['safety','depends on'],['trust','supports'],['cooperation','depends on'],['love','can support'],['serotonin','can relate to'],['nonviolence','includes']],
emotion:[['feeling','is a'],['brain','involves'],['body','involves'],['memory','interacts with'],['neurotransmitter','is influenced by'],['dopamine','can involve'],['serotonin','can involve'],['fear','includes'],['love','includes']],
emotions:[['feeling','include'],['brain','involve'],['body','involve'],['memory','interact with'],['neurotransmitters','are influenced by'],['dopamine','can involve'],['serotonin','can involve'],['fear','include'],['love','include']],
neurotransmitter:[['brain','functions in'],['chemical messenger','is a'],['dopamine','includes'],['serotonin','includes'],['norepinephrine','includes'],['emotion','influences']],
neurotransmitters:[['brain','function in'],['chemical messenger','are'],['dopamine','include'],['serotonin','include'],['norepinephrine','include'],['emotion','influence']],
dopamine:[['reward','relates to'],['motivation','relates to'],['learning','supports'],['brain','functions in'],['love','can be involved in'],['anticipation','relates to']],
serotonin:[['mood','influences'],['calm','can support'],['brain','functions in'],['wellbeing','relates to'],['peace','can relate to']],
oxytocin:[['bonding','supports'],['trust','relates to'],['attachment','relates to'],['love','relates to'],['brain','functions in']],
fear:[['threat','responds to'],['safety','contrasts with'],['amygdala','involves'],['cortisol','relates to'],['emotion','is an'],['stress','relates to']],
beauty:[['aesthetics','is studied by'],['art','appears in'],['wonder','can evoke'],['symmetry','can involve'],['proportion','can involve'],['perception','depends on']],
geometry:[['mathematics','belongs to'],['shape','studies'],['space','studies'],['symmetry','studies'],['proportion','uses'],['art','appears in'],['design','appears in'],['pattern','creates']],
pattern:[['repetition','can involve'],['structure','describes'],['mathematics','appears in'],['art','appears in'],['music','appears in'],['nature','appears in'],['symmetry','can involve']],
symmetry:[['balance','resembles'],['geometry','belongs to'],['mathematics','appears in'],['art','appears in'],['beauty','relates to'],['nature','appears in'],['pattern','is a kind of']],
creativity:[['imagination','depends on'],['art','appears in'],['innovation','supports'],['play','can emerge from'],['design','supports']],
imagination:[['creativity','supports'],['fiction','supports'],['possibility','opens'],['art','supports'],['philosophy','interests'],['play','supports']],
trust:[['safety','depends on'],['cooperation','supports'],['love','supports'],['attachment','supports'],['oxytocin','relates to'],['peace','supports']],
'cat in the hat':[["children's literature",'belongs to'],['play','celebrates'],['imagination','awakens'],['mischief','embodies'],['rules','disrupts'],['humor','uses'],['childhood','targets']],
"the cat in the hat":[["children's literature",'belongs to'],['play','celebrates'],['imagination','awakens'],['mischief','embodies'],['rules','disrupts'],['humor','uses'],['childhood','targets']],
"children's literature":[['childhood','centers on'],['play','often uses'],['imagination','cultivates'],['education','can support'],['storytelling','uses']],
play:[['imagination','feeds'],['learning','supports'],['freedom','expresses'],['creativity','supports'],['joy','creates']],
rules:[['ethics','relate to'],['freedom','limit'],['social norms','overlap with'],['order','support'],['authority','come from']],
humor:[['joy','evokes'],['play','supports'],['absurdity','can use'],['incongruity','often uses']],
childhood:[['play','centers on'],['education','connects to'],['curiosity','contains'],['imagination','contains'],['learning','contains']],
ethics:[['philosophy','belongs to'],['responsibility','involves'],['care','can ground'],['rules','relates to'],['values','studies']],
aesthetics:[['philosophy','belongs to'],['beauty','studies'],['art','studies'],['imagination','relates to'],['perception','considers']],
meaning:[['philosophy','interests'],['language','depends on'],['identity','shapes'],['storytelling','can carry']],
knowledge:[['philosophy','investigates'],['science','builds'],['learning','can build'],['evidence','supports']],
wonder:[['curiosity','feeds'],['philosophy','begins in'],['beauty','can evoke'],['science','can motivate']],
learning:[['education','belongs to'],['knowledge','builds'],['dopamine','supports'],['curiosity','supports']],
freedom:[['choice','requires'],['peace','can support'],['ethics','relates to'],['play','can express'],['rules','can limit']],
calm:[['peace','belongs to'],['serotonin','relates to'],['safety','supports'],['emotion','is a state of']],
safety:[['peace','supports'],['trust','supports'],['fear','contrasts with'],['calm','supports']],
care:[['love','expresses'],['ethics','can ground'],['attachment','supports'],['peace','can support']],
attachment:[['love','connects to'],['trust','supports'],['oxytocin','relates to'],['bonding','is a form of']],
bonding:[['love','connects to'],['attachment','is a form of'],['oxytocin','relates to'],['trust','supports']],
brain:[['neurotransmitter','uses'],['emotion','supports'],['memory','supports'],['perception','supports'],['learning','supports']],
color:[['art','appears in'],['design','appears in'],['perception','depends on'],['beauty','can contribute to']],
design:[['art','overlaps with'],['geometry','uses'],['pattern','uses'],['creativity','uses'],['function','balances with form']],
nature:[['science','studies'],['pattern','contains'],['symmetry','contains'],['beauty','can contain'],['art','inspires']],
logic:[['philosophy','uses'],['mathematics','uses'],['reasoning','formalizes'],['science','uses']],
proportion:[['mathematics','uses'],['geometry','uses'],['art','uses'],['beauty','can involve'],['design','uses']],
rhythm:[['music','uses'],['pattern','is a'],['time','organizes'],['body','appears in']],
harmony:[['music','uses'],['proportion','can involve'],['pattern','can involve'],['beauty','can evoke']],
curiosity:[['wonder','feeds'],['learning','supports'],['science','motivates'],['philosophy','motivates']],
cooperation:[['trust','requires'],['peace','supports'],['social behavior','is a'],['care','can support']]
};
let nodes=[],links=[],A=null,B=null,selected=null,timer=null,busy=false,round=0,meetKey=null,bridgeKeys=new Set(),bridgeEdges=new Set(),sourceState={datamuse:true,conceptnet:true};
const semCache=new Map(),relCache=new Map();
function key(s){return String(s||'').toLowerCase().trim().replace(/[’']/g,'').replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' ').slice(0,80)}
function label(s){return String(s||'').trim().replace(/_/g,' ').replace(/\s+/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}
function valid(w){w=key(w);return w.length>1&&w.length<55&&!STOP.has(w)&&!/^(wikipedia|article|category|list of)/.test(w)}
async function jfetch(url,ms=6500){const c=new AbortController(),t=setTimeout(()=>c.abort(),ms);try{const r=await fetch(url,{signal:c.signal});if(!r.ok)throw Error('HTTP '+r.status);return await r.json()}finally{clearTimeout(t)}}
async function semantic(term){const k=key(term);if(semCache.has(k))return semCache.get(k);const map=new Map();for(const [w,rel] of (LOCAL[k]||[])){const wk=key(w);if(valid(wk)&&wk!==k)map.set(wk,{key:wk,label:label(w),score:180-(map.size*7),rel,source:'local'});}let remote=false;try{const [ml,trg]=await Promise.all([jfetch(`${DM}?ml=${encodeURIComponent(k)}&max=90`),jfetch(`${DM}?rel_trg=${encodeURIComponent(k)}&max=60`)]);remote=true;sourceState.datamuse=true;for(const x of [...ml,...trg]){const wk=key(x.word);if(!valid(wk)||wk===k)continue;const score=Math.log10((Number(x.score)||1)+10)*28;const prev=map.get(wk);if(!prev||score>prev.score)map.set(wk,{key:wk,label:label(x.word),score,rel:prev?.rel||'semantically related to',source:prev?.source||'datamuse'});}}catch{sourceState.datamuse=false;}const out=[...map.values()].sort((a,b)=>b.score-a.score);out.remote=remote;semCache.set(k,out);return out}
async function relation(a,b,hint){if(hint&&hint!=='semantically related to')return hint;const id=[key(a),key(b)].sort().join('|');if(relCache.has(id))return relCache.get(id);let text=hint||'semantically related to';try{const j=await jfetch(`${CN}/query?node=/c/en/${encodeURIComponent(key(a).replace(/ /g,'_'))}&other=/c/en/${encodeURIComponent(key(b).replace(/ /g,'_'))}&limit=5`,4500);sourceState.conceptnet=true;const e=(j.edges||[])[0];if(e?.rel?.label){const m={IsA:'is a',PartOf:'part of',UsedFor:'used for',Causes:'can cause',HasProperty:'has property',SimilarTo:'similar to',Antonym:'opposite of',RelatedTo:'related to',CapableOf:'can',HasA:'has',AtLocation:'found at'};text=m[e.rel.label]||e.rel.label;}}catch{sourceState.conceptnet=false;}relCache.set(id,text);return text}
function addNode(k,side,depth=0,rawLabel){k=key(k);if(!k)return null;let n=nodes.find(x=>x.key===k);if(!n){n={id:'n'+Math.random().toString(36).slice(2,10),key:k,label:rawLabel||label(k),side:side||'',sides:{A:side==='A',B:side==='B'},depth,bridge:false,freshUntil:Date.now()+1400};nodes.push(n)}else if(side){n.sides=n.sides||{A:false,B:false};n.sides[side]=true;if(n.sides.A&&n.sides.B)n.side='both';else if(!n.side)n.side=side;n.depth=Math.min(n.depth??depth,depth)}return n}
function eid(a,b){a=a.id||a;b=b.id||b;return a<b?a+'|'+b:b+'|'+a}
function addLink(a,b,text){if(!a||!b||a.id===b.id)return null;const id=eid(a,b);let e=links.find(l=>eid(l.source,l.target)===id);if(!e){e={source:a.id,target:b.id,label:text||'related to',bridge:false};links.push(e)}return e}
