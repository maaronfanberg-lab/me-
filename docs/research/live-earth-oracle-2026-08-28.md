# Live Earth Oracle research record — 2026-08-28

## Observed problem
The existing Unified Market Oracle uses a small number of periodically refreshed inputs. The requested experiment is a much broader continuously changing display using genuinely live or near-live public telemetry, while preventing one failed upstream source from breaking the entire page.

## Research question
Can a static GitHub Pages application combine several public real-time/near-real-time feeds at source-appropriate cadences without adding credentials or coupling the experiment to the production Room relay?

## Sources checked
- Coinbase Exchange WebSocket documentation, 2026-08-28: https://docs.cdp.coinbase.com/exchange/websocket-feed/overview and https://docs.cdp.coinbase.com/exchange/websocket-feed/channels . Public market-data WebSocket; ticker emits updates as matches occur.
- USGS real-time earthquake feeds, 2026-08-28: https://earthquake.usgs.gov/earthquakes/feed/ . GeoJSON summary feeds; past-hour/day feeds are refreshed on a short cadence.
- NOAA Space Weather Prediction Center products, 2026-08-28: https://services.swpc.noaa.gov/products/ and https://services.swpc.noaa.gov/json/rtsw/ . Public machine-readable planetary K-index and real-time solar-wind products.
- Open-Meteo API documentation, 2026-08-28: https://open-meteo.com/en/docs . Coordinate-based current temperature, humidity, pressure and wind variables.
- Where The ISS At API documentation, checked 2026-08-28: https://wheretheiss.at/w/developer . Public ISS position/state endpoint.
- ADSB.lol API documentation, checked 2026-08-28: https://api.adsb.lol/docs . Public aircraft endpoint by latitude/longitude/radius.
- Existing repository implementation: `cloudflare/room-worker/src/open-allen.js` already exposes `/api/market` as a CORS-enabled Yahoo chart bridge. Reuse avoids adding a second market proxy.
- Existing GitHub Pages workflow: `.github/workflows/pages.yml` deploys repository contents after app changes.

## Findings supporting the change
1. A browser can consume Coinbase public ticker data through WebSocket without credentials, giving the experiment a genuinely event-driven stream rather than only timers.
2. USGS, NOAA, Open-Meteo, ISS and ADSB sources provide compact public JSON suitable for independent browser fetches.
3. Different feeds have different natural update rates, so a single global polling interval would either be wasteful or stale.
4. The existing market Worker already solves the Yahoo browser-access problem and should be reused rather than modifying Room state code.
5. Static hosting is sufficient if each upstream source is isolated and failures are represented as source status rather than thrown through a shared request chain.

## Contradictory / limiting evidence
- Public APIs can change schemas, CORS behavior, quotas or availability without coordination with this repository.
- ADSB.lol explicitly describes its public service as community infrastructure; production consumers should expect possible endpoint evolution.
- GitHub unauthenticated REST calls are rate limited, so repository activity is polled at 65 seconds rather than aggressively.
- “Current weather” is not sensor-by-sensor telemetry; it is the newest Open-Meteo current-condition value available for the requested coordinate.
- The equity bridge uses Yahoo chart data at one-minute granularity; polling it faster does not create sub-minute exchange ticks.
- The combined Oracle index is intentionally non-scientific. The source observations are real; the normalization, weighting and inferred market target have no predictive evidence.

## 10-level gate
1. **Observed problem:** passed; narrow current app and single-source-failure risk are directly observable from its architecture.
2. **Foundational evidence:** not materially applicable to the joke model; standard resilient client/data-stream design is the relevant mechanism.
3. **Current evidence:** passed through current first-party/public-network API documentation above.
4. **Natural-behavior evidence:** not applicable; no human behavior is being modeled.
5. **Mechanism evidence:** passed; independent scheduling, WebSocket events, timeout isolation, last-good state and stale detection map directly to reliability goals.
6. **Competing explanations:** upstream failure may be provider, CORS, quota, connectivity or schema drift; UI therefore reports failure rather than assigning a single cause.
7. **Replication/correction/limitations:** limitations are recorded above; fallback parsing exists for NOAA solar wind.
8. **Context transfer:** passed; implementation is a standalone Pages app and does not alter Room cognition/state behavior.
9. **Implementation mapping:** one new standalone HTML app; existing market bridge reused unchanged; each feed owns cadence/status/factor; no production relay modifications.
10. **Post-change validation:** validate file deployment, JavaScript load, independent source statuses, WebSocket reconnect behavior, manual refresh, ticker reload, and that a failed source does not suppress other cards.

## Implementation mapping
`apps/live-earth-oracle.html` contains nine isolated streams: equity market, BTC-USD WebSocket, local aircraft, ISS, USGS earthquakes, NOAA Kp, NOAA solar wind, local Open-Meteo weather and latest GitHub commit. Each source updates its own card and bounded factor. The displayed Ω is a bounded aggregate of only currently available numeric factors. The ceremonial market target is capped to ±8% from the fetched market price.

## Pre-change baseline
The prior Oracle had five principal exogenous variables plus manual controls, one-minute market polling, and no true push stream or broad telemetry dashboard.

## Validation criteria
- Page deploys through existing Pages workflow.
- BTC ticker receives public WebSocket updates and automatically reconnects after closure while visible.
- Market ticker can be changed without reloading the page.
- Location permission updates aircraft/weather coordinates; denial falls back to Portland, Maine.
- Each fetch has a timeout and a failed feed enters ERROR/STALE independently.
- Successful values visually update and add bounded history sparklines.
- Ω recomputes using available factors and never requires all sources to be healthy.
- No source failure can throw out of the scheduler and stop unrelated jobs.
- No credentials or private data are added to the repository.

## Post-change result
Pending deployment/browser validation at the time this record was created. Update after merge if deployment or a public source reveals a blocking incompatibility.
