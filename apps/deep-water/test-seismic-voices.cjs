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
// 2026-11-16 (Alex: 'not the constant static'): only prominent half-waves sing (peak >= 1.25x the running average, or
// one every 0.5 s), so every voice still comes from a measured half-wave but the steady background no longer hisses.
assert.ok((e.sdCount||0)>30,'prominent measured half-waves must be represented; count '+e.sdCount);
assert.ok(measured.maxVoices>3,'overlapping voices allowed; actual max '+measured.maxVoices);
assert.ok(measured.energy>0.01,'wave resonances must be audible');
const signatures=new Set(e.sdLog.map(v=>v.slice(0,5).map(x=>x.toFixed(5)).join(':')));
assert.ok(signatures.size>=Math.min(20,Math.floor(e.sdLog.length*.25)),'distinct wave shapes must produce distinct sound parameters; '+signatures.size+' of '+e.sdLog.length);
// steady background (constant-amplitude 0.3 Hz wave, like a microseism) must stay sparse: no dense hiss
{const rate=40,n=rate*60,a=new Float32Array(n);for(let i=0;i<n;i++)a[i]=.3*Math.sin(2*Math.PI*.3*i/rate+.3*Math.sin(i/57));
 const q=new Eng(SR);q.hum=0;q.szLvl=0;q.seis({data:a,drive:a,rate:rate*20});render(q,2);
 assert.ok((q.sdCount||0)/2<=4,'steady background must not form a dense stream of voices; per second '+(q.sdCount||0)/2);}
// pitch is proportional to the measured wave frequency (intervals preserved): a 2x faster wave sounds an octave higher
{const mk=hz=>{const rate=40,n=rate*30,a=new Float32Array(n);for(let i=0;i<n;i++)a[i]=Math.sin(2*Math.PI*hz*i/rate)*(i%200<100?1:.2);return a;};
 const f=hz=>{const q=new Eng(SR);q.hum=0;q.sdLog=[];const a=mk(hz);q.seis({data:a,drive:a,rate:800});render(q,1);const v=q.sdLog.map(x=>x[0]).sort((x,y)=>x-y);return v[v.length>>1];};
 const r=f(2)/f(1);assert.ok(Math.abs(r-2)<.15,'octave for twice the frequency; ratio '+r.toFixed(3));}
const oldCount=e.sdCount;e.seis(null);assert.equal(e.sz,null,'clear stale seismogram');
assert.equal(e.B.filter(b=>b.sdb).length,0,'clear orphaned seismic voices');
render(e,.3);assert.equal(e.sdCount,oldCount,'no new sound after data loss');
console.log('PASS: '+oldCount+' measured events, '+signatures.size+' unique wave signatures, maximum '+measured.maxVoices+' simultaneous voices, nonzero bass signal, silence without data.');
