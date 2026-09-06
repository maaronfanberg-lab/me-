const assert=require('assert');
const fs=require('fs');
const vm=require('vm');

const source=fs.readFileSync('apps/pocket-spatial-commons.js','utf8');

function sliceFunction(name,nextName){
  const start=source.indexOf('function '+name+'(');
  const end=source.indexOf('\nfunction '+nextName+'(',start);
  assert(start>=0,'missing function '+name);
  assert(end>start,'missing boundary after '+name);
  return source.slice(start,end);
}

const snippet="var API='https://commons.wikimedia.org/w/api.php';\nvar CATEGORY='Category:Audio files of music';\n"+
  sliceFunction('buildCatalogURL','jsonp')+'\n'+
  sliceFunction('plain','metadataValue')+'\n'+
  sliceFunction('metadataValue','licenseAllowsSpatial')+'\n'+
  sliceFunction('licenseAllowsSpatial','isHTTPS')+'\n'+
  sliceFunction('isHTTPS','looksLikeMP3')+'\n'+
  sliceFunction('looksLikeMP3','selectMP3')+'\n'+
  sliceFunction('selectMP3','pageURL')+'\n'+
  'this.api={buildCatalogURL:buildCatalogURL,licenseAllowsSpatial:licenseAllowsSpatial,selectMP3:selectMP3};';

const sandbox={encodeURIComponent:encodeURIComponent};
vm.runInNewContext(snippet,sandbox,{filename:'commons-pure-extract.js'});
const api=sandbox.api;

function info(shortName,url,usage){
  return {extmetadata:{
    LicenseShortName:{value:shortName||''},
    LicenseUrl:{value:url||''},
    UsageTerms:{value:usage||''}
  }};
}

assert.strictEqual(api.licenseAllowsSpatial(info('CC BY-SA 4.0','https://creativecommons.org/licenses/by-sa/4.0/','')),true);
assert.strictEqual(api.licenseAllowsSpatial(info('CC0 1.0','https://creativecommons.org/publicdomain/zero/1.0/','')),true);
assert.strictEqual(api.licenseAllowsSpatial(info('CC BY-ND 4.0','https://creativecommons.org/licenses/by-nd/4.0/','No derivatives')),false);
assert.strictEqual(api.licenseAllowsSpatial(info('CC BY-NC 4.0','https://creativecommons.org/licenses/by-nc/4.0/','NonCommercial')),false);
assert.strictEqual(api.licenseAllowsSpatial({extmetadata:{}}),false);

let transport=api.selectMP3({url:'https://upload.wikimedia.org/a/song.mp3',mime:'audio/mpeg',derivatives:[]});
assert(transport&&transport.source==='original');
assert.strictEqual(transport.url,'https://upload.wikimedia.org/a/song.mp3');

transport=api.selectMP3({url:'https://upload.wikimedia.org/a/song.ogg',mime:'audio/ogg',derivatives:[
  {src:'https://upload.wikimedia.org/transcoded/song.mp3',type:'audio/mpeg',transcodekey:'mp3'}
]});
assert(transport&&transport.source==='mp3_derivative');
assert.strictEqual(transport.url,'https://upload.wikimedia.org/transcoded/song.mp3');

assert.strictEqual(api.selectMP3({url:'https://upload.wikimedia.org/a/song.ogg',mime:'audio/ogg',derivatives:[]}),null);
assert.strictEqual(api.selectMP3({url:'http://example.com/song.mp3',mime:'audio/mpeg',derivatives:[]}),null);

const url=api.buildCatalogURL('cb');
assert(url.indexOf('commons.wikimedia.org/w/api.php')!==-1);
assert(url.indexOf('generator=categorymembers')!==-1);
assert(url.indexOf('Category%3AAudio%20files%20of%20music')!==-1);
assert(url.indexOf('prop=videoinfo')!==-1);
assert(url.indexOf('derivatives')!==-1);
assert(url.indexOf('extmetadata')!==-1);
assert(url.indexOf('callback=cb')!==-1);
assert(url.indexOf('client_id')===-1);
assert(url.indexOf('token')===-1);

function FakeElement(tag){
  this.tagName=tag;
  this.children=[];
  this.style={};
  this.parentNode=null;
  this.textContent='';
  this.className='';
  this.listeners={};
  this.firstChild=null;
  this.disabled=false;
}
FakeElement.prototype.appendChild=function(child){
  child.parentNode=this;
  this.children.push(child);
  this.firstChild=this.children[0]||null;
  return child;
};
FakeElement.prototype.removeChild=function(child){
  const i=this.children.indexOf(child);
  if(i>=0)this.children.splice(i,1);
  this.firstChild=this.children[0]||null;
  child.parentNode=null;
};
FakeElement.prototype.insertBefore=function(child,before){
  child.parentNode=this;
  const i=this.children.indexOf(before);
  if(i<0)this.children.push(child);else this.children.splice(i,0,child);
  this.firstChild=this.children[0]||null;
};
FakeElement.prototype.addEventListener=function(type,handler){this.listeners[type]=handler;};
FakeElement.prototype.setAttribute=function(name,value){this[name]=value;};
FakeElement.prototype.click=function(){
  assert(this.listeners.click,'button missing click listener');
  this.listeners.click({type:'click',target:this});
};

const hero=new FakeElement('div');
const page=new FakeElement('main');
page.appendChild(hero);
const head=new FakeElement('head');
let appendedScript=null;
head.appendChild=function(child){appendedScript=child;child.parentNode=head;return child;};
const fakeDocument={
  querySelector:function(selector){return selector==='.card.hero'?hero:null;},
  createElement:function(tag){return new FakeElement(tag);},
  createTextNode:function(text){const n=new FakeElement('#text');n.textContent=text;return n;},
  head:head
};

const uiSnippet="var root=this;\nvar API='https://commons.wikimedia.org/w/api.php';\nvar CATEGORY='Category:Audio files of music';\nvar jsonpCounter=0;\nvar state={tracks:[],lastProbe:null};\n"+
  sliceFunction('el','button')+'\n'+
  sliceFunction('button','setStatus')+'\n'+
  sliceFunction('setStatus','removeNode')+'\n'+
  sliceFunction('removeNode','buildCatalogURL')+'\n'+
  sliceFunction('buildCatalogURL','jsonp')+'\n'+
  sliceFunction('jsonp','plain')+'\n'+
  'function normalizePage(){return null;}\nfunction renderTracks(){}\n'+
  sliceFunction('loadCatalog','createUI')+'\n'+
  sliceFunction('createUI','boot')+'\n'+
  'this.makeUI=createUI;';

const uiSandbox={
  document:fakeDocument,
  encodeURIComponent:encodeURIComponent,
  setTimeout:function(){return 1;},
  clearTimeout:function(){}
};
vm.runInNewContext(uiSnippet,uiSandbox,{filename:'commons-ui-click-extract.js'});
const ui=uiSandbox.makeUI();
assert(ui&&ui.load,'Commons UI should create a load button');
assert.doesNotThrow(function(){ui.load.click();},'Commons catalog button click must not throw');
assert.strictEqual(ui.load.disabled,true);
assert.strictEqual(ui.load.textContent,'LOADING COMMONS…');
assert(ui.status.textContent.indexOf('Requesting a small batch')!==-1);
assert(appendedScript&&appendedScript.src.indexOf('callback=PocketSpatialCommonsJSONP1')!==-1,'catalog click should append JSONP request script');

console.log('Pocket Spatial Wikimedia Commons transport and catalog-button tests passed.');
