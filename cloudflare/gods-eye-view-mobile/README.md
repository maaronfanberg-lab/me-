# Earth Signal on Cloudflare

Earth Signal is the calm, public-data wrapper around the MIT-licensed upstream project `bilawalsidhu/gods-eye-view`.

The wrapper intentionally does **not** vendor a stale upstream copy. Its build clones the current upstream `main`, applies Earth Signal's live-data and presentation policy, installs the locked dependencies, runs the upstream Vite build, then adds mobile/PWA assets.

## Live-data policy

Earth Signal does not present generated or simulated observations as live conditions.

The static Cloudflare Pages build currently verifies and supports these direct public feeds:

- **USGS earthquakes** — official 24-hour GeoJSON feed, refreshed by the upstream layer every 60 seconds.
- **ADSB.lol aircraft** — public ADS-B API, converted into the upstream flight-layer state-vector shape by the wrapper.

The upstream street-traffic layer normally falls back to animated simulated vehicles when TomTom's server-side proxy is unavailable. This static wrapper does not ship that private proxy, so Earth Signal replaces the traffic layer with an inert `UNAVAILABLE` implementation and hides its control instead of drawing synthetic cars.

Other upstream features that require private/server-side credentials remain unavailable until their proxy routes are explicitly ported to a Cloudflare Worker. A failed or missing feed should surface as unavailable/degraded rather than being replaced by fabricated data.

## Cloudflare Pages settings

- Production branch: `main`
- Root directory: `cloudflare/gods-eye-view-mobile`
- Build command: `npm run build`
- Build output directory: `dist`
- Node version: `24.14.0`

## Map configuration

`GOOGLE_MAPS_API_KEY` is optional in Earth Signal. If present, the wrapper uses Google Photorealistic 3D Tiles. If absent or unavailable, it keeps the keyless globe visible instead of aborting startup.

If you configure a Google Maps key, restrict it by HTTP referrer and API in Google Cloud because the browser must receive it.

`CESIUM_ION_TOKEN` remains optional for upstream features that use Cesium ion.

Do not put private server keys into client-prefixed environment variables.

## iPhone use

Open the deployed Cloudflare URL in Safari. The wrapper adds safe-area handling, touch-friendly sizing, a web-app manifest and standalone Home Screen mode. In Safari choose Share → Add to Home Screen.

## Build invariants

The build fails rather than silently weakening the data contract if:

- the upstream earthquake layer no longer contains the official USGS feed or its 60-second refresh seam;
- the ADSB.lol aircraft bridge can no longer be applied; or
- the Earth Signal traffic replacement no longer reports itself unavailable and detection-empty.

The upstream cinematic scope mask and surveillance-style presentation are disabled/hidden by this wrapper; the underlying data-layer architecture remains upstream-compatible.

## Licensing

Upstream application code is MIT licensed. Preserve upstream attribution and comply separately with the licenses/terms of third-party datasets, map tiles and API providers used by the project.
