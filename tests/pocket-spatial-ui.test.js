'use strict';
var assert=require('assert');
var fs=require('fs');
var vm=require('vm');
var core=require('../apps/pocket-spatial-core.js');

function near(actual,expected,tol,label){
  assert(Math.abs(actual-expected)<=tol,label+': expected '+expected+', got '+actual);
}

function Param(value){
  this.value=value||0;
}
Param.prototype.cancelScheduledValues=function(){};
Param.prototype.setTargetAtTime=function(value){this.value=value;};

function Node(type){
  this.type=type;
  this.connections=[];
}
Node.prototype.connect=function(target,output,input){
  this.connections.push({target:target,output:output,input:input});
  return target;
};

function GainNode(){Node.call(this,'gain');this.gain=new Param(1);}
GainNode.prototype=Object.create(Node.prototype);
function DelayNode(){Node.call(this,'delay');this.delayTime=new Param(0);}
DelayNode.prototype=Object.create(Node.prototype);
function FilterNode(){Node.call(this,'filter');this.frequency=new Param(350);this.Q=new Param(1);this.type='lowpass';}
FilterNode.prototype=Object.create(Node.prototype);

function FakeAudioContext(){
  this.currentTime=0;
  this.state='running';
  this.destination=new Node('destination');
  this.gains=[];
  this.delays=[];
  this.filters=[];
  FakeAudioContext.last=this;
}
FakeAudioContext.prototype.createMediaElementSource=function(){return new Node('media');};
FakeAudioContext.prototype.createChannelSplitter=function(){return new Node('splitter');};
FakeAudioContext.prototype.createChannelMerger=function(){return new Node('merger');};
FakeAudioContext.prototype.createGain=function(){var n=new GainNode();this.gains.push(n);return n;};
FakeAudioContext.prototype.createDelay=function(){var n=new DelayNode();this.delays.push(n);return n;};
FakeAudioContext.prototype.createBiquadFilter=function(){var n=new FilterNode();this.filters.push(n);return n;};
FakeAudioContext.prototype.resume=function(){this.state='running';return Promise.resolve();};

function Element(id,value){
  this.id=id;
  this.value=value==null?'':String(value);
  this.textContent='';
  this.className='';
  this.src='';
  this.files=[];
  this.listeners={};
  this.attrs={};
}
Element.prototype.addEventListener=function(type,fn){this.listeners[type]=fn;};
Element.prototype.dispatch=function(type){if(this.listeners[type]){this.listeners[type].call(this,{type:type});}};
Element.prototype.getAttribute=function(name){return this.attrs[name];};

var ids={};
function element(id,value){var e=new Element(id,value);ids[id]=e;return e;}

element('audio');
element('file');
element('spatial');
element('space',72);
element('angle',57);
element('depth',45);
element('badge');
element('track');
element('status');
element('spaceRead');
element('angleRead');
element('depthRead');
element('engine');
element('delay');
element('cutoff');
element('far');
element('direct');
element('reflTimes');
element('reflGain');
element('reflCutoff');
element('master');

var document={
  hidden:false,
  listeners:{},
  getElementById:function(id){return ids[id];},
  querySelectorAll:function(){return [];},
  addEventListener:function(type,fn){this.listeners[type]=fn;}
};

var context={
  window:{AudioContext:FakeAudioContext,PocketSpatialCore:core},
  document:document,
  URL:{createObjectURL:function(){return 'blob:test';},revokeObjectURL:function(){}},
  console:console,
  Math:Math,
  Promise:Promise
};
context.window.webkitAudioContext=FakeAudioContext;

var html=fs.readFileSync('apps/pocket-spatial.html','utf8');
var matches=html.match(/<script>([\s\S]*?)<\/script>/i);
assert(matches,'inline Pocket Spatial script not found');
vm.runInNewContext(matches[1],context,{filename:'pocket-spatial-inline.js'});

// Turning Spatial on must build the graph and apply the displayed defaults.
ids.spatial.dispatch('click');
var audio=FakeAudioContext.last;
assert(audio,'AudioContext was not created by Spatial button');
assert.strictEqual(audio.gains.length,9,'expected master + 4 localization gains + 4 reflection gains');
assert.strictEqual(audio.delays.length,6,'expected 2 ITD + 4 reflection delays');
assert.strictEqual(audio.filters.length,6,'expected 2 head-shadow + 4 reflection filters');

function assertTargets(space,angle,depth,label){
  var t=core.appliedTargets(space,angle,depth,true);
  var r=core.readouts(space,angle,depth,true);

  near(audio.delays[0].delayTime.value,t.delaySeconds,1e-12,label+' ITD L');
  near(audio.delays[1].delayTime.value,t.delaySeconds,1e-12,label+' ITD R');
  near(audio.filters[0].frequency.value,t.cutoffHz,1e-9,label+' head shadow L');
  near(audio.filters[1].frequency.value,t.cutoffHz,1e-9,label+' head shadow R');
  near(audio.gains[1].gain.value,t.directGain,1e-12,label+' direct L');
  near(audio.gains[2].gain.value,t.directGain,1e-12,label+' direct R');
  near(audio.gains[3].gain.value,t.farGain,1e-12,label+' cross L');
  near(audio.gains[4].gain.value,t.farGain,1e-12,label+' cross R');

  near(audio.delays[2].delayTime.value,t.refl1DelayL,1e-12,label+' reflection L1 time');
  near(audio.delays[3].delayTime.value,t.refl1DelayR,1e-12,label+' reflection R1 time');
  near(audio.delays[4].delayTime.value,t.refl2DelayL,1e-12,label+' reflection L2 time');
  near(audio.delays[5].delayTime.value,t.refl2DelayR,1e-12,label+' reflection R2 time');
  for(var i=2;i<6;i++){
    near(audio.filters[i].frequency.value,t.reflCutoff,1e-9,label+' reflection cutoff '+i);
    near(audio.filters[i].Q.value,t.reflQ,1e-12,label+' reflection Q '+i);
  }
  near(audio.gains[5].gain.value,t.refl1Gain,1e-12,label+' reflection L1 gain');
  near(audio.gains[6].gain.value,t.refl1Gain,1e-12,label+' reflection R1 gain');
  near(audio.gains[7].gain.value,t.refl2Gain,1e-12,label+' reflection L2 gain');
  near(audio.gains[8].gain.value,t.refl2Gain,1e-12,label+' reflection R2 gain');
  near(audio.gains[0].gain.value,t.masterGain,1e-12,label+' master gain');

  assert.strictEqual(ids.delay.textContent,r.delayText,label+' delay readout');
  assert.strictEqual(ids.cutoff.textContent,r.cutoffText,label+' cutoff readout');
  assert.strictEqual(ids.far.textContent,r.farText,label+' far readout');
  assert.strictEqual(ids.direct.textContent,r.directText,label+' direct readout');
  assert.strictEqual(ids.reflTimes.textContent,r.reflectionTimesText,label+' reflection-time readout');
  assert.strictEqual(ids.reflGain.textContent,r.reflectionGainText,label+' reflection-gain readout');
  assert.strictEqual(ids.reflCutoff.textContent,r.reflectionCutoffText,label+' reflection-cutoff readout');
  assert.strictEqual(ids.master.textContent,r.masterText,label+' master readout');
}

assertTargets(72,57,45,'default');

// Depth slider must control only reflection strength/headroom, not reflection times.
ids.depth.value='100';
ids.depth.dispatch('input');
assertTargets(72,57,100,'depth 100');
near(audio.gains[5].gain.value,0.14,1e-12,'Depth 100 reflection 1');
near(audio.gains[7].gain.value,0.07,1e-12,'Depth 100 reflection 2');

ids.depth.value='0';
ids.depth.dispatch('input');
assertTargets(72,57,0,'depth 0');
assert.strictEqual(audio.gains[5].gain.value,0,'Depth 0 reflection 1 silent');
assert.strictEqual(audio.gains[7].gain.value,0,'Depth 0 reflection 2 silent');

// Angle and Spatial Amount must drive the advertised localization params.
ids.depth.value='70';ids.depth.dispatch('input');
ids.angle.value='70';ids.angle.dispatch('input');
ids.space.value='100';ids.space.dispatch('input');
assertTargets(100,70,70,'max localization');

// Global bypass must make every added path silent and direct/output unity.
ids.spatial.dispatch('click');
assert.strictEqual(audio.gains[1].gain.value,1,'bypass direct L');
assert.strictEqual(audio.gains[2].gain.value,1,'bypass direct R');
assert.strictEqual(audio.gains[3].gain.value,0,'bypass cross L');
assert.strictEqual(audio.gains[4].gain.value,0,'bypass cross R');
assert.strictEqual(audio.gains[5].gain.value,0,'bypass reflection L1');
assert.strictEqual(audio.gains[6].gain.value,0,'bypass reflection R1');
assert.strictEqual(audio.gains[7].gain.value,0,'bypass reflection L2');
assert.strictEqual(audio.gains[8].gain.value,0,'bypass reflection R2');
assert.strictEqual(audio.gains[0].gain.value,1,'bypass master');

console.log('Pocket Spatial UI/Web Audio integration test passed: slider events drive the exact displayed DSP targets.');
