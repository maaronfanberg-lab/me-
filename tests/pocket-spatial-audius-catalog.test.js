'use strict';
var assert=require('assert');
var fs=require('fs');
var vm=require('vm');
var source=fs.readFileSync('apps/pocket-spatial-audius-catalog.js','utf8');

function sliceFunction(name,nextName){
  var start=source.indexOf('function '+name+'(');
  var end=source.indexOf('\nfunction '+nextName+'(',start);
  assert(start>=0,'missing function '+name);
  assert(end>start,'missing boundary after '+name);
  return source.slice(start,end);
}

var snippet="var API='https://api.audius.co/v1';\nvar APP_NAME='PocketSpatial';\nvar MAX_RESULTS=24;\n"+
  sliceFunction('cleanText','licenseAllowsSpatial')+'\n'+
  sliceFunction('licenseAllowsSpatial','isPlayable')+'\n'+
  sliceFunction('isPlayable','streamURL')+'\n'+
  sliceFunction('streamURL','pageURL')+'\n'+
  sliceFunction('pageURL','normalizeTrack')+'\n'+
  sliceFunction('normalizeTrack','buildCatalogURL')+'\n'+
  sliceFunction('buildCatalogURL','xhrJSON')+'\n'+
  'this.api={licenseAllowsSpatial:licenseAllowsSpatial,isPlayable:isPlayable,streamURL:streamURL,pageURL:pageURL,normalizeTrack:normalizeTrack,buildCatalogURL:buildCatalogURL};';

var sandbox={encodeURIComponent:encodeURIComponent,String:String,Number:Number,RegExp:RegExp};
vm.runInNewContext(snippet,sandbox,{filename:'audius-catalog-pure.js'});
var api=sandbox.api;

function track(overrides){
  var t={
    id:'D7KyD',
    title:'Test Track',
    duration:142,
    is_streamable:true,
    is_stream_gated:false,
    stream_conditions:null,
    access:{stream:true},
    license:'CC BY 4.0',
    permalink:'/testartist/test-track',
    user:{name:'Test Artist',handle:'testartist'}
  };
  var k;
  overrides=overrides||{};
  for(k in overrides)if(Object.prototype.hasOwnProperty.call(overrides,k))t[k]=overrides[k];
  return t;
}

assert.strictEqual(api.licenseAllowsSpatial(track({license:'CC BY 4.0'})),true);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'CC BY-SA 4.0'})),true);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'Creative Commons Attribution'})),true);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'CC0 1.0'})),true);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'Public Domain'})),true);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'CC BY-NC 4.0'})),false);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'CC BY-ND 4.0'})),false);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'CC BY-NC-ND 4.0'})),false);
assert.strictEqual(api.licenseAllowsSpatial(track({license:'All Rights Reserved'})),false);
assert.strictEqual(api.licenseAllowsSpatial(track({license:''})),false);

assert.strictEqual(api.isPlayable(track()),true);
assert.strictEqual(api.isPlayable(track({is_streamable:false})),false);
assert.strictEqual(api.isPlayable(track({is_stream_gated:true})),false);
assert.strictEqual(api.isPlayable(track({stream_conditions:{follow_user_id:7}})),false);
assert.strictEqual(api.isPlayable(track({access:{stream:false}})),false);
assert.strictEqual(api.isPlayable(track({duration:181})),false);
assert.strictEqual(api.isPlayable(track({license:'CC BY-ND 4.0'})),false);

var normalized=api.normalizeTrack(track());
assert(normalized,'playable Audius track should normalize');
assert.strictEqual(normalized.pageid,'audius:D7KyD');
assert.strictEqual(normalized.source,'Audius');
assert.strictEqual(normalized.artist,'Test Artist');
assert.strictEqual(normalized.duration,142);
assert.strictEqual(normalized.license,'CC BY 4.0');
assert.strictEqual(normalized.file_page,'https://audius.co/testartist/test-track');
assert.strictEqual(normalized.audio,'https://api.audius.co/v1/tracks/D7KyD/stream?app_name=PocketSpatial');
assert.strictEqual(api.normalizeTrack(track({license:'CC BY-ND 4.0'})),null);
assert.strictEqual(api.normalizeTrack(track({license:''})),null);

var trending=api.buildCatalogURL('');
assert(trending.indexOf('https://api.audius.co/v1/tracks/trending?')===0);
assert(trending.indexOf('limit=24')!==-1);
assert(trending.indexOf('app_name=PocketSpatial')!==-1);
var search=api.buildCatalogURL('ambient piano');
assert(search.indexOf('/tracks/search?query=ambient%20piano')!==-1);
assert(search.indexOf('app_name=PocketSpatial')!==-1);

assert(source.indexOf('access_token')===-1);
assert(source.indexOf('client_secret')===-1);
assert(source.indexOf('bearerToken')===-1);
assert(source.indexOf('localStorage')===-1);
assert(source.indexOf('indexedDB')===-1);

console.log('Pocket Spatial Audius catalog tests passed.');
