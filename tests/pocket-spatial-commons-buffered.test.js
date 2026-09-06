'use strict';
var assert=require('assert');
var fs=require('fs');
var vm=require('vm');
var core=require('../apps/pocket-spatial-core.js');

function Param(value){this.value=value||0;}
Param.prototype.cancelScheduledValues=function(){};
Param.prototype.setTargetAtTime=function(value){this.value=value;};

function Node(type){this.type=type;this.connections=[];}
Node.prototype.connect=function(target,output,input){this.connections.push({target:target,output:output,input:input});return target;};
Node.prototype.disconnect=function(){};

function Gain(){Node.call(this,'gain');this.gain=new Param(1);}
Gain.prototype=Object.create(Node.prototype);
function Delay(){Node.call(this,'delay');this.delayTime=new Param(0);}
Delay.prototype=Object.create(Node.prototype);
function Filter(){Node.call(this,'filter');this.frequency=new Param(350);this.Q=new Param(1);this.type='lowpass';}
Filter.prototype=Object.create(Node.prototype);
function BufferSource(){Node.call(this,'bufferSource');this.buffer=null;this.started=false;this.onended=null;}
BufferSource.prototype=Object.create(Node.prototype);
BufferSource.prototype.start=function(){this.started=true;};
BufferSource.prototype.stop=function(){};

function FakeAudioContext(){
  this.currentTime=0;
  this.state='running';
  this.destination=new Node('destination');
  this.gains=[];this.delays=[];this.filters=[];this.sources=[];
  FakeAudioContext.last=this;
}
FakeAudioContext.prototype.createChannelSplitter=function(){return new Node('splitter');};
FakeAudioContext.prototype.createChannelMerger=function(){return new Node('merger');};
FakeAudioContext.prototype.createGain=function(){var n=new Gain();this.gains.push(n);return n;};
FakeAudioContext.prototype.createDelay=function(){var n=new Delay();this.delays.push(n);return n;};
FakeAudioContext.prototype.createBiquadFilter=function(){var n=new Filter();this.filters.push(n);return n;};
FakeAudioContext.prototype.createBufferSource=function(){var n=new BufferSource();this.sources.push(n);return n;};
FakeAudioContext.prototype.resume=function(){this.state='running';};
FakeAudioContext.prototype.decodeAudioData=function(bytes,success){
  assert(bytes&&bytes.byteLength===4096,'decodeAudioData receives fetched bytes');
  success({duration:5.7,numberOfChannels:2});
};

function Element(id,value){
  this.id=id;this.value=value==null?'':String(value);this.textContent='';this.className='';this.disabled=false;this.listeners={};
}
Element.prototype.addEventListener=function(type,fn){this.listeners[type]=fn;};
Element.prototype.getAttribute=function(){return null;};

var ids={};
function add(id,value){var e=new Element(id,value);ids[id]=e;return e;}
add('space',72);add('angle',57);add('depth',45);add('spaceRead');add('angleRead');add('depthRead');
add('delay');add('cutoff');add('far');add('direct');add('reflTimes');add('reflGain');add('reflCutoff');add('master');
add('spatial');add('badge');add('engine');add('audio');add('file');add('track');add('status');
ids.spatial.textContent='TURN SPATIAL ON';ids.badge.textContent='Spatial off';ids.badge.className='badge';

var document={
  readyState:'complete',
  getElementById:function(id){return ids[id]||null;},
  querySelectorAll:function(){return [];},
  addEventListener:function(){}
};

function FakeXHR(){this.readyState=0;this.status=0;this.response=null;this.timeout=0;}
FakeXHR.prototype.open=function(method,url,async){assert.strictEqual(method,'GET');assert(/^https:\/\//.test(url));assert.strictEqual(async,true);this.readyState=1;};
FakeXHR.prototype.send=function(){this.status=200;this.response=new ArrayBuffer(4096);this.readyState=4;this.onload();};
FakeXHR.prototype.abort=function(){this.readyState=4;};

var sandbox={
  PocketSpatialCore:core,
  AudioContext:FakeAudioContext,
  webkitAudioContext:FakeAudioContext,
  XMLHttpRequest:FakeXHR,
  document:document,
  console:console,
  Math:Math,
  Number:Number,
  String:String,
  ArrayBuffer:ArrayBuffer,
  setTimeout:setTimeout,
  clearTimeout:clearTimeout
};

var source=fs.readFileSync('apps/pocket-spatial-commons-buffered.js','utf8');
vm.runInNewContext(source,sandbox,{filename:'pocket-spatial-commons-buffered.js'});
assert(sandbox.PocketSpatialBufferedCommons,'buffered engine exported');
assert.strictEqual(sandbox.PocketSpatialBufferedCommons.limits.compressedBytes,6291456);
assert.strictEqual(sandbox.PocketSpatialBufferedCommons.limits.durationSeconds,180);
assert.deepStrictEqual(JSON.parse(JSON.stringify(sandbox.PocketSpatialBufferedCommons.preset)),{space:86,angle:64,depth:58});

var control=new Element('control');
var diagnostic=new Element('diagnostic');
var track={pageid:9,title:'File:Immersive test.mp3',artist:'Test Artist',audio:'https://upload.wikimedia.org/test.mp3'};
sandbox.PocketSpatialBufferedCommons.toggle(track,control,diagnostic);

assert.strictEqual(ids.space.value,'86');
assert.strictEqual(ids.angle.value,'64');
assert.strictEqual(ids.depth.value,'58');
assert.strictEqual(control.textContent,'STOP IMMERSIVE PLAYBACK');
assert.strictEqual(control.disabled,false);
assert.strictEqual(diagnostic.className,'status good');
assert(diagnostic.textContent.indexOf('Buffered immersive playback is live')!==-1);
assert.strictEqual(ids.badge.textContent,'Buffered immersive');
assert.strictEqual(ids.spatial.disabled,true);
assert.strictEqual(ids.engine.textContent,'buffered');
assert.strictEqual(ids.track.textContent,'Commons buffered · Immersive test.mp3 · Test Artist');

var audio=FakeAudioContext.last;
assert(audio,'AudioContext created');
assert.strictEqual(audio.gains.length,9,'master + localization + reflections');
assert.strictEqual(audio.delays.length,6,'ITD + four reflections');
assert.strictEqual(audio.filters.length,6,'head-shadow + reflection filters');
assert.strictEqual(audio.sources.length,1,'one AudioBufferSourceNode');
assert.strictEqual(audio.sources[0].started,true,'buffer source started');

var target=core.appliedTargets(86,64,58,true);
function near(actual,expected,label){assert(Math.abs(actual-expected)<1e-12,label+': expected '+expected+', got '+actual);}
near(audio.delays[0].delayTime.value,target.delaySeconds,'immersive ITD L');
near(audio.delays[1].delayTime.value,target.delaySeconds,'immersive ITD R');
near(audio.gains[1].gain.value,target.directGain,'immersive direct L');
near(audio.gains[3].gain.value,target.farGain,'immersive cross L');
near(audio.gains[5].gain.value,target.refl1Gain,'immersive reflection 1');
near(audio.gains[7].gain.value,target.refl2Gain,'immersive reflection 2');
near(audio.gains[0].gain.value,target.masterGain,'immersive headroom');

sandbox.PocketSpatialBufferedCommons.stop();
assert.strictEqual(ids.spatial.disabled,false);
assert.strictEqual(control.textContent,'BUFFER + PLAY IMMERSIVE');

console.log('Pocket Spatial buffered Commons immersive playback tests passed.');
