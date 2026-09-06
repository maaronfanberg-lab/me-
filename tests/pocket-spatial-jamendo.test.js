const assert=require('assert');
const fs=require('fs');
const vm=require('vm');

const source=fs.readFileSync('apps/pocket-spatial-jamendo.js','utf8');
const sandbox={
  console:console,
  setTimeout:setTimeout,
  clearTimeout:clearTimeout,
  setInterval:setInterval,
  clearInterval:clearInterval,
  document:{readyState:'loading',addEventListener:function(){},createElement:function(){return {};},head:{appendChild:function(){}}}
};
sandbox.window=sandbox;
sandbox.self=sandbox;
vm.runInNewContext(source,sandbox,{filename:'pocket-spatial-jamendo.js'});

const api=sandbox.PocketSpatialJamendo;
assert(api,'PocketSpatialJamendo API missing');
assert.strictEqual(api.testClientId,'709fa152');

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
