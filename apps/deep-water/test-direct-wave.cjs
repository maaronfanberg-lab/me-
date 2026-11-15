// Verify direct audification: the recorded waveform itself, not seismic-triggered oscillators.
const assert=require('node:assert/strict');
const {Eng}=require('./engine.js')();
const SR=48000, stationRate=40, speed=40;
function trace(hz,seconds=10){
 const n=stationRate*seconds, a=new Float32Array(n);
 for(let i=0;i<n;i++)a[i]=.78*Math.sin(2*Math.PI*hz*i/stationRate);
 return a;
}
function read(e,seconds){
 const L=new Float32Array(128),R=new Float32Array(128),record=[];
 for(let k=0;k<Math.ceil(seconds*SR/128);k++){
  e.process(L,R,L.length);
  for(let i=0;i<L.length;i++){
   assert.ok(Number.isFinite(L[i])&&Number.isFinite(R[i]),'finite speaker signal');
   assert.equal(L[i],R[i],'same physical vertical waveform sent to both channels');
   record.push(L[i]);
  }
 }
 return record;
}
const blank=new Eng(SR);blank.direct=true;blank.hum=1;
assert.ok(read(blank,.1).every(x=>x===0),'no recording produces exact silence even if hum on');
const e=new Eng(SR);e.direct=true;e.hum=1;e.speed=speed;
e.seis({data:trace(2),rate:stationRate});
assert.equal(e.szRate,1600,'40x recorded playback rate');
const samples=read(e,.1);
assert.equal(e.B.length,0,'no bubbles, no resonating voices');
assert.equal(e.Q.length,0,'no seismic note events');
assert.ok(Math.max(...samples.map(Math.abs))<1,'safe sample ceiling');
const mid=samples.slice(1500,4200); // skip onset; compare with measured recording at accelerated time
let dot=0,d2=0,s2=0,energy=0;
for(let j=0;j<mid.length;j++){
 const i=j+1500,t=i/SR;
 const expected=Math.sin(2*Math.PI*2*speed*t);
 dot+=mid[j]*expected;d2+=mid[j]**2;s2+=expected**2;energy+=mid[j]**2;
}
const correlation=dot/Math.sqrt(d2*s2);
assert.ok(correlation>.95,'preserve waveform frequency and phase at 40x, correlation '+correlation);
assert.ok(energy>20,'strong measured signal, not silent');
const start=e.szPos;e.speed=80;e.szRate=e.szBaseRate*e.speed;
read(e,.025);
const advance=(e.szPos-start+e.sz.length)%e.sz.length;
const expectedAdvance=Math.ceil(.025*SR/128)*128*(stationRate*80/SR);
assert.ok(Math.abs(advance-expectedAdvance)<1,'80x speed advances at twice the rate; got '+advance+' expected '+expectedAdvance);
e.seis(null);assert.ok(read(e,.1).every(x=>x===0),'data loss silences audio instantly');
const sub=new Eng(SR);sub.direct=true;sub.speed=40;sub.seis({data:trace(.1),rate:stationRate});
const subEnergy=read(sub,.2).reduce((z,x)=>z+x*x,0);
const bass=new Eng(SR);bass.direct=true;bass.speed=40;bass.seis({data:trace(2),rate:stationRate});
const bassEnergy=read(bass,.2).reduce((z,x)=>z+x*x,0);
assert.ok(subEnergy<bassEnergy*.07,'speaker-safe subsonic attenuation');
console.log('PASS direct waveform: time-compressed seismic samples, stereo identity, 40x / 80x rates, correlation '+correlation.toFixed(4)+', silence when unavailable, subsonic protection, no synthesized voices.');
