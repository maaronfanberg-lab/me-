# Room Pages live-viewer deployment fix — research gate (2026-08-19)

## Observed problem

The live Room viewer on GitHub Pages remains on an older build and can sit indefinitely on “Loading the Room…”. `apps/sarah-room.html` on `main` is now a redirect to `room/`, while `.github/workflows/pages.yml` still unconditionally runs `python3 scripts/bake_room.py`. That bake script exits with an error when `apps/sarah-room.html` does not contain the legacy `__ROOM_SNAPSHOT_B64__` token. Therefore the current Pages job cannot reach the upload/deploy steps, leaving the previous Pages artifact active.

## Research question

What is the smallest reliability fix that allows both the legacy baked launcher and the current live redirect launcher to deploy without changing Room cognition or conversation behavior?

## Evidence and mechanism

- Direct repository inspection shows the current launcher contains no bake token and redirects to `../room/`.
- Direct repository inspection shows `bake_room.py` intentionally aborts when the token is absent.
- Direct repository inspection shows the Pages workflow runs the bake step before configuring/uploading/deploying Pages.
- This is a build-contract mismatch, not a runtime conversation problem.

## Competing explanations / limitations

Browser caching alone cannot explain the persistent old layout because the repository file on `main` is materially different from the deployed screen. A failed Pages deployment does explain why an older artifact continues to be served. This change does not alter data retention, Room generation, cognition, or Cloudflare relay behavior.

## 10-level gate

1. Observed problem — PASS: launcher/workflow/script contract inspected directly.
2. Foundational evidence — PASS / not behavior-dependent: standard fail-fast build sequencing.
3. Current evidence — PASS: repository’s current workflow and scripts are the operative implementation.
4. Natural-behavior evidence — NOT APPLICABLE: no human-conversation mechanism changes.
5. Mechanism evidence — PASS: absent token causes bake failure before deploy.
6. Competing explanations — PASS: stale browser cache considered but does not match current source/deployed-layout mismatch.
7. Replication/correction/limitations — PASS: condition is deterministic from current files.
8. Context transfer — PASS: deployment-only change.
9. Implementation mapping — PASS: make the bake step conditional on presence of the legacy token.
10. Post-change validation — REQUIRED: Pages job must complete and deployed Room must show the current five-participant/live-history viewer rather than the legacy four-person loading screen.

## Implementation mapping

Update `.github/workflows/pages.yml` so `bake_room.py` runs only when `apps/sarah-room.html` still contains `__ROOM_SNAPSHOT_B64__`. Otherwise continue directly to the normal Pages upload/deploy steps.

## Baseline

Current Pages artifact shows the older four-person viewer and can remain indefinitely on Loading.

## Success criteria

- Pages workflow completes successfully.
- `apps/sarah-room.html` redirects to the current `room/` viewer.
- Current viewer header includes Allen.
- Initial load resolves in seconds rather than minutes when at least one live/history source is reachable.
- No cognition or conversation-generation files are changed by this fix.
