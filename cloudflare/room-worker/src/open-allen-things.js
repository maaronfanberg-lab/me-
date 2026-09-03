import { DurableObject } from "cloudflare:workers";
import base, { RoomState } from "./open-allen.js";

export { RoomState };

const ISSUER = "https://token.actions.githubusercontent.com";
const EXPECTED_AUDIENCE = "room-live-mirror";
const EXPECTED_REPOSITORY = "maaronfanberg-lab/me-";
const EXPECTED_REF = "refs/heads/main";
const MAX_QUEUE = 48;
const MAX_TERM = 80;
const RESULT_TTL_MS = 30 * 60 * 1000;
const LEASE_MS = 90 * 1000;

let oidcMetadataCache = null;
let jwksCache = null;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
    },
  });
}

function bearer(request) {
  const value = request.headers.get("authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}

function decodeBase64Url(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

function decodeJwtJson(value) {
  return JSON.parse(new TextDecoder().decode(decodeBase64Url(value)));
}

async function getOidcMetadata() {
  if (oidcMetadataCache) return oidcMetadataCache;
  const response = await fetch(`${ISSUER}/.well-known/openid-configuration`, {
    headers: { accept: "application/json" },
  });
  if (!response.ok) throw new Error(`OIDC metadata ${response.status}`);
  oidcMetadataCache = await response.json();
  return oidcMetadataCache;
}

async function getJwks() {
  if (jwksCache) return jwksCache;
  const metadata = await getOidcMetadata();
  const response = await fetch(metadata.jwks_uri, { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`OIDC JWKS ${response.status}`);
  jwksCache = await response.json();
  return jwksCache;
}

async function verifyGitHubTokenWithKey(parts, claims, jwk) {
  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const verified = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    decodeBase64Url(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!verified) throw new Error("Bad token signature");

  const now = Math.floor(Date.now() / 1000);
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (claims.iss !== ISSUER) throw new Error("Wrong token issuer");
  if (!audiences.includes(EXPECTED_AUDIENCE)) throw new Error("Wrong token audience");
  if (claims.repository !== EXPECTED_REPOSITORY) throw new Error("Wrong repository");
  if (claims.ref !== EXPECTED_REF) throw new Error("Wrong branch");
  if (!claims.exp || claims.exp < now - 5) throw new Error("Expired token");
  if (claims.nbf && claims.nbf > now + 30) throw new Error("Token not active");
  return claims;
}

async function verifyGitHubToken(token) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("Malformed token");
  const header = decodeJwtJson(parts[0]);
  const claims = decodeJwtJson(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new Error("Unexpected token header");

  const jwks = await getJwks();
  let jwk = (jwks.keys || []).find((item) => item.kid === header.kid);
  if (!jwk) {
    jwksCache = null;
    const refreshed = await getJwks();
    jwk = (refreshed.keys || []).find((item) => item.kid === header.kid);
  }
  if (!jwk) throw new Error("Signing key not found");
  return verifyGitHubTokenWithKey(parts, claims, jwk);
}

async function requireGitHub(request) {
  const token = bearer(request);
  if (!token) throw new Error("missing-token");
  return verifyGitHubToken(token);
}

function cleanTerm(value) {
  const term = String(value || "").replace(/\s+/g, " ").trim();
  if (!term || term.length > MAX_TERM || /[\u0000-\u001f\u007f]/.test(term)) return null;
  return term;
}

function cleanContext(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => cleanTerm(String(item || "").slice(0, MAX_TERM)))
    .filter(Boolean)
    .slice(0, 12);
}

export class ThingsState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
  }

  async enqueue(term, context, ip) {
    const now = Date.now();
    const rateKey = `thingsRate:${String(ip || "unknown").slice(0, 80)}`;
    let rate = (await this.ctx.storage.get(rateKey)) || { window: now, count: 0, last: 0 };
    if (now - rate.window > 60 * 60 * 1000) rate = { window: now, count: 0, last: 0 };
    if (now - rate.last < 1200) return { accepted: false, reason: "rate-limited", retryAfterMs: 1200 - (now - rate.last) };
    if (rate.count >= 120) return { accepted: false, reason: "hourly-limit" };
    rate.count += 1;
    rate.last = now;
    await this.ctx.storage.put(rateKey, rate, { expirationTtl: 3700 });

    const queue = (await this.ctx.storage.get("thingsQueue")) || [];
    const normalized = term.toLocaleLowerCase("en-US");
    const duplicate = queue.find((job) => job.normalized === normalized && now - job.createdAt < 5 * 60 * 1000);
    if (duplicate) return { accepted: true, id: duplicate.id, status: duplicate.leaseUntil > now ? "working" : "queued", deduped: true };
    if (queue.length >= MAX_QUEUE) return { accepted: false, reason: "queue-full" };

    const job = {
      id: crypto.randomUUID(),
      term,
      normalized,
      context,
      createdAt: now,
      leaseUntil: 0,
    };
    queue.push(job);
    await this.ctx.storage.put("thingsQueue", queue);
    return { accepted: true, id: job.id, status: "queued", queued: queue.length };
  }

  async pending(limit = 4) {
    const now = Date.now();
    const queue = (await this.ctx.storage.get("thingsQueue")) || [];
    const selected = [];
    for (const job of queue) {
      if (selected.length >= Math.max(1, Math.min(Number(limit) || 4, 8))) break;
      if (!job.leaseUntil || job.leaseUntil <= now) {
        job.leaseUntil = now + LEASE_MS;
        selected.push({ id: job.id, term: job.term, context: job.context, createdAt: job.createdAt });
      }
    }
    if (selected.length) await this.ctx.storage.put("thingsQueue", queue);
    return { jobs: selected, queued: queue.length };
  }

  async complete(id, result, error = "") {
    const queue = (await this.ctx.storage.get("thingsQueue")) || [];
    const job = queue.find((item) => item.id === id);
    const kept = queue.filter((item) => item.id !== id);
    if (kept.length !== queue.length) await this.ctx.storage.put("thingsQueue", kept);

    const record = {
      id,
      term: job?.term || result?.term || "",
      status: error ? "error" : "done",
      result: error ? null : result,
      error: String(error || "").slice(0, 500),
      completedAt: Date.now(),
      expiresAt: Date.now() + RESULT_TTL_MS,
    };
    await this.ctx.storage.put(`thingsResult:${id}`, record, { expirationTtl: Math.ceil(RESULT_TTL_MS / 1000) + 60 });
    return { accepted: true, id, status: record.status, queued: kept.length };
  }

  async result(id) {
    const record = await this.ctx.storage.get(`thingsResult:${id}`);
    if (record) return record;
    const now = Date.now();
    const queue = (await this.ctx.storage.get("thingsQueue")) || [];
    const job = queue.find((item) => item.id === id);
    if (!job) return { id, status: "missing" };
    return { id, term: job.term, status: job.leaseUntil > now ? "working" : "queued", createdAt: job.createdAt };
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/things/")) return base.fetch(request, env, ctx);

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "authorization,content-type",
          "access-control-max-age": "86400",
        },
      });
    }

    const stub = env.THINGS.getByName("main");

    if (url.pathname === "/api/things/enrich" && request.method === "POST") {
      try {
        const body = await request.json();
        const term = cleanTerm(body?.term);
        if (!term) return json({ error: "invalid-term", max: MAX_TERM }, 400);
        const context = cleanContext(body?.context);
        const ip = request.headers.get("cf-connecting-ip") || "unknown";
        const result = await stub.enqueue(term, context, ip);
        return json(result, result.accepted ? 202 : result.reason === "rate-limited" || result.reason === "hourly-limit" ? 429 : 503);
      } catch (error) {
        return json({ error: "invalid-request", detail: String(error?.message || error) }, 400);
      }
    }

    if (url.pathname === "/api/things/result" && request.method === "GET") {
      const id = String(url.searchParams.get("id") || "").trim();
      if (!/^[0-9a-f-]{20,50}$/i.test(id)) return json({ error: "invalid-id" }, 400);
      const result = await stub.result(id);
      return json(result, result.status === "missing" ? 404 : 200);
    }

    if (url.pathname === "/api/things/pending" && request.method === "GET") {
      try {
        await requireGitHub(request);
        return json(await stub.pending(4));
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }

    if (url.pathname === "/api/things/complete" && request.method === "POST") {
      try {
        await requireGitHub(request);
        const body = await request.json();
        const id = String(body?.id || "").trim();
        if (!/^[0-9a-f-]{20,50}$/i.test(id)) return json({ error: "invalid-id" }, 400);
        return json(await stub.complete(id, body?.result || null, body?.error || ""));
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }

    return json({ error: "not-found" }, 404);
  },
};
