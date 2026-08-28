import fs from 'node:fs';
import vm from 'node:vm';

const file = 'apps/live-earth-oracle.html';
const html = fs.readFileSync(file, 'utf8');

function fail(message) {
  console.error(`Fast Oracle validation failed: ${message}`);
  process.exit(1);
}

if (!html.includes('<title>The Fast Nonsense Predictor</title>')) fail('fast predictor title missing');
if (!html.includes('Experiment, not investment advice.')) fail('experiment disclaimer missing');
if (!html.includes('F₀(x)=x')) fail('Alex recurrence description missing');

const expectedStreams = ['market','btc','eth','sol','pressure','aircraft','iss','wind','mag','k1m','xray','wiki'];
for (const stream of expectedStreams) {
  if (!new RegExp(`\\b${stream}\\s*:`).test(html)) fail(`fast stream missing: ${stream}`);
}
const retiredSlowStreams = ['air:{','tide:{','buoy:{','river:{','aurora:{','quakes:{','weather:{','github:{'];
for (const token of retiredSlowStreams) {
  if (html.includes(token)) fail(`slow stream still configured: ${token}`);
}

const requiredSources = [
  'room-live-mirror.dfp6k69dw5.workers.dev/api/market',
  'ws-feed.exchange.coinbase.com',
  'api.adsb.lol',
  'api.wheretheiss.at',
  'services.swpc.noaa.gov/products/summary/solar-wind-speed.json',
  'services.swpc.noaa.gov/products/summary/solar-wind-mag-field.json',
  'services.swpc.noaa.gov/json/planetary_k_index_1m.json',
  'services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json',
  'stream.wikimedia.org/v2/stream/recentchange',
];
for (const source of requiredSources) if (!html.includes(source)) fail(`source missing: ${source}`);

const guards = [
  'AbortController',
  'async function guarded',
  "document.visibilityState==='visible'",
  'setTimeout(crypto,3500)',
  'localStorage.setItem',
  'function pearson',
  'function settle',
  'function issuePrediction',
  'for(let i=1n;i<=1000n;i++)',
  'cfg[k].stale',
];
for (const token of guards) if (!html.includes(token)) fail(`reliability/score guard missing: ${token}`);

const scripts = [];
for (const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)) if (m[1].trim()) scripts.push(m[1]);
if (!scripts.length) fail('no inline JavaScript');
for (const [i,code] of scripts.entries()) {
  try { new vm.Script(code, { filename: `${file}#${i+1}` }); }
  catch (e) { fail(`JavaScript parse error: ${e.message}`); }
}

if ((html.match(/<script\b/gi)||[]).length !== (html.match(/<\/script>/gi)||[]).length) fail('unbalanced script tags');
console.log(`Fast Oracle validation passed: ${expectedStreams.length} fast streams, Alex recurrence, prediction settlement, correlation scoring, and JS parse all present.`);
