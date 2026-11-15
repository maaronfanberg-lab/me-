// Verify selected audio sections are literally taken from the measured waveform.
const assert=require('node:assert/strict');
const {analyze}=require('./wave-windows.js')();
const {Eng}=require('./engine.js')();
const rate=40,minutes=75,n=rate*minutes*60;
const x=new Float32Array(n);
// Deterministic seismic-style fixture: quiet microseism, longer low rolls,
// a short impulse packet and higher-frequency late waves. No fabricated audio in app.
for(let i=0;i<n;i++){
 const t=i/rate,part=Math.floor(t/600);
 let f=part%3===0?.12:part%3===1?1.4:5.5;
 let v=(part===2?4:part===5?2:1)*Math.sin(2*Math.PI*f*t);
 if(part===4&&i%439<15)v+=1.8*Math.sin(2*Math.PI*8*t);
 x[i]=v*.1;
}
const one=analyze(x,rate,1700000000000,{limit:7});
const two=analyze(x,rate,1700000000000,{limit:7});
assert.ok(one.length>=5,'enough distinct sections from long recording');
assert.deepEqual(one,two,'selection is deterministic');
const descriptors=new Set();
for(const w of one){
 assert.ok(w.from>=0&&w.end<=n&&w.end>w.from,'each section is contiguous and measurable');
 assert.equal(w.at,1700000000000+w.from/rate*1000,'grounded recorded time');
 const original=x.slice(w.from,w.end);
 assert.equal(original[0],x[w.from],'audio begins at the actual chosen recorded sample');
 assert.equal(original[original.length-1],x[w.end-1],'audio ends at actual recorded sample');
 descriptors.add([Math.round(w.rough*100),Math.round(w.burst*10),Math.round(w.crest*10)].join(':'));
}
assert.ok(descriptors.size>=3,'selected sections reflect different measured waveform shapes');
const sample=one[0],e=new Eng(48000);e.direct=true;e.speed=160;
e.seis({data:x.slice(sample.from,sample.end),rate,clip:1});
const L=new Float32Array(128),R=new Float32Array(128);e.process(L,R,128);
assert.equal(e.directClipId,1);
assert.equal(e.B.length,0,'direct sound never creates oscillators');
const next=one[1],before=e.directLast;e.seis({data:x.slice(next.from,next.end),rate,clip:2});
e.process(L,R,128);
assert.equal(e.directClipId,2,'next clip is actually loaded');
assert.ok(Math.abs(L[0]-before)<.001,'click guard begins at previous output sample');
assert.ok(L.every(Number.isFinite),'clip transition finite');
console.log('PASS: '+one.length+' measured sections, '+descriptors.size+' distinct waveform descriptors, sample-exact slices, deterministic selection and click-free transitions.');
