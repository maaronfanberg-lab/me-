# Allen auth production validation — 2026-08-19

This is the production result for `room-allen-auth-fallback-2026-08-19.md`.

At `2026-08-19T21:42:15.942488Z`, the repository's existing external Worker status job reached the live `room-live-mirror` Worker successfully and requested `/api/allen/auth` with no credential.

Observed live result:

- transport: success
- HTTP: 401
- JSON error: `unauthorized`
- `allen_auth_fallback_live`: true
- diagnostic state: `fallback-capable-worker-live`

The pre-change production baseline for the same unauthenticated route was HTTP 503 with `allen-key-not-configured`. The change from 503 to 401 is the predefined deployment invariant proving that the Worker build containing the source-level high-entropy-token hash fallback is live.

Repository simulation had already passed fallback authentication without `ROOM_ALLEN_KEY`, wrong-token rejection, missing-token 401, legacy Cloudflare-secret compatibility, and verifier-backed Allen queue submission. The plaintext fallback bearer token was not committed to GitHub; only its SHA-256 verifier is present in source.

No Room cognition, conversation semantics, participant labeling, feed ordering, or Durable Object queue behavior was changed by this auth repair.
