'use strict';
var assert=require('assert');
var core=require('../apps/pocket-spatial-core.js');

function near(actual,expected,tol,label){
  assert(Math.abs(actual-expected)<=tol,label+': expected '+expected+', got '+actual);
}

function woodworthMs(deg){
  var theta=deg*Math.PI/180;
  return ((0.0875/343)*(theta+Math.sin(theta)))*1000;
}

var cases=[
  {space:0,angle:20},
  {space:48,angle:38},
  {space:72,angle:57},
  {space:92,angle:68},
  {space:100,angle:70}
];

cases.forEach(function(c){
  var p=core.calculate(c.space,c.angle);
  near(p.wet,c.space/100,1e-12,'wet '+c.space);
  near(p.deg,c.angle,1e-12,'angle '+c.angle);
  near(p.itd*1000,woodworthMs(c.angle),1e-9,'ITD '+c.angle);
  near(p.cutoff,7000-3800*(c.space/100),1e-9,'cutoff '+c.space);
  near(p.farGain,0.22*(c.space/100),1e-12,'far gain '+c.space);
  near(p.directGain,1-0.18*(c.space/100),1e-12,'direct gain '+c.space);
  near(p.baseMasterGain,1-0.06*(c.space/100),1e-12,'base master gain '+c.space);

  var on=core.appliedTargets(c.space,c.angle,0,true);
  var off=core.appliedTargets(c.space,c.angle,0,false);
  near(on.delaySeconds,p.itd,1e-12,'applied delay');
  near(on.cutoffHz,p.cutoff,1e-12,'applied cutoff');
  near(on.farGain,p.farGain,1e-12,'applied far gain');
  near(on.directGain,p.directGain,1e-12,'applied direct gain');
  near(on.masterGain,p.baseMasterGain,1e-12,'baseline master gain');
  assert.strictEqual(on.refl1Gain,0,'depth zero reflection 1 must be silent');
  assert.strictEqual(on.refl2Gain,0,'depth zero reflection 2 must be silent');
  assert.strictEqual(off.farGain,0,'bypass far path must be zero');
  assert.strictEqual(off.directGain,1,'bypass direct path must be unity');
  assert.strictEqual(off.refl1Gain,0,'bypass reflection 1 must be zero');
  assert.strictEqual(off.refl2Gain,0,'bypass reflection 2 must be zero');
  assert.strictEqual(off.masterGain,1,'bypass master must be unity');

  var r=core.readouts(c.space,c.angle,0,true);
  assert.strictEqual(r.spaceText,Math.round(c.space)+'%');
  assert.strictEqual(r.angleText,Math.round(c.angle)+'°');
  assert.strictEqual(r.delayText,(p.itd*1000).toFixed(2)+' ms');
  assert.strictEqual(r.cutoffText,Math.round(p.cutoff)+' Hz');
  assert.strictEqual(r.farText,Math.round(p.farGain*100)+'%');
});

var depthCases=[0,25,50,75,100];
var previous1=-1;
var previous2=-1;
depthCases.forEach(function(depth){
  var d=core.calculateDepth(depth);
  near(d.depth,depth/100,1e-12,'depth '+depth);
  assert.strictEqual(d.refl1DelayL,0.011);
  assert.strictEqual(d.refl1DelayR,0.013);
  assert.strictEqual(d.refl2DelayL,0.021);
  assert.strictEqual(d.refl2DelayR,0.024);
  assert.strictEqual(d.reflCutoff,2600);
  assert.strictEqual(d.reflQ,0.5);
  near(d.refl1Gain,0.14*(depth/100),1e-12,'reflection 1 gain '+depth);
  near(d.refl2Gain,0.07*(depth/100),1e-12,'reflection 2 gain '+depth);
  assert(d.refl1Gain>=previous1,'reflection 1 gain must be monotonic');
  assert(d.refl2Gain>=previous2,'reflection 2 gain must be monotonic');
  previous1=d.refl1Gain;
  previous2=d.refl2Gain;

  var t=core.appliedTargets(72,57,depth,true);
  near(t.refl1Gain,d.refl1Gain,1e-12,'applied reflection 1 gain');
  near(t.refl2Gain,d.refl2Gain,1e-12,'applied reflection 2 gain');
  near(t.refl1DelayL,d.refl1DelayL,1e-12,'reflection delay L1');
  near(t.refl1DelayR,d.refl1DelayR,1e-12,'reflection delay R1');
  near(t.refl2DelayL,d.refl2DelayL,1e-12,'reflection delay L2');
  near(t.refl2DelayR,d.refl2DelayR,1e-12,'reflection delay R2');
  near(t.reflCutoff,d.reflCutoff,1e-12,'reflection cutoff');
  assert(t.nominalSum*t.masterGain<=1.000000000001,'nominal summed path budget must remain <= 1');

  var r=core.readouts(72,57,depth,true);
  assert.strictEqual(r.depthText,depth+'%');
  assert.strictEqual(r.reflectionTimesText,'11/13 · 21/24 ms');
  assert.strictEqual(r.reflectionGainText,(d.refl1Gain*100).toFixed(1)+'% / '+(d.refl2Gain*100).toFixed(1)+'%');
  assert.strictEqual(r.reflectionCutoffText,'2600 Hz');
});

var d0=core.calculateDepth(0);
var d100=core.calculateDepth(100);
assert.strictEqual(d0.refl1Gain,0);
assert.strictEqual(d0.refl2Gain,0);
assert.strictEqual(d100.refl1Gain,0.14);
assert.strictEqual(d100.refl2Gain,0.07);

var full=core.appliedTargets(100,70,100,true);
assert(full.masterGain<core.calculate(100,70).baseMasterGain,'depth headroom must reduce output trim when needed');
assert(full.nominalSum*full.masterGain<=1.000000000001,'full settings must satisfy nominal headroom budget');

var clamped=core.calculate(150,5);
assert.strictEqual(clamped.wet,1);
assert.strictEqual(clamped.deg,20);
var clamped2=core.calculate(-20,100);
assert.strictEqual(clamped2.wet,0);
assert.strictEqual(clamped2.deg,70);
assert.strictEqual(core.calculateDepth(200).depth,1);
assert.strictEqual(core.calculateDepth(-50).depth,0);

var wide=core.calculate(72,57);
assert.strictEqual(core.readouts(72,57,0,true).delayText,(wide.itd*1000).toFixed(2)+' ms');
assert.strictEqual(core.readouts(72,57,0,true).cutoffText,Math.round(wide.cutoff)+' Hz');
assert.strictEqual(core.readouts(72,57,0,true).farText,Math.round(wide.farGain*100)+'%');

console.log('Pocket Spatial slider + Depth mapping tests passed for '+cases.length+' spatial and '+depthCases.length+' depth calibration points.');
