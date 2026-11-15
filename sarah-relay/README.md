# Sarah Private Relay

This Worker is the private remote-brain bridge for Sarah. The iPhone page handles Sarah's interface, microphone, ambient hearing, voice, and local continuity. This Worker keeps the OpenAI API key off the phone and calls the remote model securely.

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/maaronfanberg-lab/me-/tree/main/sarah-relay)

## Setup

1. Click **Deploy to Cloudflare** above.
2. Sign in or create a Cloudflare account.
3. When Cloudflare asks for `OPENAI_API_KEY`, paste your OpenAI API key. Do not put the key into Sarah's browser page or commit it to GitHub.
4. Finish deployment.
5. Copy the Worker URL Cloudflare gives you, for example `https://sarah-private-relay.<account>.workers.dev`.
6. Sarah's relay URL is that address plus `/chat`, for example `https://sarah-private-relay.<account>.workers.dev/chat`.
7. Open Sarah on your iPhone, open Settings, paste that `/chat` URL into **Private relay URL**, save, and tap **Test connection**.

## Health check

Open the Worker address with `/health` at the end. A working relay returns JSON indicating that the relay is alive.

## Privacy

The Worker only accepts Sarah chat requests from `https://maaronfanberg-lab.github.io` (plus local development origins). Requests to OpenAI use `store: false`. Sarah's browser-side history and continuity stay on the device unless included as context for a conversation turn.
