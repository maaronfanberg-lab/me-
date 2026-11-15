import { DurableObject } from "cloudflare:workers";

const ISSUER = "https://token.actions.githubusercontent.com";
const EXPECTED_AUDIENCE = "room-live-mirror";
const EXPECTED_REPOSITORY = "maaronfanberg-lab/me-";
const EXPECTED_REF = "refs/heads/main";
const ALLEN = "allen";
const MAX_TURN = 700;
const MAX_QUEUE = 50;
const ALLEN_KEY_SHA256 = "e53d0db863593fc618b4b764f70b31a5b9652931d8f8f7838a24cbd8cf87aa4d";

let oidcMetadataCache = null;
let jwksCache = null;

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      ...extraHeaders,
    },
  });
}

function html(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

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

async function allenAuthorized(request, env) {
  const token = bearer(request);
  if (!token) return false;
  const expected = String(env.ROOM_ALLEN_KEY || "");
  if (expected && token === expected) return true;
  return constantTimeHexEqual(await sha256Hex(token), ALLEN_KEY_SHA256);
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

async function verifyGitHubToken(token) {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("Malformed token");

  const header = decodeJwtJson(parts[0]);
  const claims = decodeJwtJson(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new Error("Unexpected token header");

  const jwks = await getJwks();
  const jwk = (jwks.keys || []).find((key) => key.kid === header.kid);
  if (!jwk) {
    jwksCache = null;
    const refreshed = await getJwks();
    const retryKey = (refreshed.keys || []).find((key) => key.kid === header.kid);
    if (!retryKey) throw new Error("Signing key not found");
    return verifyGitHubTokenWithKey(parts, claims, retryKey);
  }
  return verifyGitHubTokenWithKey(parts, claims, jwk);
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

async function requireGitHub(request) {
  const token = bearer(request);
  if (!token) throw new Error("missing-token");
  return verifyGitHubToken(token);
}

function validFeed(feed) {
  return Boolean(
    feed &&
      typeof feed === "object" &&
      feed.state &&
      Number.isFinite(Number(feed.state.cycle)) &&
      Array.isArray(feed.conversation) &&
      feed.minds &&
      feed.minds.entities,
  );
}

export class RoomState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
  }

  async putLatest(feed, sourceSha = "") {
    const incomingCycle = Number(feed?.state?.cycle || 0);
    const incomingBoot = String(feed?.state?.boot_id || "");
    const incomingStamp = Date.parse(feed?.generated_at || feed?.state?.last_run || "");
    const current = await this.ctx.storage.get("latest");
    const currentFeed = current?.feed || null;
    const currentCycle = Number(currentFeed?.state?.cycle || 0);
    const currentBoot = String(currentFeed?.state?.boot_id || "");
    const currentStamp = Date.parse(currentFeed?.generated_at || currentFeed?.state?.last_run || "");

    if (current) {
      const sameBoot = Boolean(incomingBoot && currentBoot && incomingBoot === currentBoot);
      const incomingHasStamp = Number.isFinite(incomingStamp);
      const currentHasStamp = Number.isFinite(currentStamp);

      // A cycle is monotonic only inside one Room boot. Never compare reset cycle
      // counters across boots as though they belonged to one global sequence.
      if (sameBoot && incomingCycle < currentCycle) {
        return { accepted: false, cycle: currentCycle, bootId: currentBoot, reason: "older-cycle" };
      }

      // Across boots, generated_at / last_run is the freshness authority. It also
      // prevents a replay from an older boot with a numerically larger cycle from
      // replacing the current feed.
      if (incomingHasStamp && currentHasStamp) {
        if (incomingStamp < currentStamp) {
          return { accepted: false, cycle: currentCycle, bootId: currentBoot, reason: "older-feed" };
        }
        if (incomingStamp === currentStamp && !sameBoot) {
          return { accepted: false, cycle: currentCycle, bootId: currentBoot, reason: "not-newer-boot" };
        }
      } else if (!sameBoot) {
        // A boot change without comparable timestamps is ambiguous; preserve the
        // known-good record rather than guessing from unrelated cycle counters.
        return { accepted: false, cycle: currentCycle, bootId: currentBoot, reason: "unverifiable-boot-change" };
      }
    }

    const record = {
      feed,
      receivedAt: new Date().toISOString(),
      sourceSha,
    };
    await this.ctx.storage.put("latest", record);
    return { accepted: true, cycle: incomingCycle, bootId: incomingBoot, receivedAt: record.receivedAt };
  }

  async getLatest() {
    return (await this.ctx.storage.get("latest")) || null;
  }

  async enqueueAllen(text) {
    const queue = (await this.ctx.storage.get("allenQueue")) || [];
    if (queue.length >= MAX_QUEUE) return { accepted: false, reason: "queue-full" };
    const turn = {
      id: crypto.randomUUID(),
      speaker: ALLEN,
      text,
      at: new Date().toISOString(),
    };
    queue.push(turn);
    await this.ctx.storage.put("allenQueue", queue);
    return { accepted: true, id: turn.id, at: turn.at, queued: queue.length };
  }

  async pendingAllen() {
    const queue = (await this.ctx.storage.get("allenQueue")) || [];
    return { messages: queue.slice(0, 20) };
  }

  async ackAllen(ids) {
    const wanted = new Set((Array.isArray(ids) ? ids : []).map(String));
    const queue = (await this.ctx.storage.get("allenQueue")) || [];
    const kept = queue.filter((turn) => !wanted.has(String(turn.id)));
    await this.ctx.storage.put("allenQueue", kept);
    return { acknowledged: queue.length - kept.length, queued: kept.length };
  }
}

const VIEWER = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#08090d"><title>The Room — Cloudflare Live</title><style>
html,body{margin:0;min-height:100%;background:#08090d;color:#f5f3ee;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{padding:0 12px 70px}.top{position:sticky;top:0;background:#08090df5;padding:calc(14px + env(safe-area-inset-top)) 2px 11px;border-bottom:1px solid #252b36;z-index:2}.title{font-size:24px;font-weight:850}.sub{font-size:11px;color:#a3a9b3;margin-top:4px}.status{margin-top:9px;font-size:12px;color:#e0bf79}.status.live{color:#98dfc8}.chat{max-width:760px;margin:14px auto}.beat{font-size:10px;color:#6f7783;text-align:center;margin:18px 0 10px}.msg{background:#11141b;border:1px solid #2b3240;border-radius:16px;padding:11px 13px;margin:0 0 10px}.who{font-size:10px;font-weight:800;letter-spacing:.1em;color:#d7c18a;margin-bottom:6px}.text{font-size:16px;line-height:1.45}.when{font-size:9px;color:#707887;margin-top:7px}.err{padding:24vh 18px;text-align:center;color:#a3a9b3;line-height:1.5}</style></head><body>
<div class="top"><div class="title">The Room</div><div class="sub">Sarah · Mara · Owen · Jules · Allen</div><div id="status" class="status">connecting…</div></div><main id="chat" class="chat"><div class="err">Opening the live Room…</div></main>
<script>(function(){var status=document.getElementById('status'),chat=document.getElementById('chat'),last='',busy=false;function tm(s){try{return new Date(s).toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}catch(e){return''}}function nm(x,m){return x.speaker==='allen'?'Allen':((m[x.speaker]&&m[x.speaker].name)||x.speaker||'')}function render(r){var f=r.feed||{},c=Array.isArray(f.conversation)?f.conversation:[],m=f.minds&&f.minds.entities||{},st=f.state||{},sig=c.length?String(c[c.length-1].id||'')+':'+c.length:'';var age=r.receivedAt?Math.max(0,Math.floor((Date.now()-Date.parse(r.receivedAt))/1000)):9999;status.className='status'+(age<15?' live':'');status.textContent=(age<15?'LIVE':'STALE')+' · beat '+(st.cycle||'—')+' · '+(st.beat_message_count||0)+' voices · '+age+'s';if(sig===last)return;last=sig;chat.innerHTML='';var start=Math.max(0,c.length-80),prev='';for(var i=start;i<c.length;i++){var x=c[i]||{},b=x.beat_id||'';if(b!==prev){var h=document.createElement('div');h.className='beat';h.textContent='BEAT '+(b?b.slice(-6):'—');chat.appendChild(h);prev=b}var d=document.createElement('div');d.className='msg';var w=document.createElement('div');w.className='who';w.textContent=nm(x,m);var t=document.createElement('div');t.className='text';t.textContent=x.text||'';var q=document.createElement('div');q.className='when';q.textContent=tm(x.at);d.appendChild(w);d.appendChild(t);d.appendChild(q);chat.appendChild(d)}if(c.length)window.scrollTo(0,document.body.scrollHeight)}async function refresh(){if(busy)return;busy=true;try{var r=await fetch('/api/feed?fresh='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);render(await r.json())}catch(e){status.className='status';status.textContent='relay unavailable';if(!last)chat.innerHTML='<div class="err">The Cloudflare relay is not receiving the Room yet.</div>'}finally{busy=false}}refresh();setInterval(refresh,2000);document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible')refresh()})})();</script></body></html>`;

const ALLEN_VIEWER = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#08090d"><title>Allen — The Room</title><style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#08090d;color:#f5f3ee;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{padding:0 12px 150px}.top{position:sticky;top:0;background:#08090df6;padding:calc(14px + env(safe-area-inset-top)) 2px 11px;border-bottom:1px solid #252b36;z-index:3}.title{font-size:24px;font-weight:850}.sub{font-size:11px;color:#a3a9b3;margin-top:4px}.status{margin-top:9px;font-size:12px;color:#e0bf79}.status.live{color:#98dfc8}.chat{max-width:760px;margin:14px auto}.beat{font-size:10px;color:#6f7783;text-align:center;margin:18px 0 10px}.msg{background:#11141b;border:1px solid #2b3240;border-radius:16px;padding:11px 13px;margin:0 0 10px}.msg.allen{border-color:#756338}.who{font-size:10px;font-weight:800;letter-spacing:.1em;color:#d7c18a;margin-bottom:6px}.text{font-size:16px;line-height:1.45}.when{font-size:9px;color:#707887;margin-top:7px}.lock{max-width:520px;margin:22vh auto 0;background:#11141b;border:1px solid #2b3240;border-radius:18px;padding:18px}.lock h2{margin:0 0 7px}.hint{font-size:12px;line-height:1.45;color:#9ca5b3;margin-bottom:12px}.keyrow{display:flex;gap:8px}.keyrow input{min-width:0;flex:1}.composer{position:fixed;left:0;right:0;bottom:0;z-index:4;background:#08090df8;border-top:1px solid #2b3240;padding:10px 12px calc(10px + env(safe-area-inset-bottom))}.composer-inner{max-width:760px;margin:auto;display:flex;gap:8px;align-items:flex-end}.composer textarea{flex:1;min-height:48px;max-height:150px;resize:vertical}.composer button,.keyrow button,.forget{white-space:nowrap}input,textarea{background:#11141b;color:#fff;border:1px solid #394150;border-radius:12px;padding:11px 12px;font:inherit;outline:none}button{border:1px solid #4a5364;background:#171d28;color:#fff;border-radius:12px;padding:11px 14px;font-weight:800}.send{background:#d3bd82;color:#111;border-color:#d3bd82}.send:disabled{opacity:.5}.mini{max-width:760px;margin:0 auto 8px;text-align:right}.forget{font-size:10px;padding:5px 8px;background:transparent;color:#7d8795;border-color:#2b3240}.hidden{display:none!important}</style></head><body>
<div id="lock" class="lock"><h2>Allen</h2><div class="hint">Enter your private Room key. It stays in this browser and is never placed in the conversation.</div><div class="keyrow"><input id="key" type="password" autocomplete="current-password" placeholder="Room key"><button id="unlock">Enter</button></div><div id="lockStatus" class="status"></div></div>
<div id="app" class="hidden"><div class="top"><div class="title">The Room</div><div class="sub">Sarah · Mara · Owen · Jules · Allen</div><div id="status" class="status">connecting…</div></div><main id="chat" class="chat"></main><div class="mini"><button id="forget" class="forget">forget key</button></div><div class="composer"><div class="composer-inner"><textarea id="turn" maxlength="700" placeholder="Speak as Allen…"></textarea><button id="send" class="send">Send</button></div></div></div>
<script>(function(){var lock=document.getElementById('lock'),app=document.getElementById('app'),keyInput=document.getElementById('key'),unlock=document.getElementById('unlock'),lockStatus=document.getElementById('lockStatus'),status=document.getElementById('status'),chat=document.getElementById('chat'),turn=document.getElementById('turn'),send=document.getElementById('send'),forget=document.getElementById('forget'),last='',busy=false,roomKey=localStorage.getItem('roomAllenKey')||'';function headers(){return {'Authorization':'Bearer '+roomKey}}function tm(s){try{return new Date(s).toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}catch(e){return''}}function nm(x,m){return x.speaker==='allen'?'Allen':((m[x.speaker]&&m[x.speaker].name)||x.speaker||'')}async function auth(){if(!roomKey)return false;try{var r=await fetch('/api/allen/auth',{headers:headers(),cache:'no-store'});if(!r.ok)return false;lock.classList.add('hidden');app.classList.remove('hidden');refresh();return true}catch(e){return false}}async function doUnlock(){roomKey=keyInput.value.trim();lockStatus.textContent='checking…';if(await auth()){localStorage.setItem('roomAllenKey',roomKey);lockStatus.textContent=''}else{lockStatus.textContent='That key did not open Allen.';roomKey=''}}unlock.onclick=doUnlock;keyInput.addEventListener('keydown',function(e){if(e.key==='Enter')doUnlock()});forget.onclick=function(){localStorage.removeItem('roomAllenKey');location.reload()};function render(r){var f=r.feed||{},c=Array.isArray(f.conversation)?f.conversation:[],m=f.minds&&f.minds.entities||{},st=f.state||{},sig=c.length?String(c[c.length-1].id||'')+':'+c.length:'';var age=r.receivedAt?Math.max(0,Math.floor((Date.now()-Date.parse(r.receivedAt))/1000)):9999;status.className='status'+(age<15?' live':'');status.textContent=(age<15?'LIVE':'STALE')+' · beat '+(st.cycle||'—')+' · '+age+'s';if(sig===last)return;last=sig;chat.innerHTML='';var start=Math.max(0,c.length-90),prev='';for(var i=start;i<c.length;i++){var x=c[i]||{},b=x.beat_id||'';if(b!==prev){var h=document.createElement('div');h.className='beat';h.textContent='BEAT '+(b?b.slice(-6):'—');chat.appendChild(h);prev=b}var d=document.createElement('div');d.className='msg'+(x.speaker==='allen'?' allen':'');var w=document.createElement('div');w.className='who';w.textContent=nm(x,m);var t=document.createElement('div');t.className='text';t.textContent=x.text||'';var q=document.createElement('div');q.className='when';q.textContent=tm(x.at);d.appendChild(w);d.appendChild(t);d.appendChild(q);chat.appendChild(d)}}async function refresh(){if(busy)return;busy=true;try{var r=await fetch('/api/feed?fresh='+Date.now(),{cache:'no-store'});if(r.ok)render(await r.json())}finally{busy=false}}async function speak(){var text=turn.value.trim();if(!text||send.disabled)return;send.disabled=true;status.textContent='sending Allen…';try{var r=await fetch('/api/allen',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},headers()),body:JSON.stringify({text:text})});if(r.status===401){localStorage.removeItem('roomAllenKey');location.reload();return}var data=await r.json();if(!r.ok)throw new Error(data.error||'send failed');turn.value='';status.className='status live';status.textContent='Allen is queued for the next Room beat';setTimeout(refresh,1200)}catch(e){status.className='status';status.textContent=String(e.message||e)}finally{send.disabled=false;turn.focus()}}send.onclick=speak;turn.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();speak()}});setInterval(refresh,2000);document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible')refresh()});if(roomKey){auth().then(function(ok){if(!ok){roomKey='';localStorage.removeItem('roomAllenKey')}})}else{keyInput.focus()}})();</script></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stub = env.ROOM.getByName("main");

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

    if (url.pathname === "/api/ingest" && request.method === "POST") {
      try {
        const claims = await requireGitHub(request);
        const feed = await request.json();
        if (!validFeed(feed)) return json({ error: "invalid-feed" }, 400);
        const result = await stub.putLatest(feed, claims.sha || "");
        return json(result, result.accepted ? 202 : 200);
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }

    if (url.pathname === "/api/participant/pending" && request.method === "GET") {
      try {
        await requireGitHub(request);
        return json(await stub.pendingAllen());
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }

    if (url.pathname === "/api/participant/ack" && request.method === "POST") {
      try {
        await requireGitHub(request);
        const body = await request.json();
        return json(await stub.ackAllen(body?.ids || []));
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }

    if (url.pathname === "/api/allen/auth" && request.method === "GET") {
      if (!(await allenAuthorized(request, env))) return json({ error: "unauthorized" }, 401);
      return json({ ok: true, identity: "Allen" });
    }

    if (url.pathname === "/api/allen" && request.method === "POST") {
      if (!(await allenAuthorized(request, env))) return json({ error: "unauthorized" }, 401);
      try {
        const body = await request.json();
        const text = String(body?.text || "").trim();
        if (!text) return json({ error: "empty-turn" }, 400);
        if (text.length > MAX_TURN) return json({ error: "turn-too-long", max: MAX_TURN }, 400);
        const result = await stub.enqueueAllen(text);
        return json(result, result.accepted ? 202 : 429);
      } catch (error) {
        return json({ error: "invalid-request", detail: String(error?.message || error) }, 400);
      }
    }

    if (url.pathname === "/api/feed" && request.method === "GET") {
      const latest = await stub.getLatest();
      if (!latest) return json({ error: "no-feed-yet" }, 503);
      return json(latest);
    }

    if (url.pathname === "/health" && request.method === "GET") {
      const latest = await stub.getLatest();
      return json({ ok: true, hasFeed: Boolean(latest), cycle: latest?.feed?.state?.cycle || null, receivedAt: latest?.receivedAt || null });
    }

    if (url.pathname === "/allen" && (request.method === "GET" || request.method === "HEAD")) {
      return request.method === "HEAD" ? html("") : html(ALLEN_VIEWER);
    }

    if (request.method === "GET" || request.method === "HEAD") {
      return request.method === "HEAD" ? html("") : html(VIEWER);
    }

    return json({ error: "not-found" }, 404);
  },
};
