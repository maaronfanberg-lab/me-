'use strict';
var assert=require('assert');
var fs=require('fs');
var vm=require('vm');
var source=fs.readFileSync('apps/pocket-spatial-buffered-catalog.js','utf8');

function sliceFunction(name,nextName){
  var start=source.indexOf('function '+name+'(');
  var end=source.indexOf('\nfunction '+nextName+'(',start);
  assert(start>=0,'missing function '+name);
  assert(end>start,'missing boundary after '+name);
  return source.slice(start,end);
}

var snippet="var API='https://commons.wikimedia.org/w/api.php';\nvar CATEGORY='Category:Audio files of music';\n"+
  sliceFunction('plain','metadataValue')+'\n'+
  sliceFunction('metadataValue','licenseAllowsSpatial')+'\n'+
  sliceFunction('licenseAllowsSpatial','isHTTPS')+'\n'+
  sliceFunction('isHTTPS','looksLikeMP3')+'\n'+
  sliceFunction('looksLikeMP3','selectMP3')+'\n'+
  sliceFunction('selectMP3','pageURL')+'\n'+
  sliceFunction('pageURL','normalizePage')+'\n'+
  sliceFunction('normalizePage','buildCatalogURL')+'\n'+
  sliceFunction('buildCatalogURL','jsonp')+'\n'+
  'this.api={licenseAllowsSpatial:licenseAllowsSpatial,selectMP3:selectMP3,normalizePage:normalizePage,buildCatalogURL:buildCatalogURL};';

var sandbox={encodeURIComponent:encodeURIComponent};
vm.runInNewContext(snippet,sandbox,{filename:'buffered-catalog-pure.js'});
var api=sandbox.api;

function info(shortName,url,usage,derivatives){
  return{
    url:'https://upload.wikimedia.org/original.ogg',
    mime:'audio/ogg',
    derivatives:derivatives||[],
    extmetadata:{
      LicenseShortName:{value:shortName||''},
      LicenseUrl:{value:url||''},
      UsageTerms:{value:usage||''},
      Artist:{value:'Test Artist'}
    }
  };
}

assert.strictEqual(api.licenseAllowsSpatial(info('CC BY-SA 4.0','https://creativecommons.org/licenses/by-sa/4.0/','')),true);
assert.strictEqual(api.licenseAllowsSpatial(info('CC BY-ND 4.0','https://creativecommons.org/licenses/by-nd/4.0/','No derivatives')),false);
assert.strictEqual(api.licenseAllowsSpatial(info('CC BY-NC 4.0','https://creativecommons.org/licenses/by-nc/4.0/','NonCommercial')),false);
assert.strictEqual(api.licenseAllowsSpatial({extmetadata:{}}),false);

var mp3='https://upload.wikimedia.org/transcoded/test.mp3';
assert.strictEqual(api.selectMP3(info('CC BY-SA 4.0','','',[{src:mp3,type:'audio/mpeg',transcodekey:'mp3'}])),mp3);

var page={
  pageid:7,
  title:'File:Test song.ogg',
  videoinfo:[info('CC BY-SA 4.0','https://creativecommons.org/licenses/by-sa/4.0/','',[{src:mp3,type:'audio/mpeg',transcodekey:'mp3'}])]
};
var track=api.normalizePage(page);
assert(track,'permitted page should normalize');
assert.strictEqual(track.pageid,7);
assert.strictEqual(track.audio,mp3);
assert.strictEqual(track.artist,'Test Artist');
assert(track.file_page.indexOf('commons.wikimedia.org/wiki/')!==-1);

var url=api.buildCatalogURL('cb');
assert(url.indexOf('generator=categorymembers')!==-1);
assert(url.indexOf('Category%3AAudio%20files%20of%20music')!==-1);
assert(url.indexOf('derivatives%7Cextmetadata')!==-1);
assert(url.indexOf('callback=cb')!==-1);
assert(url.indexOf('client_id')===-1);
assert(url.indexOf('access_token')===-1);
assert(url.indexOf('api_key')===-1);

console.log('Pocket Spatial buffered Commons catalog tests passed.');
