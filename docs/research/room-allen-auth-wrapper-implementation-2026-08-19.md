# Allen auth wrapper implementation delta — 2026-08-19

> **Status: SUPERSEDED BEFORE FINAL PRODUCTION VALIDATION.** The original one-shot source repair completed after this wrapper experiment was prepared. The wrapper was therefore removed and Wrangler was restored to `src/index.js`, which now contains the same hash-fallback mechanism and passed the repository simulator. This note is retained only as an audit record of the temporary fallback path.

## Why the implementation mapping temporarily changed

The previously planned one-shot GitHub Actions source patch had not yet published a visible repair commit when this fallback was prepared. Rather than keep adding automation around a large, already-working Worker file, a smaller temporary implementation was tested as a new Worker entry module that intercepted only `/api/allen/auth` and `POST /api/allen`, then delegated every other request to the existing `src/index.js` Worker unchanged.

This preserved the evidence-backed mechanism from `room-allen-auth-fallback-2026-08-19.md`: a high-entropy bearer token checked against a committed SHA-256 verifier, while an existing `ROOM_ALLEN_KEY` remained a compatible first path. The plaintext bearer token was never committed.

## Temporary change boundary

- `cloudflare/room-worker/src/index-allen.js` was briefly added.
- Wrangler `main` was briefly changed from `src/index.js` to `src/index-allen.js`.
- The wrapper re-exported the existing `RoomState` Durable Object class.
- All non-Allen requests delegated to the existing Worker.

The wrapper and entrypoint change were removed once the original validated source patch became visible on `main`.

## Pre-deploy simulator

The exact proposed wrapper was executed locally with a stub of the existing Worker boundary. It passed six checks:

1. verifier-backed auth works with no `ROOM_ALLEN_KEY`;
2. wrong key returns 401;
3. missing key returns 401 rather than 503;
4. existing `ROOM_ALLEN_KEY` remains compatible;
5. verifier-backed `POST /api/allen` queues the Allen text;
6. a non-Allen route delegates to the underlying Worker.

## Final production path

The production path is again `cloudflare/room-worker/src/index.js`. Its one-shot repair recorded a red pre-change baseline and green post-change run in `room-allen-auth-fallback-2026-08-19.md`. Final production validation remains the live unauthenticated `/api/allen/auth` transition from `503 allen-key-not-configured` to `401 unauthorized`, with `/health` remaining healthy.
