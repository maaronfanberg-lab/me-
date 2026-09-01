const RAW_BASE = "https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/experiments/emily-olivia-society/";
const VIEWER_SOURCE = RAW_BASE + "viewer.html";
const SNAPSHOT_SOURCE = RAW_BASE + "replay/community_session.json";
const STREAM_SOURCE = RAW_BASE + "replay/community_session.jsonl";

// Tombstone the old Durable Object generator. Existing alarms from the retired
// Cloudflare conversation stop themselves after this deployment; no model is
// called and no synthetic Emily/Olivia messages can be created here.
export class Community {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }

  async alarm() {
    const state = (await this.ctx.storage.get("state")) || {};
    state.running = false;
    state.retired = true;
    state.updated_at = new Date().toISOString();
    await this.ctx.storage.put("state", state);
    await this.ctx.storage.deleteAlarm();
  }

  async fetch() {
    await this.alarm();
    return text("Retired duplicate generator. This endpoint is read-only now.", 410);
  }
}

async function upstream(url) {
  const response = await fetch(url + "?t=" + Date.now(), {
    headers: { "user-agent": "emily-olivia-read-only-viewer" },
    cf: { cacheTtl: 0, cacheEverything: false }
  });
  if (!response.ok) {
    return new Response("Upstream replay unavailable", {
      status: 502,
      headers: { "cache-control": "no-store" }
    });
  }
  return response;
}

function text(body, status = 200, contentType = "text/plain; charset=utf-8") {
  return new Response(body, {
    status,
    headers: {
      "content-type": contentType,
      "cache-control": "no-store",
      "access-control-allow-origin": "*"
    }
  });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/" || url.pathname === "/viewer") {
      const source = await upstream(VIEWER_SOURCE);
      if (!source.ok) return source;
      return text(await source.text(), 200, "text/html; charset=utf-8");
    }

    if (url.pathname === "/state") {
      const source = await upstream(SNAPSHOT_SOURCE);
      if (!source.ok) return source;
      return text(await source.text(), 200, "application/json; charset=utf-8");
    }

    if (url.pathname === "/stream") {
      const source = await upstream(STREAM_SOURCE);
      if (!source.ok) return source;
      return text(await source.text(), 200, "application/x-ndjson; charset=utf-8");
    }

    if (url.pathname === "/start" || url.pathname === "/stop") {
      return text("Retired duplicate generator. Emily + Olivia run only through the Stanford Community workflow.", 410);
    }

    return text("Not found", 404);
  }
};
