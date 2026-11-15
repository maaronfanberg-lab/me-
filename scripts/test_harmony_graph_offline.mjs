// Regression: Harmony Graph must remain responsive when upstream APIs never resolve.
// Run: node scripts/test_harmony_graph_offline.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const scripts=[
  'things-universe-v16-data.js',
  'things-universe-v23-state.js',
  'things-universe-v22-sources.js',
  'things-universe-v20-core.js',
  'things-universe-v21-growth.js',
  'things-universe-v24-progressive.js',
  'things-universe-v24-selection.js',
  'things-universe-v24-controls.js',
  'things-universe-v24-gestures.js',
  'things-universe-v24-init.js',
];
const nodes=new Map();
const fakeCanvasContext=new Proxy({}, {get:()=>()=>{}});
function element(id){
  if(!nodes.has(id)){
    const classes=new Set();
    nodes.set(id,{
      value:'',textContent:'',innerHTML:'',style:{},children:[],
      clientWidth:700,clientHeight:500,disabled:false,
      classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),
        toggle:(x,yes)=>yes?classes.add(x):classes.delete(x),contains:x=>classes.has(x)},
      getBoundingClientRect:()=>({left:0,top:0,width:700,height:500}),
      getContext:()=>fakeCanvasContext,addEventListener(){},setPointerCapture(){}
    });
  }
  return nodes.get(id);
}
const document={
  querySelector:element,
  documentElement:{style:{setProperty(){}}}
};
const window={
  innerHeight:700,visualViewport:{height:700,addEventListener(){}},
  addEventListener(){}
};
const sandbox={
  document,window,performance:{now:()=>1},devicePixelRatio:2,
  requestAnimationFrame:()=>0,
  // Keep deferred DOM timers inert to test the graph synchronously.
  setTimeout:()=>0,clearTimeout(){},
  fetch:()=>new Promise(()=>{}), // external knowledge services are stalled
  AbortController:class {constructor(){this.signal={}}abort(){}},
  console
};
const context=vm.createContext(sandbox);
for(const name of scripts){
  const file=path.join('apps',name);
  vm.runInContext(fs.readFileSync(file,'utf8'),context,{filename:file});
}
const result=await vm.runInContext(`(async()=>{
  let finished=false;
  addThing('mathematics').then(()=>{finished=true});
  for(let i=0;i<60;i++)await Promise.resolve();
  const initial={finished,nodes:N.length,edges:L.length,ready:!!document.querySelector('#add').onclick};
  await addThing('physics');
  initial.seeds=seeds.length;
  toggle();initial.autoOn=auto;toggle();initial.autoOff=!auto;
  connectMode=true;toggleConnectNode(N[0]);toggleConnectNode(N[1]);
  initial.selected=connectSelection.length;
  reset();initial.remaining=N.length;
  return initial;
})()`,context);
assert.equal(result.ready,true,'Add button must be wired');
assert.equal(result.finished,true,'Add cannot wait for stalled APIs');
assert.ok(result.nodes>=30,'Mathematics atlas must populate immediately');
assert.ok(result.edges>=25,'Verified conceptual connections must render');
assert.equal(result.seeds,2,'Multiple seeds must still work');
assert.equal(result.autoOn,true,'Auto-grow must turn on');
assert.equal(result.autoOff,true,'Auto-grow must turn off');
assert.equal(result.selected,2,'Connect selection must work');
assert.equal(result.remaining,0,'Reset must clear the graph');
console.log('Harmony Graph offline smoke passed:',JSON.stringify(result));
