# Fast Oracle: remove flaky comparison feeds — 2026-08-29

## Observed problem
The live Fast Nonsense Predictor repeatedly showed missing or non-loading data across several comparison cards. Direct user observation on 2026-08-29 reported missing earthquake and solar activity data, followed by many additional cards failing to load. Code inspection showed the page independently connects from the browser to USGS, NOAA SWPC, Hacker News Firebase, RIPE RIS Live, and RIPE Atlas, in addition to Wikimedia, Coinbase, and the market Worker.

## Research question
Does removing the unreliable non-essential comparison feeds improve dashboard reliability without changing R or the core market-comparison experiment?

## Sources and dates
- Direct user observation, 2026-08-29: multiple comparison cards not loading.
- `apps/live-earth-oracle.html`, inspected 2026-08-29: browser makes independent HTTP/WebSocket connections to USGS, NOAA SWPC, Hacker News Firebase, RIPE RIS Live, RIPE Atlas, Wikimedia, Coinbase, and the market Worker.
- USGS Earthquake Hazards Program GeoJSON feed documentation, current 2026.
- NOAA Space Weather Prediction Center product services, current 2026.
- RIPE Atlas Streaming API documentation, current 2026.

## Findings that support the change
The flaky sources are comparison-only. They do not participate in the current restored Wikimedia six-feature R engine. Removing their cards and network activity therefore does not alter R. It reduces independent browser network dependencies and removes blank/error cards that currently degrade the usable dashboard.

## Contradictory / limiting evidence
Removing the feeds reduces the breadth of simultaneous non-market comparisons. Earthquake, geomagnetic, Hacker News, BGP, and RIPE Atlas comparisons will no longer be available in the browser until a more reliable ingestion path is deployed. This change improves operational simplicity at the cost of comparison diversity.

## 10-level gate
1. Observed problem: PASS. Repeated direct user reports and current code inspection.
2. Foundational evidence: LIMITED / not central. This is a reliability/interface simplification, not a behavioral model change.
3. Current evidence: PASS. Current source endpoints and browser architecture were inspected.
4. Natural-behavior evidence: N/A.
5. Mechanism evidence: PASS. Fewer independent browser connections means fewer independent failure points and removes known failing cards.
6. Competing explanations: PASS. Individual source outages, format changes, CORS, mobile browser lifecycle, and undeployed Worker changes can each contribute. Removal avoids depending on distinguishing them for the current UI.
7. Replication/correction/limitations: PASS with limitation that source diversity decreases.
8. Context transfer: PASS. The change applies directly to this GitHub Pages browser app.
9. Implementation mapping: PASS. Remove `quake`, `kp`, `hn`, `bgp`, and `atlas` from `cfg`; stop starting or polling their fetch/socket functions; keep target market, Coinbase crypto/order pressure, Wikimedia R, NQ benchmark, prediction, and correlations.
10. Post-change validation: PENDING deployment. Success = no removed cards appear; no requests are initiated for their sources; R formula and Wikimedia seed behavior remain unchanged; market/crypto/Wikimedia cards continue updating.

## Pre-change baseline
The dashboard could display ERROR/STALE/blank states for multiple non-essential external comparison cards. R itself was intended to use only Wikimedia.

## Proposed implementation mapping
Trim the active comparison set to TARGET, BTC, ETH, SOL, DOGE, LTC, LINK, AVAX, BCH, XRP, ORDER PRESSURE, and WIKI EDITS. Leave the six-feature Wikimedia R calculation untouched. Leave the NQ benchmark panel untouched.

## Validation criteria
- Removed comparison cards do not render.
- Their polling/WebSocket startup functions are not called.
- R still reports the restored Wikimedia six-feature engine.
- Wikimedia reconnect watchdog remains active.
- Target market, Coinbase crypto, order pressure, and NQ benchmark code remains active.

## Post-change result
Pending deployment and live observation.
