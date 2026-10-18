# Spatial SoundCloud OAuth broker

SoundCloud currently requires a `client_secret` for authorization-code token exchange and refresh, even for mobile clients using PKCE. This Worker exists only to keep that secret out of the iPhone application.

It does **not** proxy audio. Once authenticated, the iPhone talks directly to the SoundCloud API and its streaming CDN.

## Configure

Register a SoundCloud API application and use this exact redirect URI unless you deliberately change both the Worker and iOS app:

```text
spatialsoundcloud://soundcloud/callback
```

Set the public client ID and the secret client secret in the Worker environment:

```bash
cd cloudflare/spatial-soundcloud-auth
npx wrangler secret put SOUNDCLOUD_CLIENT_ID
npx wrangler secret put SOUNDCLOUD_CLIENT_SECRET
```

`SOUNDCLOUD_REDIRECT_URI` is already declared in `wrangler.jsonc` because it is not secret.

Deploy with your normal Cloudflare workflow or locally with Wrangler. After deployment, replace the placeholder `SoundCloudBrokerBaseURL` in the iOS `Info.plist` with the Worker URL.

## Routes

- `GET /health` — liveness and configured/not-configured status; never returns credentials.
- `GET /config` — returns the public client ID, redirect URI, and SoundCloud authorization URL.
- `POST /oauth/exchange` — accepts `code`, `code_verifier`, and `redirect_uri`; adds the server-held client secret and exchanges the authorization code.
- `POST /oauth/refresh` — accepts the current refresh token and returns SoundCloud's replacement token payload.

All responses use `Cache-Control: no-store`. Never log request bodies for the exchange or refresh routes, because they contain credentials/tokens.
