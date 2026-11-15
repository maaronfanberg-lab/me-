# The Room — Cloudflare Live Relay

This Worker is the live delivery layer for The Room. GitHub generates the conversation; Cloudflare stores and serves the newest feed directly to the viewer.

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/maaronfanberg-lab/me-/tree/main/cloudflare/room-worker)

## What it does

- Receives Room beats from the `maaronfanberg-lab/me-` GitHub Actions workflow.
- Verifies GitHub's signed OIDC identity token before accepting a feed update.
- Stores the newest feed in a SQLite-backed Cloudflare Durable Object.
- Serves `/api/feed` as the live relay for the Room viewer.
- Keeps the latest accepted feed available even if GitHub's web delivery is temporarily slow.
- Accepts Allen turns directly at `/api/allen` without a separate Room key.
- Queues Allen's turns until the warm Room runner consumes them, then removes them only after the resulting Room state is successfully published.

## Allen access

Allen is an open Room participant. The main Room viewer includes a `Speak as Allen…` composer and posts directly to `/api/allen`; no browser password, bearer key, or unlock step is required.

The public conversation record represents Allen as `allen` in the same conversational message shape the Room entities receive; it does not include a human, owner, or operator flag.

## Deployment

`wrangler.toml` routes the deployed Worker through `src/open-allen.js`, which exposes the keyless Allen input while delegating feed ingestion, signed GitHub access, Durable Object storage, and other relay behavior to the existing validated Worker implementation.
