# God's Eye View Mobile on Cloudflare

This folder is a Cloudflare Pages deployment wrapper for the MIT-licensed upstream project `bilawalsidhu/gods-eye-view`.

It intentionally does **not** vendor a stale copy of the upstream repository. The Cloudflare build clones the current upstream `main`, installs its locked dependencies, runs the upstream Vite build, then injects iPhone/mobile overrides and PWA/Home Screen support.

## Cloudflare Pages settings

Use this repository and set:

- Production branch: `main` after this PR is merged
- Root directory: `cloudflare/gods-eye-view-mobile`
- Build command: `npm run build`
- Build output directory: `dist`
- Node version: `24.14.0`

## Required environment variable

`GOOGLE_MAPS_API_KEY`

The upstream project requires a Google Maps API key with Map Tiles API enabled. The key is deliberately client-exposed by the upstream app, so restrict it by HTTP referrer and API in Google Cloud.

## Useful optional environment variables

- `CESIUM_ION_TOKEN`
- `OPENSKY_AUTH_MODE=anon` for aircraft without OpenSky credentials

The upstream project also supports server-side credentials such as OpenAI, AISStream, NASA FIRMS, TomTom and authenticated OpenSky. Those routes are implemented as Vite development-server middleware upstream and are not automatically converted into Cloudflare Worker routes by this static Pages wrapper.

That means the first Cloudflare deployment gives you the core browser app and any client-capable/keyless layers that do not depend on `/api/*`. Features backed by private server credentials should remain disabled until their proxy routes are explicitly ported to a Worker. Do not put private server keys into client-prefixed variables.

## iPhone use

Open the deployed Cloudflare URL in Safari. The wrapper adds safe-area handling, touch-friendly control sizing, reduced small-screen panel sizes, a web-app manifest and standalone Home Screen mode. In Safari choose Share → Add to Home Screen.

## Licensing

Upstream application code is MIT licensed. Preserve upstream attribution and comply separately with the licenses/terms of third-party datasets, map tiles and API providers used by the project.
