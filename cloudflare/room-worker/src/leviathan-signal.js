import { DurableObject } from "cloudflare:workers";

const ALLOWED_ORIGIN = "https://maaronfanberg-lab.github.io";
const VALID_EVENTS = new Set(["page_view", "power_on", "interest_click"]);
const VALID_INTENTS = new Set(["yes", "maybe", "no"]);

function clean(value, max) {
  return String(value ?? "")
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .trim()
    .slice(0, max);
}

function email(value) {
  const valueClean = clean(value, 160);
  if (!valueClean) return "";
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valueClean) ? valueClean : null;
}

function cors(origin) {
  if (origin !== ALLOWED_ORIGIN) return {};
  return {
    "access-control-allow-origin": ALLOWED_ORIGIN,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400",
    vary: "Origin",
  };
}

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
    },
  });
}

export class LeviathanSignalStore extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ctx.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS leviathan_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS leviathan_interest (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        intent TEXT NOT NULL,
        email TEXT NOT NULL,
        comment TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
    `);
  }

  async recordEvent(type, source) {
    this.ctx.storage.sql.exec(
      "INSERT INTO leviathan_events(type, source, created_at) VALUES (?, ?, ?)",
      type,
      source,
      new Date().toISOString(),
    );
    return { ok: true };
  }

  async recordInterest(intent, emailValue, comment, source) {
    this.ctx.storage.sql.exec(
      "INSERT INTO leviathan_interest(intent, email, comment, source, created_at) VALUES (?, ?, ?, ?, ?)",
      intent,
      emailValue,
      comment,
      source,
      new Date().toISOString(),
    );
    return { ok: true };
  }

  async summary() {
    const events = { page_view: 0, power_on: 0, interest_click: 0 };
    for (const row of this.ctx.storage.sql.exec(
      "SELECT type, COUNT(*) AS n FROM leviathan_events WHERE source != 'deploy-smoke' GROUP BY type",
    )) {
      if (Object.hasOwn(events, row.type)) events[row.type] = Number(row.n || 0);
    }

    const interest = { yes: 0, maybe: 0, no: 0, total: 0 };
    for (const row of this.ctx.storage.sql.exec(
      "SELECT intent, COUNT(*) AS n FROM leviathan_interest WHERE source != 'deploy-smoke' GROUP BY intent",
    )) {
      if (Object.hasOwn(interest, row.intent)) interest[row.intent] = Number(row.n || 0);
    }
    interest.total = interest.yes + interest.maybe + interest.no;

    return { ok: true, events, interest };
  }
}

export async function handleLeviathanSignal(request, env) {
  const url = new URL(request.url);
  const origin = request.headers.get("origin") || "";
  const headers = cors(origin);

  if (request.method === "OPTIONS") {
    if (origin !== ALLOWED_ORIGIN) return new Response(null, { status: 403 });
    return new Response(null, { status: 204, headers });
  }

  if (url.pathname === "/api/leviathan/summary" && request.method === "GET") {
    const stub = env.LEVIATHAN_SIGNALS.getByName("global");
    return json(await stub.summary());
  }

  if (request.method !== "POST") return json({ ok: false, error: "not-found" }, 404, headers);
  if (origin !== ALLOWED_ORIGIN) return json({ ok: false, error: "origin-not-allowed" }, 403, headers);

  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > 8192) return json({ ok: false, error: "too-large" }, 413, headers);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "bad-json" }, 400, headers);
  }

  const source = clean(body?.source || "github-pages", 40) || "github-pages";
  const stub = env.LEVIATHAN_SIGNALS.getByName("global");

  if (url.pathname === "/api/leviathan/event") {
    const type = clean(body?.type, 32);
    if (!VALID_EVENTS.has(type)) return json({ ok: false, error: "bad-event" }, 400, headers);
    return json(await stub.recordEvent(type, source), 200, headers);
  }

  if (url.pathname === "/api/leviathan/interest") {
    const intent = clean(body?.intent, 12).toLowerCase();
    if (!VALID_INTENTS.has(intent)) return json({ ok: false, error: "bad-intent" }, 400, headers);
    const emailValue = email(body?.email);
    if (emailValue === null) return json({ ok: false, error: "bad-email" }, 400, headers);
    const comment = clean(body?.comment, 600);
    return json(await stub.recordInterest(intent, emailValue, comment, source), 200, headers);
  }

  return json({ ok: false, error: "not-found" }, 404, headers);
}
