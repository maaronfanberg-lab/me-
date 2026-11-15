'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const create = require('./capture-latest.js');
const sample = {start: 1000, rate: 2, samples: [11,-5,3]};
const cap = create({parse: () => [sample]});
test('SeedLink 4 binary framing passes the miniSEED 2 payload to reader', () => {
  const sta = ['IU','ANMO','00','BHZ','Albuquerque'];
  const id = Buffer.from('IU_ANMO');
  const payload = Buffer.alloc(512);
  const b = Buffer.alloc(17 + id.length + payload.length);
  b.write('SE2D',0,'ascii');b.writeUInt32LE(payload.length,4);b[16]=id.length;
  id.copy(b,17);payload.copy(b,17+id.length);
  assert.equal(cap.decodeSeedLinkPacket(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),sta).records[0],sample);
  assert.deepEqual(cap.decodeSeedLinkPacket(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),['IU','HRV','00','BHZ','Harvard']).records,[]);
  assert.equal(cap.decodeSeedLinkPacket(Uint8Array.from([69,78,68]).buffer,sta).ended,true);
});
test('amplitude counts, original timestamps, and gap separation', () => {
  const sta=['IU','ANMO','00','BHZ','Albuquerque'];
  const r=cap.contiguousLatest([{start:1000,rate:2,samples:[11,-5,3]},{start:2500,rate:2,samples:[8,7]}],sta,'SeedLink');
  assert.deepEqual([...r.raw],[11,-5,3,8,7]);
  assert.equal(r.startT,1000);assert.equal(r.endT,3500);
  assert.ok(cap.csv(r).includes('1970-01-01T00:00:01.500Z,-5,IU.ANMO.00.BHZ'));
  const gap=cap.contiguousLatest([{start:1000,rate:2,samples:[1,2]},{start:9000,rate:2,samples:[7,8]}],sta,'SeedLink');
  assert.deepEqual([...gap.raw],[7,8]); // no invented zeros bridging a gap
});
test('archive used once when websocket unavailable, with honest UTC age', async () => {
  const at=1000000, sta=['IU','ANMO','00','BHZ','Albuquerque'];
  let called=0;
  const reader=create({parse: () => [{start:at-5000,rate:2,samples:[3,5,8,11]}]});
  const r=await reader.capture(sta,{at,SocketClass:null,fetcher:async(url) => {
    called++;assert.ok(url.includes('service.earthscope.org'));return {ok:true,arrayBuffer:async()=>new ArrayBuffer(512)};
  }});
  assert.equal(called,1);
  assert.equal(r.source,'EarthScope archive');
  assert.equal(r.endT,at-3000);
  assert.equal(r.warning,'');
  assert.deepEqual([...r.raw],[3,5,8,11]);
});
test('stale sample is labeled, never represented as fresh', async () => {
  const at=600000, sta=['IU','ANMO','00','BHZ','Albuquerque'];
  const reader=create({parse: () => [{start:1000,rate:2,samples:[1,2,3]}]});
  const r=await reader.capture(sta,{at,SocketClass:null,fetcher:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(512)})});
  assert.match(r.warning,/Not fresh/);
  assert.ok(r.ageMs>120000);
});
