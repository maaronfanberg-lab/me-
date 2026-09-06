const assert=require('assert');
const fs=require('fs');
const vm=require('vm');

const source=fs.readFileSync('apps/pocket-spatial-jamendo.js','utf8');

function sliceFunction(name,nextName){
  const start=source.indexOf('function '+name+'(');
  const end=source.indexOf('\nfunction '+nextName+'(',start);
  assert(start>=0,'missing function '+name);
  assert(end>start,'missing boundary after '+name);
  return source.slice(start,end);
}

const constants="var TEST_CLIENT_ID='709fa152';\nvar API='https://api.jamendo.com/v3.0/tracks/';\n";
const snippet=constants+
  sliceFunction('buildTracksURL','jsonp')+'\n'+
  sliceFunction('licenseURL','licenseLabel')+'\n'+
  'this.api={buildTracksURL:buildTracksURL,licenseAllowsSpatial:licenseAllowsSpatial};';

const sandbox={encodeURIComponent:encodeURIComponent};
vm.runInNewContext(snippet,sandbox,{filename:'jamendo-pure-extract.js'});
const api=sandbox.api;

assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:'https://creativecommons.org/licenses/by/4.0/'}),true);
assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:'https://creativecommons.org/licenses/by-sa/4.0/'}),true);
assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:'https://creativecommons.org/licenses/by-nc/4.0/'}),true);
assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:'https://creativecommons.org/licenses/by-nd/4.0/'}),false);
assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:'https://creativecommons.org/licenses/by-nc-nd/4.0/'}),false);
assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:''}),false);
assert.strictEqual(api.licenseAllowsSpatial({license_ccurl:'https://example.com/license'}),false);

const url=api.buildTracksURL('cb');
assert(url.indexOf('client_id=709fa152')!==-1);
assert(url.indexOf('audioformat=mp32')!==-1);
assert(url.indexOf('include=licenses')!==-1);
assert(url.indexOf('ccnd=false')!==-1);
assert(url.indexOf('callback=cb')!==-1);
assert(url.indexOf('audiodownload')===-1);

console.log('Pocket Spatial Jamendo pure contract tests passed.');
