import { BubbleState, cleanId } from "./bubble-state-terminal.js";

const ISSUER = "https://token.actions.githubusercontent.com";
const DEFAULT_AUDIENCE = "room-live-mirror";
const DEFAULT_REPOSITORY = "maaronfanberg-lab/me-";
const DEFAULT_ALLOWED_REFS = "refs/heads/main";

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

function authConfig(env) {
  const allowedRefs = String(env?.GITHUB_ALLOWED_REFS || DEFAULT_ALLOWED_REFS)
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  return {
    audience: String(env?.GITHUB_WORKFLOW_AUDIENCE || DEFAULT_AUDIENCE),
    repository: String(env?.GITHUB_EXPECTED_REPOSITORY || DEFAULT_REPOSITORY),
    allowedRefs,
  };
}

async function verifyGitHubToken(token, env) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("malformed-token");
  const header = decodeJwtJson(parts[0]);
  const claims = decodeJwtJson(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new Error("unexpected-token-header");

  const jwks = await getJwks();
  let jwk = (jwks.keys || []).find((item) => item.kid === header.kid);
  if (!jwk) {
    jwksCache = null;
    const refreshed = await getJwks();
    jwk = (refreshed.keys || []).find((item) => item.kid === header.kid);
  }
  if (!jwk) throw new Error("signing-key-not-found");

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
  if (!verified) throw new Error("bad-token-signature");

  const now = Math.floor(Date.now() / 1000);
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  const config = authConfig(env);
  if (claims.iss !== ISSUER) throw new Error("wrong-token-issuer");
  if (!audiences.includes(config.audience)) throw new Error("wrong-token-audience");
  if (claims.repository !== config.repository) throw new Error("wrong-repository");
  if (!config.allowedRefs.includes(claims.ref)) throw new Error("wrong-branch");
  if (!claims.exp || claims.exp < now - 5) throw new Error("expired-token");
  if (claims.nbf && claims.nbf > now + 30) throw new Error("token-not-active");
  return claims;
}

async function requireGitHub(request, env) {
  const token = bearer(request);
  if (!token) throw new Error("missing-token");
  return verifyGitHubToken(token, env);
}

function simIdFrom(url, body = null) {
  return cleanId(body?.sim_id || url.searchParams.get("sim_id"));
}

export async function handleBubbleApi(request, env) {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/api/bubble/")) return null;

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

  try {
    await requireGitHub(request, env);
  } catch (error) {
    return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
  }

  try {
    if (url.pathname === "/api/bubble/start" && request.method === "POST") {
      const body = await request.json();
      const simId = simIdFrom(url, body);
      if (!simId) return json({ error: "invalid-sim-id" }, 400);
      const stub = env.BUBBLE.getByName(simId);
      return json({ sim_id: simId, ...(await stub.initialize(body || {})) }, 200);
    }

    if (url.pathname === "/api/bubble/status" && request.method === "GET") {
      const simId = simIdFrom(url);
      if (!simId) return json({ error: "invalid-sim-id" }, 400);
      const result = await env.BUBBLE.getByName(simId).status();
      return json({ sim_id: simId, ...result }, result.status === "missing" ? 404 : 200);
    }

    if (url.pathname === "/api/bubble/task" && request.method === "GET") {
      const simId = simIdFrom(url);
      const node = Number(url.searchParams.get("node"));
      if (!simId || !Number.isInteger(node)) return json({ error: "invalid-task-request" }, 400);
      return json({ sim_id: simId, ...(await env.BUBBLE.getByName(simId).task(node)) });
    }

    if (url.pathname === "/api/bubble/submit" && request.method === "POST") {
      const body = await request.json();
      const simId = simIdFrom(url, body);
      const node = Number(body?.node);
      if (!simId || !Number.isInteger(node)) return json({ error: "invalid-submit-request" }, 400);
      const result = await env.BUBBLE.getByName(simId).submit(node, body?.stamp || {}, body?.result || {});
      return json({ sim_id: simId, ...result }, result.accepted === false && result.reason === "invalid-result" ? 400 : 200);
    }

    return json({ error: "not-found" }, 404);
  } catch (error) {
    return json({ error: "bubble-api-error", detail: String(error?.message || error) }, 400);
  }
}

export { BubbleState };
