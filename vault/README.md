# Room Dynamics Vault

This directory is an isolated experimental cognition layer for the Room.

## Isolation contract

- Production remains on `main`.
- This experiment lives only on `vault-room-dynamics`.
- Vault code reads `origin/main:room/feed.json` as a snapshot; it never edits that file.
- The vault does not invoke Llama, the relay, or any network service.
- `speech_requested` and `production_write_enabled` are hard-coded false in shadow reports.
- Candidate selection means only **would consider speaking**. It is telemetry, not permission to speak.
- The shadow workflow persists only `vault/runtime/shadow-state.json` and `vault/runtime/report.json`.
- Automatic persistence commits use `[skip ci]` so they do not recursively wake unrelated workflows.

The branch was forked from production commit:

`b23b89f58a670c62a964ed843e989ba1bd4a19bd`

## Dynamics

Each entity (`sarah`, `mara`, `owen`, `jules`) has a bounded eight-dimensional latent state seeded partly from its production genome. A shadow observation performs:

1. exact analytic damped-oscillator advancement across elapsed time;
2. bounded semantic impulses from new Room messages;
3. homeostatic contraction to prevent accumulation/saturation;
4. projection into ten observable signals;
5. four regime logits (`settled`, `exploratory`, `social`, `transition`);
6. softmax regime probabilities, entropy, and regime-change measurements;
7. bounded candidate selection with a global budget of one and per-entity cooldown;
8. compact directional state summaries suitable for a small LLM in a future phase.

## Ingestion and persistence safeguards

The v4 runner now handles experimental-data failure modes explicitly:

- corrupt state JSON recovers to a fresh envelope rather than crashing;
- v3 state migrates to v4 without discarding valid accumulated entity state;
- a damaged entity is repaired independently instead of resetting all four;
- genomes are finite-checked and clamped to [0, 1];
- malformed conversation elements are ignored and reported;
- missing message IDs receive deterministic synthetic IDs;
- duplicate IDs keep only their latest occurrence;
- a missing cursor after feed-window truncation uses recent-ID history instead of blind replay;
- message text and per-run backlog are bounded;
- future timestamps are capped at the observation time;
- clock and cycle regressions are reported;
- candidate selection is suppressed during bootstrap and cycle regression;
- cooldown falls back to observation count when source cycles are unavailable;
- state/report writes are atomic replacements.

## Semantic safeguards

Lexicon matches use word/phrase boundaries rather than raw substrings. Negated certainty such as `not sure` does not simultaneously create a strong confidence signal. An entity receives no positive impulse simply because its own prior speech is present in the feed, avoiding a self-reinforcing output loop.

The compact LLM adapter labels entropy specifically as `regime_entropy`, includes separation between the two strongest regimes, marks salient signals as `high` or `low`, sanitizes enumerated fields, and caps the entire state string at 480 characters.

## Current status

Stage 4: persistent passive shadow dynamics with hardened ingestion, deterministic bounded candidate selection, compact semantic summaries, live production-feed observation, and CI-enforced isolation. Llama invocation and public speech remain intentionally disabled.
