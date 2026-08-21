import fs from 'node:fs';

const source = fs.readFileSync(new URL('../src/index.ts', import.meta.url), 'utf8');
const config = JSON.parse(fs.readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8'));

const forbidden = [
  'room/feed.json',
  'room/conversation.json',
  'cloudflare/room-worker',
  'scripts/room_engine',
  'scripts/room_expression_quality',
  'ROOM_QUALITY_REJECTION_EXIT',
];
for (const token of forbidden) {
  if (source.includes(token)) throw new Error(`Room Next must not depend on old Room token: ${token}`);
}
if (config.name !== 'room-next') throw new Error('Room Next must deploy as its own Worker');
if (!source.includes('"speak" | "silence" | "leave"')) throw new Error('silence/leave must remain first-class actions');
if (!source.includes('Math.random() > 0.34')) throw new Error('autonomous initiation must remain optional');
if (!source.includes('maxAgentTurns: 8')) throw new Error('human-started conversations must stay bounded');
if (!source.includes('WorldAgent') || !source.includes('CharacterAgent')) throw new Error('world and private character agents must remain separate');
console.log('ROOM NEXT ARCHITECTURE: GREEN — isolated world, private minds, optional speech, bounded conversations');
