# Room Dynamics Vault

This directory is an isolated experimental layer for persistent Room dynamics.

## Isolation contract

- Production remains on `main`.
- This experiment lives only on the `vault-room-dynamics` branch.
- Nothing in this directory writes `room/feed.json` or any production state.
- Nothing here calls Llama or any network service.
- No workflow is enabled for the vault yet.
- State evolution is deterministic for a given state, elapsed time, and event.

The branch was forked from production commit:

`b23b89f58a670c62a964ed843e989ba1bd4a19bd`

## First experimental model

Each Room entity gets a tiny bounded latent state. A tick performs:

1. analytic decay / oscillator evolution from elapsed time,
2. optional bounded event perturbation,
3. projection into ten observable features,
4. four regime logits,
5. softmax regime probabilities,
6. normalized entropy and state-change measurements,
7. a *recommendation* about whether the state is interesting enough to consider speech.

The engine never invokes speech itself. This keeps the expensive LLM path outside the dynamical core and gives us a hard safety boundary.

## Success criteria before any Llama integration

- repeated identical inputs are reproducible;
- all latent values remain finite and bounded;
- regime probabilities always sum to 1;
- entropy remains in [0, 1];
- long missed intervals can be advanced in one analytic step;
- no tick can write production data;
- no tick can create an LLM call;
- entity states can diverge from history and new events without runaway growth.

## Current status

Stage 1: isolated branch and inert deterministic dynamics core.
