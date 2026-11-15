# Room viewer retained-history and refresh repair — 2026-08-19

## Observed problem

Direct user observation on iPhone: `apps/sarah-room.html` updates on open and sometimes while left open, but it does not show a comprehensive retained conversation record. Activating the viewer status/refresh control can make the visible conversation disappear and leave the page in a loading/retry state.

Code inspection established two concrete causes:

1. `scripts/build_room_feed.py` deliberately publishes only the last 160 messages into `room/feed.json`, while `room/conversation.json` retains a much larger transcript (currently bounded by the Room engine's retained-history limit).
2. `room/index.html` rendered directly from whichever live-feed candidate won the freshness race. A candidate with an empty/partial conversation could replace the existing DOM, and a forced refresh depended on several network sources before restoring a stable view.

## Research question

What is the smallest viewer-only reliability change that preserves fast live updates, exposes the larger retained transcript already available in the repository, and guarantees that a manual refresh never destroys the last successfully rendered conversation?

## Evidence and mechanism

This is an interface/data-loading defect rather than a human-conversation behavioral change. The strongest evidence is the repository's current implementation and the user's direct observation.

- `room/feed.json` is intentionally a lightweight live tail (160 messages).
- `room/conversation.json` is the canonical retained transcript used by the Room engine.
- The live viewer can therefore keep polling the small feed for freshness while loading retained history separately and merging the live tail by stable message id.
- DOM replacement should happen only after a complete successful render has been constructed off-screen. If refresh fails or returns no usable transcript, the previously rendered conversation should remain visible.
- All network reads require explicit timeouts so a manual refresh cannot remain in an indefinite loading state.

## Competing explanations / limitations

- This does not create an all-time archive. It exposes the full transcript that the Room currently retains; the engine itself still bounds retained conversation history. A true permanent archive would be a separate architectural change.
- A stale CDN/raw snapshot can still occur temporarily, so the viewer continues to compare several sources and keeps the newest successful state.
- Loading the retained transcript is heavier than loading the live feed, so history is cached in-browser and refreshed much less often than the live tail.

## 10-level gate

1. Observed problem — PASS: reproduced from user report plus code inspection.
2. Foundational evidence — PASS: standard non-destructive UI state preservation; no behavioral modeling involved.
3. Current evidence — PASS: current repository implementation inspected directly.
4. Natural-behavior evidence — N/A: no conversational behavior is altered.
5. Mechanism evidence — PASS: separate retained-history load + id merge + atomic DOM replacement.
6. Competing explanations — PASS: feed truncation and destructive replacement are directly visible in code.
7. Replication/correction/limitations — PASS: retained-history bound and network-staleness limits documented.
8. Context transfer — PASS: viewer-only change; Room cognition remains untouched.
9. Implementation mapping — PASS: `room/index.html` and legacy launcher cache-buster only.
10. Post-change validation — REQUIRED: verify retained message count is greater than live-tail count when history is available; verify manual refresh preserves existing messages during failed/slow requests; verify automatic live updates continue.

## Implementation

- `room/index.html`
  - loads `room/conversation.json` from GitHub Raw/Pages as retained history;
  - continues using the small live feed for freshness/status;
  - merges retained history and live tail by message id;
  - builds replacement chat content in a `DocumentFragment` and swaps only when complete;
  - preserves existing messages when a refresh fails or returns no usable conversation;
  - uses explicit fetch timeouts and disables the refresh button only during a forced refresh;
  - displays the retained-message count and source in the footer;
  - renders Allen consistently when present.
- `apps/sarah-room.html`
  - cache-buster advanced to `live-room-20260819a` so the repaired viewer is requested.

## Post-change result

Pending live GitHub Pages propagation and user validation.
