import worker, { RoomState } from "./index.js";
import { LeviathanSignalStore, handleLeviathanSignal } from "./leviathan-signal.js";
import { SaraExperimentState, handleSaraLive } from "./sara-live.js";

export { RoomState, LeviathanSignalStore, SaraExperimentState };

const ALLEN_KEY_SHA256 = "c72f439977bc05b63b4cb8427dd958d78e564856e2e070aa8137fb7bdd295e18";
const ALLEN_KEY_BUILD = "20260820-current";
const LEVIATHAN_SIGNAL_BUILD = "20260821-v1";
const SARA_LIVE_BUILD = "20260822-v1";

function bearer(request) {
  const value = request.headers.get("authorization") || "";
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}
async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(value)));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
function constantTimeHexEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
async function allenFingerprintAuthorized(request) {
  const token = bearer(request);
  if (!token) return { ok: false, token: "" };
  const fingerprint = await sha256Hex(token);
  return { ok: constantTimeHexEqual(fingerprint, ALLEN_KEY_SHA256), token };
}
async function markedHealth(request, env, ctx) {
  const response = await worker.fetch(request, env, ctx);
  if (!response.ok) return response;
  const body = await response.json();
  return new Response(JSON.stringify({...body,allenKeyBuild:ALLEN_KEY_BUILD,leviathanSignalBuild:LEVIATHAN_SIGNAL_BUILD,saraLiveBuild:SARA_LIVE_BUILD}),{status:response.status,headers:response.headers});
}

async function handleAuthenticatedSaraTurn(request, env, ctx) {
  const authUrl = new URL(request.url);
  authUrl.pathname = "/api/participant/pending";
  authUrl.search = "";
  const authRequest = new Request(authUrl.toString(), {
    method: "GET",
    headers: { authorization: request.headers.get("authorization") || "" },
  });
  const authResponse = await worker.fetch(authRequest, env, ctx);
  if (!authResponse.ok) {
    let detail = "unauthorized";
    try {
      const body = await authResponse.json();
      detail = String(body?.detail || body?.error || detail);
    } catch {}
    return new Response(JSON.stringify({error:"unauthorized",detail}),{status:401,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"}});
  }
  const result = await env.SARA_EXPERIMENT.getByName("main").appendTurn(await request.json());
  return new Response(JSON.stringify(result),{status:result?.accepted?202:400,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","access-control-allow-origin":"*"}});
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") return markedHealth(request, env, ctx);
    if (url.pathname.startsWith("/api/leviathan/")) return handleLeviathanSignal(request, env);
    if (url.pathname === "/api/sara/turn" && request.method === "POST") return handleAuthenticatedSaraTurn(request, env, ctx);
    if (url.pathname.startsWith("/api/sara/")) return handleSaraLive(request, env);
    const allenPath = url.pathname === "/api/allen/auth" || url.pathname === "/api/allen";
    if (allenPath) {
      const auth = await allenFingerprintAuthorized(request);
      if (auth.ok) {
        const proxiedEnv = new Proxy(env,{get(target,prop,receiver){if(prop === "ROOM_ALLEN_KEY") return auth.token;return Reflect.get(target,prop,receiver);}});
        return worker.fetch(request, proxiedEnv, ctx);
      }
    }
    return worker.fetch(request, env, ctx);
  },
};
