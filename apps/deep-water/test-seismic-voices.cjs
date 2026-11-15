// Deep Water seismic sonification invariants. Run: node apps/deep-water/test-seismic-voices.cjs
const assert=require('node:assert/strict');
const {Eng}=require('./engine.js')();
const SR=48000;
function makeTrace(){
 const rate=40,n=rate*4,a=new Float32Array(n);let phase=0;
 for(let i=0;i<n;i++){const t=i/rate;const hz=8.5+1.4*Math.sin(2*Math.PI*t/1.8);
  phase+=2*Math.PI*hz/rate;
  a[i]=(0.58+0.25*Math.sin(2*Math.PI*t/2.1))*Math.sin(phase);
 }return a;
}
function render(e,seconds){
 const L=new Float32Array(128),R=new Float32Array(128);let maxVoices=0,energy=0;
 for(let k=0;k<Math.ceil(seconds*SR/128);k++){
  e.process(L,R,128);maxVoices=Math.max(maxVoices,e.B.length);
  for(let i=0;i<128;i++){assert.ok(Number.isFinite(L[i])&&Number.isFinite(R[i]),'finite audio');energy+=L[i]*L[i]+R[i]*R[i];}
 }return{maxVoices,energy};
}
const none=new Eng(SR);none.hum=0;none.szLvl=0;
const quiet=render(none,.25);
assert.equal(none.sdCount||0,0,'no input must not trigger notes');
assert.equal(quiet.energy,0,'no input and no hum must be silent');
const trace=makeTrace(),e=new Eng(SR);e.hum=0;e.szLvl=0;e.sdLog=[];
e.seis({data:trace,drive:trace,rate:40*20});
const measured=render(e,.7);
assert.ok((e.sdCount||0)>100,'every measured half-wave should be represented; count '+e.sdCount);
assert.ok(measured.maxVoices>28,'no 28-voice ceiling; actual max '+measured.maxVoices);
assert.ok(measured.energy>0.01,'wave resonances must be audible');
const signatures=new Set(e.sdLog.map(v=>v.slice(0,5).map(x=>x.toFixed(5)).join(':')));
assert.ok(signatures.size>20,'distinct wave shapes must produce distinct sound parameters');
const oldCount=e.sdCount;e.seis(null);assert.equal(e.sz,null,'clear stale seismogram');
assert.equal(e.B.filter(b=>b.sdb).length,0,'clear orphaned seismic voices');
render(e,.3);assert.equal(e.sdCount,oldCount,'no new sound after data loss');
console.log('PASS: '+oldCount+' measured events, '+signatures.size+' unique wave signatures, maximum '+measured.maxVoices+' simultaneous voices, nonzero bass signal, silence without data.');
