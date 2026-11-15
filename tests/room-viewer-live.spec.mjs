import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const BASE = 'http://127.0.0.1:4173';
const RELAY = 'https://room-live-mirror.dfp6k69dw5.workers.dev/api/feed';
const RAW_FEED = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/feed.json';
const API_FEED = 'https://api.github.com/repos/maaronfanberg-lab/me-/contents/room/feed.json';
const RAW_HISTORY = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/conversation.json';

function iso(offsetSeconds = 0) {
  return new Date(Date.now() + offsetSeconds * 1000).toISOString();
}

function beatMessages(beat) {
  const speakers = ['sarah', 'mara', 'owen', 'jules'];
  return speakers.map((speaker, i) => ({
    id: `sim-beat-${beat}-${speaker}`,
    speaker,
    text: `SIM BEAT ${beat} ${speaker.toUpperCase()}`,
    at: iso(beat - 100 + i * 0.01),
    beat_id: `sim-beat-${beat}`,
  }));
}

function feed(beat, generatedOffsetSeconds = 0, conversation = null) {
  return {
    generated_at: iso(generatedOffsetSeconds),
    state: {
      version: 'room-viewer-simulator',
      cycle: beat,
      last_run: iso(generatedOffsetSeconds),
      beat_message_count: 4,
    },
    minds: {
      entities: {
        sarah: { name: 'Sarah' },
        mara: { name: 'Mara' },
        owen: { name: 'Owen' },
        jules: { name: 'Jules' },
      },
    },
    conversation: conversation || beatMessages(beat),
  };
}

function retainedHistory() {
  const list = [];
  for (let i = 1; i <= 996; i++) {
    list.push({
      id: `history-${i}`,
      speaker: ['sarah', 'mara', 'owen', 'jules'][i % 4],
      text: `retained history ${i}`,
      at: new Date(Date.now() - (1200 - i) * 1000).toISOString(),
      beat_id: `history-beat-${Math.floor(i / 4)}`,
    });
  }
  list.push(...beatMessages(100));
  return list;
}

function githubContentsPayload(value) {
  const text = JSON.stringify(value);
  return {
    type: 'file',
    encoding: 'base64',
    content: Buffer.from(text, 'utf8').toString('base64'),
  };
}

test('open Room viewer must catch up from an independent live fallback when Pages is stale', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(`pageerror: ${e.message}`));
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });

  const history = retainedHistory();
  const staticPagesFeed = feed(100, -300);
  let apiCalls = 0;
  let relayCalls = 0;
  let rawCalls = 0;
  const observedApiBeats = [];

  await page.route(`${RELAY}*`, async route => {
    relayCalls++;
    await route.abort('failed');
  });

  await page.route(`${RAW_FEED}*`, async route => {
    rawCalls++;
    await route.abort('failed');
  });

  await page.route(`${API_FEED}*`, async route => {
    apiCalls++;
    observedApiBeats.push(103);
    const catchUp = feed(103, 0, [
      ...beatMessages(101),
      ...beatMessages(102),
      ...beatMessages(103),
    ]);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(githubContentsPayload(catchUp)),
    });
  });

  await page.route(`${RAW_HISTORY}*`, async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(history),
    });
  });

  await page.route(`${BASE}/room/conversation.json*`, async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(history),
    });
  });

  await page.route(`${BASE}/room/feed.json*`, async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(staticPagesFeed),
    });
  });

  await page.goto(`${BASE}/room/?viewer-simulator=1`, { waitUntil: 'domcontentloaded' });

  // History must survive regardless of whether the independent fallback catches
  // up immediately or on a later poll. A correct viewer may therefore show
  // more than 1000 messages after appending the live tail.
  await expect.poll(async () => page.locator('.msg').count(), { timeout: 12000 }).toBeGreaterThanOrEqual(1000);
  await page.waitForTimeout(4500);

  const status = await page.locator('#status').innerText();
  const meta = await page.locator('#meta').innerText();
  const bodyText = await page.locator('#chat').innerText();
  const beatMatch = status.match(/beat\s+(\d+)/i);
  const observedBeat = beatMatch ? Number(beatMatch[1]) : null;
  const messageCount = await page.locator('.msg').count();

  const requiredMarkers = [101, 102, 103].map(n => `SIM BEAT ${n}`);
  const markersPresent = requiredMarkers.map(marker => bodyText.includes(marker));
  const pass = observedBeat !== null && observedBeat >= 103 &&
    markersPresent.every(Boolean) && messageCount >= 1000 && apiCalls >= 1 && errors.length === 0;

  const diagnostic = {
    checked_at: new Date().toISOString(),
    pass,
    expected_final_beat: 103,
    observed_final_beat: observedBeat,
    status,
    meta,
    retained_message_floor: 1000,
    observed_message_count: messageCount,
    markers_present: Object.fromEntries(requiredMarkers.map((m, i) => [m, markersPresent[i]])),
    relay_calls: relayCalls,
    raw_calls: rawCalls,
    api_calls: apiCalls,
    api_beats_served: observedApiBeats,
    errors,
    invariant: 'already-open viewer catches up without reload and never treats static Pages snapshot as live',
  };

  fs.writeFileSync('room/viewer-simulator-diagnostic.json', JSON.stringify(diagnostic, null, 2) + '\n');

  expect(pass, JSON.stringify(diagnostic, null, 2)).toBeTruthy();
});
