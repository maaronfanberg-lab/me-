# Little World Lab

A fresh, isolated sandbox for testing sustained multi-agent behavior with a local Falcon/BitNet model.

This experiment does **not** import or modify The Room, Emily/Olivia runtime state, or personal/family data. It only mirrors the already-confirmed localhost BitNet HTTP contract: `GET /health` and `POST /v1/chat/completions`.

## What exists in v1

- 8 fictional agents in **Cedar Hollow** with traits, private goals, energy, private episodic memory, and rule-backed relationships.
- 6 connected locations with visible local resources.
- Environmental incidents that change the world without prescribing a story or dialogue.
- A model boundary where Falcon proposes exactly one structured action.
- An engine that validates and resolves actions. Free-form model text cannot directly mutate world state.
- Closed v1 actions: `move`, `talk`, `help`, `work`, `rest`, `observe`.
- Dialogue only between co-located agents. Talk text is observable memory but does not mechanically alter relationship scores.
- Lightweight private-memory retrieval using recency, importance, and lexical overlap.
- Near-repeat and repeated-action guards so one model loop cannot consume the run forever.
- Seeded per-tick scheduling so deterministic test runs are reproducible without permanently favoring the same first actor.
- Append-only `events.jsonl`, per-tick `metrics.jsonl`, final `metrics.json`, and resumable `checkpoint.json`.
- A deterministic `StubBackend` for CI. Stub behavior is an engine test fixture, **not** behavioral evidence.
- A standard-library `BitNetBackend` compatible with the existing localhost OpenAI-style server contract.

## Run the deterministic smoke simulation

From this directory:

```bash
python living_world.py --backend stub --ticks 30 --actors-per-tick 2 --seed 7 --output runs/stub-7
```

The output directory contains:

```text
events.jsonl
metrics.jsonl
metrics.json
checkpoint.json
```

## Run with Falcon / BitNet

Start a compatible BitNet `llama-server` separately. By default the lab expects:

```text
http://127.0.0.1:8080/health
http://127.0.0.1:8080/v1/chat/completions
```

Then run:

```bash
python living_world.py --backend bitnet --ticks 30 --actors-per-tick 2 --seed 7 --output runs/falcon-7
```

Optional overrides:

```bash
export LIVING_WORLD_MODEL_URL=http://127.0.0.1:8080/v1/chat/completions
export LIVING_WORLD_MODEL_NAME=community-bitnet
```

The backend sends a system message and one compact JSON user payload. The model sees only the acting agent's identity/goals, current local observation, relationships already established by engine rules, and retrieved private memories. It does not receive the global world state or another agent's private memories.

## Resume a run

```bash
python living_world.py --backend stub --resume runs/stub-7/checkpoint.json --ticks 10 --output runs/stub-7-resumed
```

For a real Falcon run, use `--backend bitnet` instead.

## Tests

```bash
python -m unittest discover -s tests -v
```

The first test suite checks deterministic replay, invalid-action containment, co-location rules, private-memory isolation, local incident visibility, non-mechanical talk, checkpoint round-tripping, and repetition rejection.

## What the metrics mean

The metrics are engineering diagnostics: action diversity, location diversity, interaction-pair count, rejection/error counts, talk count, and exact repeated-utterance rate. They are useful for comparing runs and spotting loops.

They are **not** measures of human realism, consciousness, personhood, or social validity. A fluent little town can still be a very convincing pile of statistical wallpaper. Multiple seeded Falcon runs and explicit interventions are required before calling a behavioral pattern emergent.

## Design evidence

The implementation follows the repository's research-first rule. See:

- `docs/research/little-world-lab-2026-09-05.md`
- Park et al., *Generative Agents: Interactive Simulacra of Human Behavior* (UIST 2023 / arXiv:2304.03442)
- Google DeepMind Concordia's separation of entities, engine, observation, scheduling, and resolution
- Recent literature warning that generative-agent believability is not the same as operational validity

Claude Sonnet 5 was also used through the repository's read-only oracle bridge as an independent architecture reviewer before implementation. Its most useful recommendations incorporated here were: keep the model as proposer rather than state authority, preserve private/local observations, use deterministic CI, keep scheduling reproducible without fixed-priority artifacts, make malformed/repetitive proposals observable rather than silently correcting them, and keep dialogue from mechanically rewriting social state.

## Deliberate v1 limits

- No claim of human-population validity.
- No semantic embedding model yet; memory retrieval stays auditable and stdlib-only.
- No free-form model-generated world mutation.
- No external web access for agents.
- No automatic huge-model download in GitHub Actions.
- No scripted story outcome and no canned fallback dialogue in real-model mode.
