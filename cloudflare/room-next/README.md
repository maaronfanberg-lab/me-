# Room Next

A clean-sheet social simulation. This project does **not** import state, code, feeds, prompts, memories, or workflows from the existing Room.

## Design goal

Make four persistent people feel distinct because they have different private histories, interests, goals, and reasons to participate — not because a post-generation filter tries to make four mandatory answers look different.

## Architecture

- **WorldAgent**: one Cloudflare Agent/Durable Object named `room-next-main`. It owns only public reality: the scene, public transcript, open/closed conversation episode, and recent contribution ground.
- **CharacterAgent**: four separate persistent Agent instances (`room-next-sarah`, `room-next-mara`, `room-next-owen`, `room-next-jules`). Each owns private memories, reflections, goals, familiarity, and cooldown state.
- **Speaker arbitration**: the world asks each character for a cheap private drive score. Only the strongest candidates are offered a chance to act. Direct address matters; recent speakers are penalized; cooldowns matter.
- **Optional action**: a selected character may `speak`, `silence`, or `leave`. Silence is not treated as a failure.
- **Bounded conversations**: a human-started episode allows at most eight agent actions. Autonomous episodes are shorter. Idle conversations close.
- **Private retrieval**: a character retrieves only a few personally relevant memories for its own inference. Other characters never receive those memories.
- **Reflection**: after several of its own actions, a character privately distills experience into a few higher-level insights and a possible new goal.
- **Autonomy**: a Cloudflare Cron wakes the world once per minute. When the room is quiet, most ticks do nothing. Occasionally one character may initiate.
- **Model**: Workers AI, defaulting to `@cf/meta/llama-3.3-70b-instruct-fp8-fast`, configurable with the `MODEL` Worker variable.

## Influences

The architecture borrows the useful structural ideas rather than copying implementations:

- **Generative Agents**: persistent memory, relevance/recency retrieval, reflection, planning.
- **AI Town**: conversations are explicit episodes that can start and end; agents do not endlessly talk.
- **SOTOPIA**: private goals and information asymmetry; agents may act or do nothing rather than all sharing an omniscient state.
- **Concordia**: a central world/game-master owns public reality while agents own their own cognition.

## Why this is separate

The existing Room grew around a four-speaker mandatory beat and increasingly complex anti-echo boundaries. Room Next starts from the opposite invariant: **nobody speaks unless they have a reason to contribute**.

The architecture check rejects accidental dependencies on the old Room.

## Local validation

```bash
npm install
npm run check
npm run dry-run
```

## Cloudflare resources

`wrangler.jsonc` creates two new SQLite-backed Durable Object classes and a new Worker named `room-next`. It also binds Workers AI and a one-minute Cron trigger.

The expected workers.dev hostname for the existing account is:

`https://room-next.dfp6k69dw5.workers.dev/`

## Owner input

`POST /api/say` accepts `{ "text": "...", "target": "room|sarah|mara|owen|jules" }`.

If the Worker secret `ROOM_NEXT_WRITE_KEY` is configured, the UI stores the key only in browser localStorage and sends it as a Bearer token. If no key is configured, the beta accepts same-Worker writes without authentication; configure the secret before sharing the URL publicly.

## Public API

- `GET /` — mobile-first viewer/composer
- `GET /health` — non-secret deployment/architecture status
- `GET /api/state` — public world state only
- `POST /api/say` — human turn
- `POST /api/tick` — owner/manual autonomous tick

Private character memory is never returned from the public API.
