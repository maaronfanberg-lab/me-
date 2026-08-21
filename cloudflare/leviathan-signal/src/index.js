import { DurableObject } from "cloudflare:workers";

const json = (data, status = 200, extra = {}) => new Response(JSON.stringify(data), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", ...extra }
});

function cors(origin, allowed) {
  if (origin !== allowed) return {};
  return {
    "access-control-allow-origin": allowed,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400",
    "vary": "Origin"
  };
}

function cleanText(v, max) {
  return String(v ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, max);
}

function validEmail(v) {
  const s = cleanText(v, 160);
  if (!s) return "";
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s) ? s : null;
}

export class LeviathanSignalStore extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ctx.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS interest (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        intent TEXT NOT NULL,
        email TEXT NOT NULL,
        comment TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
    `);
  }

  async fetch(request) {
    const u = new URL(request.url);
    if (request.method === "POST" && u.pathname === "/event") {
      const body = await request.json();
      this.ctx.storage.sql.exec(
        "INSERT INTO events(type, source, created_at) VALUES (?, ?, ?)",
        body.type, body.source, body.created_at
      );
      return json({ ok: true });
    }

    if (request.method === "POST" && u.pathname === "/interest") {
      const body = await request.json();
      this.ctx.storage.sql.exec(
        "INSERT INTO interest(intent, email, comment, source, created_at) VALUES (?, ?, ?, ?, ?)",
        body.intent, body.email, body.comment, body.source, body.created_at
      );
      return json({ ok: true });
    }

    if (request.method === "GET" && u.pathname === "/summary") {
      const counts = {};
      for (const row of this.ctx.storage.sql.exec(
        "SELECT type, COUNT(*) AS n FROM events WHERE source != 'deploy-smoke' GROUP BY type"
      )) counts[row.type] = Number(row.n);

      const intents = { yes: 0, maybe: 0, no: 0 };
      for (const row of this.ctx.storage.sql.exec(
        "SELECT intent, COUNT(*) AS n FROM interest WHERE source != 'deploy-smoke' GROUP BY intent"
      )) intents[row.intent] = Number(row.n);

      const total = Number([...this.ctx.storage.sql.exec(
        "SELECT COUNT(*) AS n FROM interest WHERE source != 'deploy-smoke'"
      )][0]?.n || 0);

      return json({ ok: true, events: counts, interest: { ...intents, total } });
    }

    return json({ ok: false, error: "not_found" }, 404);
  }
}

async function toStore(env, path, payload) {
  const id = env.SIGNALS.idFromName("leviathan-global");
  const stub = env.SIGNALS.get(id);
  return stub.fetch(new Request(`https://signals.internal${path}`, {
    method: path === "/summary" ? "GET" : "POST",
    headers: { "content-type": "application/json" },
    body: path === "/summary" ? undefined : JSON.stringify(payload)
  }));
}

export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    const origin = request.headers.get("origin") || "";
    const c = cors(origin, env.PUBLIC_ORIGIN);

    if (request.method === "OPTIONS") {
      if (origin !== env.PUBLIC_ORIGIN) return new Response(null, { status: 403 });
      return new Response(null, { status: 204, headers: c });
    }

    if (u.pathname === "/health" && request.method === "GET") {
      return json({ ok: true, app: "leviathan-signal", version: "1" });
    }

    if (u.pathname === "/summary" && request.method === "GET") {
      const r = await toStore(env, "/summary");
      return new Response(r.body, { status: r.status, headers: { "content-type": "application/json; charset=utf-8" } });
    }

    if (origin !== env.PUBLIC_ORIGIN) return json({ ok: false, error: "origin_not_allowed" }, 403, c);

    if (request.method !== "POST" || (u.pathname !== "/event" && u.pathname !== "/interest")) {
      return json({ ok: false, error: "not_found" }, 404, c);
    }

    const len = Number(request.headers.get("content-length") || 0);
    if (len > 8192) return json({ ok: false, error: "too_large" }, 413, c);

    let raw;
    try { raw = await request.json(); }
    catch { return json({ ok: false, error: "bad_json" }, 400, c); }

    const source = cleanText(raw.source || "github-pages", 40) || "github-pages";
    const created_at = new Date().toISOString();

    if (u.pathname === "/event") {
      const type = cleanText(raw.type, 32);
      if (!["page_view", "power_on", "interest_click"].includes(type)) {
        return json({ ok: false, error: "bad_event" }, 400, c);
      }
      const r = await toStore(env, "/event", { type, source, created_at });
      return new Response(r.body, { status: r.status, headers: { "content-type": "application/json; charset=utf-8", ...c } });
    }

    const intent = cleanText(raw.intent, 12).toLowerCase();
    if (!["yes", "maybe", "no"].includes(intent)) return json({ ok: false, error: "bad_intent" }, 400, c);
    const email = validEmail(raw.email);
    if (email === null) return json({ ok: false, error: "bad_email" }, 400, c);
    const comment = cleanText(raw.comment, 600);

    const r = await toStore(env, "/interest", { intent, email, comment, source, created_at });
    return new Response(r.body, { status: r.status, headers: { "content-type": "application/json; charset=utf-8", ...c } });
  }
};
