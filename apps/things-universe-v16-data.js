'use strict';
const $=s=>document.querySelector(s),CN='https://api.conceptnet.io',WIKI='https://en.wikipedia.org/w/api.php',WD='https://www.wikidata.org/w/api.php';
const COLORS=['#76e2d8','#d8c985','#ff9f8f','#7eb6ff','#8ed39b','#f2a6d8','#e8a95e','#a9a1ff','#76d1c5','#d9b8ff'];
const AL={math:'mathematics',maths:'mathematics',numbers:'number',numerals:'number',fungi:'fungus',funguses:'fungus',trees:'tree',organisms:'organism',systems:'system',networks:'network',patterns:'pattern',languages:'language',emotions:'emotion',waves:'wave',sounds:'sound',vibrations:'vibration',bacteria:'bacterium',animals:'animal',plants:'plant',sciences:'science',quantities:'quantity',measurements:'measurement',integers:'integer',fractions:'fraction',primes:'prime number',equations:'equation',functions:'function',sets:'set',proofs:'proof',theorems:'theorem',graphs:'graph',matrices:'matrix',vectors:'vector'};
const SAFE=new Set(['mathematics','physics','ethics','aesthetics','economics','politics','analysis','species','series','statistics']);
function raw(s){return String(s||'').toLowerCase().trim().replace(/[’']/g,'').replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' ').slice(0,80)}
function key(s){let k=raw(s);if(AL[k])return AL[k];if(!SAFE.has(k)){if(k.endsWith('ies')&&k.length>4)return k.slice(0,-3)+'y';if(k.endsWith('s')&&!k.endsWith('ss')&&k.length>4)return k.slice(0,-1)}return k}
function cap(s){return String(s).replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}
const G=new Map();
function rel(a,r,b,rb='connects to'){for(const[x,z,y]of[[a,r,b],[b,rb,a]]){let k=key(x),q=key(y);if(!G.has(k))G.set(k,[]);G.get(k).push({k:q,l:cap(y),r:z,score:500,src:'atlas'})}}
function group(p,r,items,rb='belongs to'){for(const c of items.split('|'))rel(p,r,c,rb)}
rel('mathematics','studies and uses','number','is studied and used by');
group('mathematics','includes','arithmetic|algebra|geometry|calculus|mathematical analysis|topology|combinatorics|probability|statistics|logic|set theory|number theory|discrete mathematics|applied mathematics|pure mathematics|linear algebra|abstract algebra|graph theory|category theory|game theory|information theory|optimization|numerical analysis|measure theory|complex analysis|real analysis|functional analysis|differential geometry|algebraic geometry|mathematical logic|model theory|proof theory|dynamical system|differential equation|mathematical physics');
group('number','has kinds including','natural number|integer|rational number|irrational number|real number|complex number|prime number|composite number|even number|odd number|positive number|negative number|cardinal number|ordinal number|algebraic number|transcendental number|imaginary number|zero|one|fraction|decimal|percentage|ratio|numeral|digit','is a kind of');
group('number','is used in','counting|measurement|calculation|equation|sequence|series|coordinate|probability|statistics|computer science|physics|economics|music','uses');
group('arithmetic','uses','addition|subtraction|multiplication|division|exponentiation|root|logarithm|modular arithmetic|order of operations','is used by');
group('algebra','studies and uses','variable|equation|polynomial|function|matrix|vector|group|ring|field|identity|inequality|linear equation|quadratic equation','is studied or used by');
group('geometry','studies','point|line|plane|angle|triangle|circle|polygon|polyhedron|dimension|distance|area|volume|symmetry|coordinate system|transformation','is studied by');
group('calculus','studies and uses','limit|derivative|integral|continuity|rate of change|area|series|differential equation|multivariable calculus|vector calculus','is studied or used by');
group('number theory','studies','integer|prime number|divisibility|factorization|congruence|modular arithmetic|diophantine equation|perfect number|fibonacci number|cryptography','is studied by');
group('set theory','studies','set|element|subset|union|intersection|complement|cardinality|infinity|power set|relation|function','is studied by');
group('logic','uses','proposition|truth|inference|axiom|theorem|proof|deduction|induction|contradiction|boolean algebra|predicate logic','is used by');
group('probability','studies','random event|random variable|probability distribution|expectation|variance|independence|conditional probability|bayes theorem|stochastic process','is studied by');
group('statistics','studies and uses','data|sample|population|mean|median|variance|standard deviation|distribution|regression|correlation|estimation|hypothesis test|statistical inference','is studied or used by');
group('computer science','uses','algorithm|data structure|logic|graph theory|number|binary number|computation|programming language|complexity theory','is used by');
group('physics','studies','matter|energy|force|motion|space|time|wave|field|particle|measurement|symmetry|system','is studied by');
group('biology','studies','organism|cell|gene|evolution|ecology|species|metabolism|reproduction|adaptation|ecosystem|network','is studied by');
group('philosophy','includes','metaphysics|epistemology|ethics|logic|aesthetics|philosophy of mind|philosophy of science|political philosophy|meaning|knowledge|existence');
group('language','has','word|sentence|grammar|syntax|semantics|phonology|morphology|pragmatics|meaning|communication|symbol','is part of');
group('sound','involves','wave|vibration|frequency|amplitude|medium|air|hearing|signal|resonance|music|acoustics','is involved in');
group('fungus','involves','mycelium|hypha|spore|mushroom|decomposition|symbiosis|organism|ecosystem|nutrient cycle|network|growth|substrate','is involved in');
group('network','has','node|edge|connection|path|degree|cluster|hub|flow|topology|graph','is part of');
group('system','has','component|interaction|boundary|input|output|feedback|state|process|structure|network','is part of');
group('pattern','can involve','symmetry|repetition|sequence|rhythm|fractal|structure|regularity|variation|cycle','can appear in');
group('information','can be represented by','data|signal|symbol|number|language|code|bit|message|pattern','can represent');
rel('fungus','is an','organism','includes');rel('organism','is studied by','biology','studies');rel('biology','is a','science','includes');rel('physics','is a','science','includes');rel('sound','is a','wave','can be heard as');rel('sound','is produced by','vibration','can produce');rel('wave','is studied by','physics','studies');rel('fungus','can form','symbiosis','can involve');rel('symbiosis','can involve','cooperation','can occur in');rel('cooperation','can support','trust','can support');rel('philosophy','uses','logic','is used in');rel('philosophy','includes','ethics','belongs to');rel('mycelium','forms','network','can resemble');rel('network','is a kind of','system','can include');rel('system','has','structure','can describe');rel('structure','can show','pattern','can describe');rel('pattern','appears in','nature','can contain');
const REL={IsA:['is a kind of','includes'],PartOf:['is part of','contains'],HasA:['has','is a feature of'],UsedFor:['is used for','uses'],CapableOf:['can','can be done by'],Causes:['can cause','can be caused by'],HasProperty:['has property','can describe'],AtLocation:['is found in','can contain'],MadeOf:['is made of','can make up'],HasPrerequisite:['requires','is required for'],DefinedAs:['is defined as','can define'],CreatedBy:['is created by','creates'],Entails:['entails','can be entailed by'],SymbolOf:['can symbolize','can be symbolized by']};
const WDREL={P31:'is a',P279:'is a subtype of',P361:'is part of',P527:'has part',P101:'belongs to field',P1269:'is a facet of',P1552:'has quality',P366:'is used for',P2579:'is studied by',P2283:'uses'};
const BADCAT=/articles|pages|wikipedia|cs1|short description|webarchive|use (dmy|mdy)|stub|cleanup|maintenance|tracking|redirects|templates|commons category|coordinates|births|deaths|living people/i;
const BADTITLE=/^(list of|outline of|index of|template:|category:|portal:|talk:)/i;
