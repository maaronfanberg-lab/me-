# Allen auth fallback — research gate (2026-08-19)

## Observed problem

The deployed `room-live-mirror` Worker now serves the current Allen interface, but a direct live request to `/api/allen/auth` returns `503 {"error":"allen-key-not-configured"}`. This isolates the remaining failure to Allen credential availability in the deployed Worker environment; the route and current Worker source are live.

The user has explicitly asked not to perform more Cloudflare dashboard work. There is no connected Cloudflare write tool available in the current ChatGPT session, while GitHub write access and the repository-to-Cloudflare automatic deployment path are working.

## Research question

What is the smallest change that lets Allen authenticate without requiring a mutable Cloudflare secret, while keeping the private bearer token itself out of the public repository and preserving the existing Cloudflare-secret path if it becomes available again?

## Sources and dates

Checked 2026-08-19:

- Cloudflare Workers Secrets documentation: https://developers.cloudflare.com/workers/configuration/secrets/
- Cloudflare Wrangler configuration documentation: https://developers.cloudflare.com/workers/wrangler/configuration/
- Cloudflare Wrangler Workers command documentation: https://developers.cloudflare.com/workers/wrangler/commands/workers/
- NIST FIPS 180-4 Secure Hash Standard: https://www.nist.gov/publications/secure-hash-standard

## Findings supporting the change

1. Cloudflare explicitly warns not to put sensitive values in plaintext Wrangler `vars`; deployed secrets are the preferred mechanism when an account write path is available.
2. Current Cloudflare documentation says ordinary Wrangler deployment does not intentionally delete Worker secrets. The observed live `503` therefore establishes an environment-state mismatch, but not its dashboard-side cause. Repeatedly changing unrelated deployment settings would not be evidence-based.
3. SHA-256 is a standardized secure hash. For a machine-generated, high-entropy bearer token, storing only a SHA-256 verifier in public source avoids storing the bearer token itself. This is not a human password and is therefore not relying on low-entropy password hashing.
4. The existing Worker can preserve `ROOM_ALLEN_KEY` as the first authentication path and add the hash verifier as a fallback. That keeps compatibility with a future Cloudflare secret while removing the current runtime dependency.

## Contradictory / limiting evidence

- A public verifier permits offline guesses. This is acceptable only because the fallback token is generated with high entropy; a short memorable password would not be appropriate.
- Bearer credentials remain bearer credentials: anyone who obtains the private token can speak as Allen until the verifier is rotated.
- This fallback does not diagnose why the Cloudflare secret is absent. It deliberately avoids another dashboard investigation because the live failure is already isolated and the user requested a GitHub-only recovery path.
- The existing browser console stores the bearer token in browser storage. That is outside the scope of this reliability repair and should be reviewed separately if the threat model expands.

## 10-level gate

1. **Observed problem — PASS.** Live `/api/allen/auth` returns `allen-key-not-configured`; current `/allen` UI is deployed.
2. **Foundational evidence — PASS.** Authentication uses a high-entropy bearer secret; SHA-256 is a standardized secure hash primitive.
3. **Current evidence — PASS.** Current Cloudflare first-party docs were checked for secret/deploy behavior.
4. **Natural-behavior evidence — NOT APPLICABLE.** This changes credential verification only, not Room conversation behavior.
5. **Mechanism evidence — PASS.** The mechanism removes the missing-environment-secret dependency by validating a private token against a one-way verifier.
6. **Competing explanations — PASS.** Manual secret recreation is viable but requires Cloudflare write access the user has declined to keep doing; unrelated deployment changes are unsupported.
7. **Replication/correction/limitations — PASS.** Live API behavior is reproducible; verifier/offline-guess and bearer-token limitations are explicit.
8. **Context transfer — PASS.** No cognitive, discourse, persistence, or participant identity semantics change.
9. **Implementation mapping — PASS.** Modify only Allen authorization in `cloudflare/room-worker/src/index.js`; preserve optional `ROOM_ALLEN_KEY`; add a source-level hash fallback and route awaits.
10. **Post-change validation — PENDING BEFORE IMPLEMENTATION.** The same source simulator must fail on the current Worker source, then pass after the patch. Production must stop returning `allen-key-not-configured` before the private token is handed to the user.

## Pre-change baseline

Expected simulator failure on current source: no `ALLEN_KEY_SHA256` verifier exists and Allen auth requires `env.ROOM_ALLEN_KEY`.

Observed production baseline: unauthenticated `/api/allen/auth` returns HTTP 503 with `allen-key-not-configured` rather than HTTP 401 `unauthorized`.

## Validation criteria

1. The same simulator is red against the current source and green after the patch.
2. With no `ROOM_ALLEN_KEY`, a token matching the configured SHA-256 verifier authenticates as Allen.
3. A wrong token remains HTTP 401.
4. If `ROOM_ALLEN_KEY` is present, the existing secret path still authenticates.
5. `POST /api/allen` accepts the verifier-backed token and continues to queue `speaker: "allen"` with no human/operator metadata.
6. No plaintext Allen bearer token is committed to GitHub.
7. After automatic deployment, `/api/allen/auth` without credentials returns 401 rather than `allen-key-not-configured` 503, proving the fallback-capable build is live.

## Repository validation result

The same `scripts/room_allen_auth_sim.mjs` invariant was run immediately before and after the source change. Before the patch it failed because the source had no hash fallback. After the patch it passed all five checks: fallback auth without an environment secret; wrong-token rejection; missing-token 401; compatibility with an existing `ROOM_ALLEN_KEY`; and verifier-backed Allen POST queueing.

The plaintext fallback token was not written to the repository or workflow. Only its SHA-256 verifier is committed.

Production validation remains: wait for the automatic Cloudflare deployment, then confirm unauthenticated `/api/allen/auth` returns 401 rather than `allen-key-not-configured` 503 before releasing the private token to the user.
