# Fast Oracle feed reliability fix — 2026-08-28

Problem: several browser-direct telemetry endpoints can fail independently because of CORS, upstream response shape, or transient network behavior. The market feed is more reliable because it already passes through the Cloudflare Worker.

Decision: route the browser-polled HTTP telemetry through the existing Cloudflare Worker using a fixed-source whitelist. This avoids generic proxy/SSRF behavior while centralizing CORS, timeouts, and JSON parsing.

Sources proxied: ADSB.lol aircraft, WhereTheISS, NOAA solar-wind speed, NOAA solar magnetic field, NOAA planetary 1-minute K index, NOAA GOES X-ray flux. Coinbase WebSocket and Wikimedia EventStreams remain direct push streams.

The worker exposes `/api/fast-signal?source=...`; aircraft additionally accepts bounded latitude/longitude. The browser receives normalized JSON with the upstream payload under `payload`, plus `source` and `fetchedAt` metadata.

Reliability goal: if the browser can reach the Worker, it no longer needs each upstream host to allow GitHub Pages directly. Individual feed failures still remain isolated and become STALE/ERROR without breaking the rest of the predictor.
