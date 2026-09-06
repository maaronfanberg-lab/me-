const assert=require('assert');
const fs=require('fs');
const vm=require('vm');

const source=fs.readFileSync('apps/pocket-spatial-buffer-probe.js','utf8');

function sliceFunction(name,nextName){
  const start=source.indexOf('function '+name+'(');
  const end=source.indexOf('\nfunction '+nextName+'(',start);
  assert(start>=0,'missing function '+name);
  assert(end>start,'missing boundary after '+name);
  return source.slice(start,end);
}

const pureSnippet="var API='https://commons.wikimedia.org/w/api.php';\nvar TEST_TITLE='File:Music loop 168bpm (Still frivolous).ogg';\n"+
  sliceFunction('plain','metadataValue')+'\n'+
  sliceFunction('metadataValue','licenseAllowsProbe')+'\n'+
  sliceFunction('licenseAllowsProbe','isHTTPS')+'\n'+
  sliceFunction('isHTTPS','looksLikeMP3')+'\n'+
  sliceFunction('looksLikeMP3','selectMP3')+'\n'+
  sliceFunction('selectMP3','buildMetadataURL')+'\n'+
  sliceFunction('buildMetadataURL','jsonp')+'\n'+
  'this.api={licenseAllowsProbe:licenseAllowsProbe,selectMP3:selectMP3,buildMetadataURL:buildMetadataURL};';

const pureSandbox={encodeURIComponent:encodeURIComponent};
vm.runInNewContext(pureSnippet,pureSandbox,{filename:'buffer-probe-pure.js'});
const api=pureSandbox.api;

function info(shortName,url,usage,derivatives){
  return {
    url:'https://upload.wikimedia.org/original.ogg',
    mime:'audio/ogg',
    derivatives:derivatives||[],
    extmetadata:{
      LicenseShortName:{value:shortName||''},
      LicenseUrl:{value:url||''},
      UsageTerms:{value:usage||''}
    }
  };
}

assert.strictEqual(api.licenseAllowsProbe(info('CC BY-SA 4.0','https://creativecommons.org/licenses/by-sa/4.0/','')),true);
assert.strictEqual(api.licenseAllowsProbe(info('CC BY-ND 4.0','https://creativecommons.org/licenses/by-nd/4.0/','No derivatives')),false);
assert.strictEqual(api.licenseAllowsProbe(info('CC BY-NC 4.0','https://creativecommons.org/licenses/by-nc/4.0/','NonCommercial')),false);
assert.strictEqual(api.licenseAllowsProbe({extmetadata:{}}),false);

const mp3=api.selectMP3(info('CC BY-SA 4.0','','',[
  {src:'https://upload.wikimedia.org/transcoded/test.mp3',type:'audio/mpeg',transcodekey:'mp3'}
]));
assert.strictEqual(mp3,'https://upload.wikimedia.org/transcoded/test.mp3');

const metadataURL=api.buildMetadataURL('cb');
assert(metadataURL.indexOf('commons.wikimedia.org/w/api.php')!==-1);
assert(metadataURL.indexOf('Music%20loop%20168bpm')!==-1);
assert(metadataURL.indexOf('derivatives')!==-1);
assert(metadataURL.indexOf('extmetadata')!==-1);
assert(metadataURL.indexOf('callback=cb')!==-1);
assert(metadataURL.indexOf('client_id')===-1);
assert(metadataURL.indexOf('token')===-1);

let responseBytes=4096;
let decodeShouldFail=false;
let decodeCalls=0;

function FakeXHR(){
  this.status=0;
  this.response=null;
  this.readyState=0;
  this.timeout=0;
}
FakeXHR.prototype.open=function(method,url,async){
  assert.strictEqual(method,'GET');
  assert(/^https:\/\//.test(url));
  assert.strictEqual(async,true);
  this.readyState=1;
};
FakeXHR.prototype.send=function(){
  this.status=200;
  this.response=new ArrayBuffer(responseBytes);
  this.readyState=4;
  this.onload();
};
FakeXHR.prototype.abort=function(){this.readyState=4;};

function FakeAnalyser(){
  this.fftSize=256;
  this.smoothingTimeConstant=0;
}
FakeAnalyser.prototype.connect=function(){};
FakeAnalyser.prototype.getByteTimeDomainData=function(data){
  for(let i=0;i<data.length;i+=1)data[i]=(i%2)?144:128;
};

function FakeGain(){this.gain={value:1};}
FakeGain.prototype.connect=function(){};

function FakeBufferSource(){this.buffer=null;this.started=false;}
FakeBufferSource.prototype.connect=function(){};
FakeBufferSource.prototype.start=function(){this.started=true;};
FakeBufferSource.prototype.stop=function(){};

function FakeAudioContext(){
  this.state='running';
  this.destination={};
}
FakeAudioContext.prototype.createAnalyser=function(){return new FakeAnalyser();};
FakeAudioContext.prototype.createGain=function(){return new FakeGain();};
FakeAudioContext.prototype.createBufferSource=function(){return new FakeBufferSource();};
FakeAudioContext.prototype.resume=function(){};
FakeAudioContext.prototype.close=function(){};
FakeAudioContext.prototype.decodeAudioData=function(bytes,success,failure){
  decodeCalls+=1;
  assert(bytes&&bytes.byteLength===responseBytes);
  if(decodeShouldFail){failure(new Error('decode failed'));return;}
  success({duration:5.7});
};

const runtimeSnippet="var root=this;\nvar MAX_BYTES=1048576;\n"+
  sliceFunction('probeBufferedPCM','setStatus')+'\n'+
  'this.probe=probeBufferedPCM;';

const runtimeSandbox={
  AudioContext:FakeAudioContext,
  XMLHttpRequest:FakeXHR,
  ArrayBuffer:ArrayBuffer,
  Uint8Array:Uint8Array,
  setInterval:function(fn){for(let i=0;i<15;i+=1)fn();return 1;},
  clearInterval:function(){}
};
vm.runInNewContext(runtimeSnippet,runtimeSandbox,{filename:'buffer-probe-runtime.js'});

let result=null;
runtimeSandbox.probe('https://upload.wikimedia.org/test.mp3',function(value){result=value;});
assert(result,'buffer probe should return a result');
assert.strictEqual(result.supported,true);
assert.strictEqual(result.reason,'buffered_pcm_available');
assert.strictEqual(result.received_bytes,4096);
assert.strictEqual(result.decoded_duration,5.7);
assert.strictEqual(result.max_analyser_deviation,16);
assert.strictEqual(decodeCalls,1);

responseBytes=1048577;
result=null;
runtimeSandbox.probe('https://upload.wikimedia.org/too-large.mp3',function(value){result=value;});
assert(result,'oversize probe should return a result');
assert.strictEqual(result.supported,false);
assert.strictEqual(result.reason,'buffer_probe_too_large');
assert.strictEqual(decodeCalls,1,'oversize compressed input must be rejected before decodeAudioData');

responseBytes=2048;
decodeShouldFail=true;
result=null;
runtimeSandbox.probe('https://upload.wikimedia.org/decode-fail.mp3',function(value){result=value;});
assert(result,'decode failure should return a result');
assert.strictEqual(result.supported,false);
assert.strictEqual(result.reason,'decode_audio_data_failed');
assert.strictEqual(decodeCalls,2);

console.log('Pocket Spatial buffered PCM compatibility-probe tests passed.');
