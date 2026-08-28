# Live Earth Oracle Mk II research record — 2026-08-28

## Objective
Expand the Live Earth Oracle from nine to fourteen independently updating public streams without introducing API keys, browser-exposed secrets, or a dependency on the production Room state path.

## Knowledge gaps checked before implementation
1. Whether candidate sources are genuinely current/near-real-time rather than static datasets.
2. Whether the interfaces are browser-addressable and machine-readable without credentials.
3. Expected update cadence and schema shape.
4. CORS/runtime risk and whether one source failure can be contained.
5. Whether any source has a known migration/deprecation horizon.

## Sources selected
- NOAA CO-OPS Portland, Maine station 8418150. NOAA documents machine-to-machine APIs for present observations. The station exposes water-level and meteorological products.
- NOAA NDBC station 44007. NDBC publishes realtime standard meteorological flat files over HTTPS; current records include wind, wave height, pressure, air temperature and water temperature.
- USGS Instantaneous Values service, site 01022500 (Narraguagus River at Cherryfield, Maine). The service returns near-real-time streamflow/gage-height data in JSON and explicitly supports browser CORS. USGS states the legacy Water Services host is planned for decommissioning in early 2027, so the endpoint is isolated in one function for later migration.
- NOAA SWPC OVATION latest aurora JSON. The SWPC JSON index publishes `ovation_aurora_latest.json` as a current machine-readable product.
- Open-Meteo Air Quality API. It exposes current PM2.5, ozone and UV fields without an API key for non-commercial use. These are model-derived CAMS fields, not direct local sensor observations, so the UI labels them as a model field.

## Existing sources retained
Yahoo market data through the existing Cloudflare bridge, Coinbase BTC-USD WebSocket, ADSB.lol aircraft, Where The ISS At, USGS earthquakes, NOAA Kp, NOAA solar wind, Open-Meteo weather and GitHub commit activity.

## Reliability changes
- Every polled source now executes through a per-stream `guarded()` lock. A slow request cannot overlap with the next scheduled request for that same feed.
- Every fetch still has an AbortController timeout and cache bypass.
- Each source retains independent LIVE / STALE / ERROR state and last-good data.
- Coinbase remains event-driven and has reconnect handling.
- Visibility return triggers a refresh rather than waiting for all timers.
- The aggregate Ω uses whatever numeric factors are available; no single source is required.

## Cadences
- ISS: 5 s
- aircraft: 12 s
- equity market: 15 s
- earthquakes, Kp, solar wind, weather, tide, buoy: 60 s
- GitHub: 65 s
- aurora: 120 s
- air quality and river: 300 s
- Bitcoin: event-driven WebSocket

These are polling cadences, not claims that each upstream observation changes at that frequency.

## Limitations / blockers deliberately contained
- NDBC is a text feed rather than JSON; parsing uses its published header row and treats `MM` as missing.
- Browser CORS policy can still change on any public provider. If a provider blocks a browser request, only that card enters ERROR/STALE.
- NOAA OVATION is a forecast/analysis product, not a direct aurora camera measurement.
- Open-Meteo/CAMS air quality is model-derived and updates much slower than the dashboard poll interval.
- USGS Water Services must be migrated before its announced 2027 retirement.
- The Planetary Nonsense Index remains satire. Real measurements do not make the synthetic weighting scientifically meaningful.

## Validation gate
The Oracle validator was expanded from 9 to 14 required stream configurations and now verifies the five new endpoint families plus the existing sources. It parses inline JavaScript with Node `vm.Script`, checks timeout/error/stale/reconnect/visibility behavior, and now also requires the per-stream overlap guard.

## Implementation mapping
- `apps/live-earth-oracle.html`: Mk II UI, five new streams, overlap guard, fourteen-stream aggregate.
- `scripts/validate_live_earth_oracle.mjs`: fourteen-stream/source/reliability validation.
- No production Room state, cognition or relay files changed.
