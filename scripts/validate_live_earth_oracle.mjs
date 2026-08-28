import fs from 'node:fs';
import vm from 'node:vm';

const file = 'apps/live-earth-oracle.html';
const html = fs.readFileSync(file, 'utf8');

function fail(message) {
  console.error(`Live Earth Oracle validation failed: ${message}`);
  process.exit(1);
}

if (!html.includes('<title>The Live Earth Oracle</title>')) fail('expected title is missing');
if (!html.includes('Real data. Fake theory.')) fail('satire disclaimer is missing');
if (!html.includes('MK II')) fail('Mk II marker is missing');

const expectedStreams = [
  'market','crypto','aircraft','iss','quakes','kp','solar','aurora',
  'weather','air','tide','buoy','river','github'
];
for (const stream of expectedStreams) {
  if (!new RegExp(`\\b${stream}\\s*:`).test(html)) fail(`stream configuration missing: ${stream}`);
}

const requiredReliabilityTokens = [
  'AbortController',
  "c.status=c.updated?'stale':'error'",
  'async function guarded(k,fn)',
  'if(state.running[k])return',
  'setTimeout(crypto,5000)',
  "document.visibilityState==='visible'",
  'Object.keys(jobs).forEach(k=>jobs[k]())',
  "if(ttl&&c.updated&&now-c.updated>ttl&&c.status==='live')",
];
for (const token of requiredReliabilityTokens) {
  if (!html.includes(token)) fail(`reliability guard missing: ${token}`);
}

const requiredSources = [
  'room-live-mirror.dfp6k69dw5.workers.dev/api/market',
  'ws-feed.exchange.coinbase.com',
  'api.adsb.lol',
  'api.wheretheiss.at',
  'earthquake.usgs.gov',
  'services.swpc.noaa.gov',
  'api.open-meteo.com',
  'air-quality-api.open-meteo.com',
  'api.tidesandcurrents.noaa.gov',
  'www.ndbc.noaa.gov/data/realtime2/44007.txt',
  'waterservices.usgs.gov/nwis/iv/',
  'api.github.com/repos/maaronfanberg-lab/me-/commits',
];
for (const source of requiredSources) {
  if (!html.includes(source)) fail(`expected source missing: ${source}`);
}

const inlineScripts = [];
for (const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)) {
  const body = match[1].trim();
  if (body) inlineScripts.push(body);
}
if (!inlineScripts.length) fail('no inline JavaScript found');

inlineScripts.forEach((code, index) => {
  try {
    new vm.Script(code, { filename: `${file}#inline-${index + 1}` });
  } catch (error) {
    fail(`JavaScript parse error: ${error.message}`);
  }
});

const openScripts = (html.match(/<script\b/gi) || []).length;
const closeScripts = (html.match(/<\/script>/gi) || []).length;
if (openScripts !== closeScripts) fail(`unbalanced script tags: ${openScripts} open, ${closeScripts} close`);

console.log(`Live Earth Oracle validation passed: ${inlineScripts.length} inline script(s), ${expectedStreams.length} streams, reliability guards present.`);
