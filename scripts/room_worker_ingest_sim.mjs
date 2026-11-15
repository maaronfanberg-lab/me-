#!/usr/bin/env node
import fs from 'node:fs';
import vm from 'node:vm';

const SOURCE_PATH = 'cloudflare/room-worker/src/index.js';
const OUT_PATH = 'room/worker-ingest-simulator-diagnostic.json';
const source = fs.readFileSync(SOURCE_PATH, 'utf8');

function extractClass(src, className) {
  const marker = `export class ${className}`;
  const start = src.indexOf(marker);
  if (start < 0) throw new Error(`missing ${marker}`);
  const brace = src.indexOf('{', start);
  if (brace < 0) throw new Error(`missing class body for ${className}`);
  let depth = 0;
  let quote = '';
  let escaped = false;
  for (let i = brace; i < src.length; i++) {
    const ch = src[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') { quote = ch; continue; }
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return src.slice(start, i + 1).replace(`export class ${className}`, `class ${className}`);
    }
  }
  throw new Error(`unterminated class ${className}`);
}

class Storage {
  constructor(initial = {}) { this.map = new Map(Object.entries(initial)); }
  async get(key) { return this.map.get(key); }
  async put(key, value) { this.map.set(key, structuredClone(value)); }
}

function feed({ boot, cycle, at }) {
  return {
    generated_at: at,
    state: { boot_id: boot, cycle, last_run: at, beat_message_count: 4 },
    conversation: [],
    minds: { entities: { sarah: { name: 'Sarah' } } },
  };
}

const classCode = extractClass(source, 'RoomState');
const sandbox = {
  console,
  structuredClone,
  Date,
  crypto: globalThis.crypto,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(`class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }\n${classCode}\nglobalThis.__RoomState = RoomState;`, sandbox);
const RoomState = sandbox.__RoomState;

async function runScenario(name, currentFeed, incomingFeed, expectedAccepted, expectedReason = null) {
  const storage = new Storage({ latest: { feed: currentFeed, receivedAt: currentFeed.generated_at, sourceSha: 'old' } });
  const obj = new RoomState({ storage }, {});
  const result = await obj.putLatest(incomingFeed, 'incoming');
  const stored = await storage.get('latest');
  const actualAccepted = Boolean(result?.accepted);
  const pass = actualAccepted === expectedAccepted &&
    (expectedReason === null || result?.reason === expectedReason) &&
    (expectedAccepted ? stored?.feed?.generated_at === incomingFeed.generated_at : stored?.feed?.generated_at === currentFeed.generated_at);
  return {
    name,
    pass,
    expected_accepted: expectedAccepted,
    actual_accepted: actualAccepted,
    expected_reason: expectedReason,
    actual_reason: result?.reason || null,
    current_boot: currentFeed.state.boot_id,
    current_cycle: currentFeed.state.cycle,
    current_at: currentFeed.generated_at,
    incoming_boot: incomingFeed.state.boot_id,
    incoming_cycle: incomingFeed.state.cycle,
    incoming_at: incomingFeed.generated_at,
    stored_boot: stored?.feed?.state?.boot_id || null,
    stored_cycle: stored?.feed?.state?.cycle ?? null,
    stored_at: stored?.feed?.generated_at || null,
  };
}

const oldBoot = 'room-reboot-2026-08-17T13:06Z';
const newBoot = 'room-sterile-v4-2026-08-18';
const scenarios = [];

// Exact production failure: a newer Room boot legitimately reset its cycle
// counter. Freshness must not be rejected only because 2382 < stale 8578.
scenarios.push(await runScenario(
  'newer reboot with lower cycle is accepted',
  feed({ boot: oldBoot, cycle: 8578, at: '2026-08-18T00:53:55.998258Z' }),
  feed({ boot: newBoot, cycle: 2382, at: '2026-08-19T14:35:48.478380Z' }),
  true,
));

// A replay from the stale previous boot must not overwrite a newer current boot
// merely because its numeric cycle happens to be larger.
scenarios.push(await runScenario(
  'older previous boot with higher cycle is rejected',
  feed({ boot: newBoot, cycle: 2382, at: '2026-08-19T14:35:48.478380Z' }),
  feed({ boot: oldBoot, cycle: 8579, at: '2026-08-18T00:54:30.000000Z' }),
  false,
));

scenarios.push(await runScenario(
  'same boot older cycle is rejected',
  feed({ boot: newBoot, cycle: 2382, at: '2026-08-19T14:35:48.478380Z' }),
  feed({ boot: newBoot, cycle: 2381, at: '2026-08-19T14:35:10.000000Z' }),
  false,
));

scenarios.push(await runScenario(
  'same boot newer cycle is accepted',
  feed({ boot: newBoot, cycle: 2382, at: '2026-08-19T14:35:48.478380Z' }),
  feed({ boot: newBoot, cycle: 2383, at: '2026-08-19T14:36:20.000000Z' }),
  true,
));

const diagnostic = {
  checked_at: new Date().toISOString(),
  pass: scenarios.every(s => s.pass),
  source: SOURCE_PATH,
  implementation: 'actual RoomState.putLatest class extracted and executed with fake Durable Object storage',
  invariant: 'newer feed timestamp/boot may reset cycle; stale older boot may never win merely by numeric cycle',
  scenarios,
};
fs.writeFileSync(OUT_PATH, JSON.stringify(diagnostic, null, 2) + '\n');
console.log(JSON.stringify(diagnostic, null, 2));
process.exit(diagnostic.pass ? 0 : 1);
