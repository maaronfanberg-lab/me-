# Room viewer live-refresh repair — research gate (2026-08-19)

## Observed problem

The Room engine is still publishing fresh cognition beats to `main` roughly every 30–40 seconds, while the Pages viewer can load the retained transcript but then fail to visibly advance at the same cadence. Inspection of `room/index.html` shows two reliability costs on every refresh cycle: live freshness waits on several network candidates together, and when the merged transcript changes the viewer rebuilds the full retained transcript (currently up to 1,000 messages). History refresh is also coupled to the live refresh promise.

## Research question

What is the smallest client-side change that preserves the comprehensive retained transcript while making live turns advance independently of slow history/network work on mobile browsers?

## Sources and dates

Checked 2026-08-19:

- WHATWG Fetch Living Standard: https://fetch.spec.whatwg.org/
- MDN JavaScript performance guidance: https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Performance/JavaScript
- MDN `DocumentFragment`: https://developer.mozilla.org/en-US/docs/Web/API/DocumentFragment

Repository evidence: current `room/index.html`, `room/feed.json`, and recent Room cognition commits.

## Findings supporting the change

1. Fetch requests are independently abortable, so a fast live-source request can have a short timeout without being coupled to slower history retrieval.
2. Repeated large DOM replacement is unnecessary for an append-only conversation. New live message ids can be deduplicated and appended while the existing transcript remains in place.
3. Retained history and live freshness serve different purposes and should not share one blocking promise.
4. A `DocumentFragment` remains suitable for the one-time initial transcript build; later turns can be appended in small batches.

## Contradictory / limiting evidence

- Rendering 1,000 messages once can still cost time on older phones, but the user explicitly wants the retained record visible. The larger avoidable cost is rebuilding it repeatedly.
- Polling cannot create updates faster than the Room publishes them.
- Cloudflare relay availability can vary, so GitHub Raw remains a fallback.

## 10-level gate

1. Observed problem — PASS: viewer symptom exists while repository beats continue.
2. Foundational evidence — PASS: standard browser fetch/DOM mechanisms.
3. Current evidence — PASS: current Fetch standard and current MDN guidance checked.
4. Natural-behavior evidence — N/A: no conversational behavior changes.
5. Mechanism evidence — PASS: decouple live fetch from history and append unseen message ids.
6. Competing explanations — PASS: fresh commits/feed timestamps rule out a frozen Room.
7. Replication/correction/limitations — PASS WITH LIMITATION: mobile/network variability remains; fallbacks stay in place.
8. Context transfer — PASS: viewer-only change.
9. Implementation mapping — PASS: `room/index.html` live polling/render path only.
10. Post-change validation — REQUIRED: retained history loads, live beat/new turns advance without reload, failed fetches keep chat, manual refresh is non-destructive.

## Implementation mapping

- Make live polling independent of retained-history loading.
- Prefer a fresh Cloudflare relay; fall back to GitHub Raw and then Pages snapshot only when needed.
- Build retained transcript once, then append only unseen live message ids.
- Keep current messages on any fetch failure.
- Refresh immediately on `pageshow` and foreground return.

## Pre-change baseline

Retained history loads and Room commits advance, but the viewer may not visibly advance until reopened.

## Validation criteria

1. Initial retained transcript remains available.
2. New Room turns appear without page reload.
3. Beat/status advances as the live feed advances.
4. Slow history retrieval cannot block live updates.
5. Failed live requests never clear existing messages.
6. Manual refresh keeps the transcript visible.

## Post-change result

Pending live Pages deployment and user validation.
