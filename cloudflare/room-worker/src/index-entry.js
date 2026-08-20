import worker, { RoomState } from "./index.js";

export { RoomState };

// One-way fingerprint of Allen's private browser key. The key itself is never
// committed. This entry wrapper only substitutes the presented token into the
// existing ROOM_ALLEN_KEY path when its SHA-256 fingerprint matches.
const ALLEN_KEY_SHA256 = "c72f439977bc05b63b4cb8427dd958d78e564856e2e070aa8137fb7bdd295e18";

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

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const allenPath = url.pathname === "/api/allen/auth" || url.pathname === "/api/allen";
    if (allenPath) {
      const auth = await allenFingerprintAuthorized(request);
      if (auth.ok) {
        const proxiedEnv = new Proxy(env, {
          get(target, prop, receiver) {
            if (prop === "ROOM_ALLEN_KEY") return auth.token;
            return Reflect.get(target, prop, receiver);
          },
        });
        return worker.fetch(request, proxiedEnv, ctx);
      }
    }
    return worker.fetch(request, env, ctx);
  },
};
