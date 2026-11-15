import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const BASE = 'http://127.0.0.1:4173';
const RELAY = 'https://room-live-mirror.dfp6k69dw5.workers.dev/api/feed';
const RAW_FEED = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/feed.json';
const RAW_HISTORY = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/conversation.json';

function nowIso(offset = 0) {
  return new Date(Date.now() + offset * 1000).toISOString();
}

function messages(beat) {
  return ['sarah', 'mara', 'owen', 'jules'].map((speaker, i) => ({
    id: `cors-beat-${beat}-${speaker}`,
    speaker,
    text: `CORS BEAT ${beat} ${speaker.toUpperCase()}`,
    at: nowIso(i * 0.01),
    beat_id: `cors-beat-${beat}`,
  }));
}

function feed(beat, offset = 0) {
  return {
    generated_at: nowIso(offset),
    state: { cycle: beat, last_run: nowIso(offset), beat_message_count: 4 },
    minds: { entities: {
      sarah: { name: 'Sarah' }, mara: { name: 'Mara' },
      owen: { name: 'Owen' }, jules: { name: 'Jules' },
    } },
    conversation: messages(beat),
  };
}

function history() {
  const out=[];
  for(let i=1;i<=996;i++) out.push({
    id:`cors-history-${i}`,
    speaker:['sarah','mara','owen','jules'][i%4],
    text:`cors retained ${i}`,
    at:new Date(Date.now()-(1200-i)*1000).toISOString(),
    beat_id:`cors-history-beat-${Math.floor(i/4)}`,
  });
  out.push(...messages(100));
  return out;
}

test('cross-origin live polling must not depend on preflight for simple public GET feeds', async ({ page }) => {
  const retained=history();
  const pagesSnapshot=feed(100,-300);
  const errors=[];
  let liveBeat=100;
  let preflightCalls=0;
  let liveGetCalls=0;
  const methods=[];

  page.on('pageerror',e=>errors.push(`pageerror: ${e.message}`));

  const liveHandler=async route=>{
    const method=route.request().method();
    methods.push(method);
    if(method==='OPTIONS'){
      preflightCalls++;
      await route.fulfill({status:403,contentType:'text/plain',body:'preflight rejected'});
      return;
    }
    liveGetCalls++;
    liveBeat=Math.min(103,liveBeat+1);
    await route.fulfill({
      status:200,
      contentType:'application/json',
      headers:{'access-control-allow-origin':'*','cache-control':'no-store'},
      body:JSON.stringify(feed(liveBeat,0)),
    });
  };

  await page.route(`${RELAY}*`,liveHandler);
  await page.route(`${RAW_FEED}*`,liveHandler);

  // Remote history rejects preflight too; same-origin retained history remains available.
  await page.route(`${RAW_HISTORY}*`,async route=>{
    if(route.request().method()==='OPTIONS'){
      preflightCalls++;
      await route.fulfill({status:403,contentType:'text/plain',body:'preflight rejected'});
    }else{
      await route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(retained)});
    }
  });
  await page.route(`${BASE}/room/conversation.json*`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(retained)}));
  await page.route(`${BASE}/room/feed.json*`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(pagesSnapshot)}));

  await page.goto(`${BASE}/room/?cors-simulator=1`,{waitUntil:'domcontentloaded'});
  await expect.poll(async()=>page.locator('.msg').count(),{timeout:12000}).toBeGreaterThanOrEqual(1000);
  await page.waitForTimeout(8500);

  const status=await page.locator('#status').innerText();
  const meta=await page.locator('#meta').innerText();
  const text=await page.locator('#chat').innerText();
  const m=status.match(/beat\s+(\d+)/i);
  const observedBeat=m?Number(m[1]):null;
  const markers=[101,102,103].map(n=>text.includes(`CORS BEAT ${n}`));
  const pass=observedBeat!==null&&observedBeat>=103&&markers.every(Boolean)&&preflightCalls===0&&liveGetCalls>0&&errors.length===0;

  const diagnostic={
    checked_at:new Date().toISOString(),pass,
    expected_final_beat:103,observed_final_beat:observedBeat,
    status,meta,preflight_calls:preflightCalls,live_get_calls:liveGetCalls,
    request_methods:methods,markers_present:{101:markers[0],102:markers[1],103:markers[2]},
    errors,
    invariant:'public cross-origin live feed uses simple GET without preflight-triggering request headers',
  };
  fs.writeFileSync('room/viewer-cors-simulator-diagnostic.json',JSON.stringify(diagnostic,null,2)+'\n');
  expect(pass,JSON.stringify(diagnostic,null,2)).toBeTruthy();
});
