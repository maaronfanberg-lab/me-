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
  near(p.masterGain,1-0.06*(c.space/100),1e-12,'master gain '+c.space);

  var on=core.appliedTargets(c.space,c.angle,true);
  var off=core.appliedTargets(c.space,c.angle,false);
  near(on.delaySeconds,p.itd,1e-12,'applied delay');
  near(on.cutoffHz,p.cutoff,1e-12,'applied cutoff');
  near(on.farGain,p.farGain,1e-12,'applied far gain');
  near(on.directGain,p.directGain,1e-12,'applied direct gain');
  near(on.masterGain,p.masterGain,1e-12,'applied master gain');
  assert.strictEqual(off.farGain,0,'bypass far path must be zero');
  assert.strictEqual(off.directGain,1,'bypass direct path must be unity');
  assert.strictEqual(off.masterGain,1,'bypass master must be unity');

  var r=core.readouts(c.space,c.angle,true);
  assert.strictEqual(r.spaceText,Math.round(c.space)+'%');
  assert.strictEqual(r.angleText,Math.round(c.angle)+'°');
  assert.strictEqual(r.delayText,(p.itd*1000).toFixed(2)+' ms');
  assert.strictEqual(r.cutoffText,Math.round(p.cutoff)+' Hz');
  assert.strictEqual(r.farText,Math.round(p.farGain*100)+'%');
});

var clamped=core.calculate(150,5);
assert.strictEqual(clamped.wet,1);
assert.strictEqual(clamped.deg,20);
var clamped2=core.calculate(-20,100);
assert.strictEqual(clamped2.wet,0);
assert.strictEqual(clamped2.deg,70);

var wide=core.calculate(72,57);
assert.strictEqual(core.readouts(72,57,true).delayText,(wide.itd*1000).toFixed(2)+' ms');
assert.strictEqual(core.readouts(72,57,true).cutoffText,Math.round(wide.cutoff)+' Hz');
assert.strictEqual(core.readouts(72,57,true).farText,Math.round(wide.farGain*100)+'%');

console.log('Pocket Spatial slider mapping tests passed for '+cases.length+' calibration points.');
