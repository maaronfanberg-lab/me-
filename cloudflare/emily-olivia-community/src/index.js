const RAW_BASE = "https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/experiments/emily-olivia-society/";
const VIEWER_SOURCE = RAW_BASE + "viewer.html";
const SNAPSHOT_SOURCE = RAW_BASE + "replay/community_session.json";
const STREAM_SOURCE = RAW_BASE + "replay/community_session.jsonl";
const ISSUER = "https://token.actions.githubusercontent.com";
const EXPECTED_AUDIENCE = "emily-olivia-community";
const EXPECTED_REPOSITORY = "maaronfanberg-lab/me-";
const EXPECTED_REF = "refs/heads/main";
const ALEX_KEY_SHA256 = "6df7d69a879e58e61dae75508e271107e758113a4bf1d65083691898a62b6ac5";
const MAX_ALEX_TURN = 700;
const MAX_ALEX_QUEUE = 50;
let oidcMetadataCache = null;
let jwksCache = null;

function text(body, status = 200, contentType = "text/plain; charset=utf-8") {
  return new Response(body, {
    status,
    headers: {
      "content-type": contentType,
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer"
    }
  });
}

function json(data, status = 200) {
  return text(JSON.stringify(data), status, "application/json; charset=utf-8");
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

async function alexAuthorized(request) {
  const token = bearer(request);
  if (!token) return false;
  return constantTimeHexEqual(await sha256Hex(token), ALEX_KEY_SHA256);
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
  const response = await fetch(`${ISSUER}/.well-known/openid-configuration`, { headers: { accept: "application/json" } });
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
    "jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]
  );
  const verified = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5", key, decodeBase64Url(parts[2]), new TextEncoder().encode(`${parts[0]}.${parts[1]}`)
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
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("Malformed token");
  const header = decodeJwtJson(parts[0]);
  const claims = decodeJwtJson(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new Error("Unexpected token header");
  let jwks = await getJwks();
  let jwk = (jwks.keys || []).find((item) => item.kid === header.kid);
  if (!jwk) {
    jwksCache = null;
    jwks = await getJwks();
    jwk = (jwks.keys || []).find((item) => item.kid === header.kid);
  }
  if (!jwk) throw new Error("Signing key not found");
  return verifyGitHubTokenWithKey(parts, claims, jwk);
}

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

  async enqueueAlex(textValue, targetValue) {
    const queue = (await this.ctx.storage.get("alexQueue")) || [];
    if (queue.length >= MAX_ALEX_QUEUE) return { accepted: false, reason: "queue-full" };
    const text = String(textValue || "").trim();
    const target = ["Emily", "Olivia", "both"].includes(String(targetValue || "")) ? String(targetValue) : "both";
    const turn = {
      id: crypto.randomUUID(),
      speaker: "Alex",
      text,
      target,
      at: new Date().toISOString()
    };
    queue.push(turn);
    await this.ctx.storage.put("alexQueue", queue);
    return { accepted: true, id: turn.id, at: turn.at, target, queued: queue.length };
  }

  async pendingAlex() {
    const queue = (await this.ctx.storage.get("alexQueue")) || [];
    return { messages: queue.slice(0, 20) };
  }

  async ackAlex(ids) {
    const wanted = new Set((Array.isArray(ids) ? ids : []).map(String));
    const queue = (await this.ctx.storage.get("alexQueue")) || [];
    const kept = queue.filter((turn) => !wanted.has(String(turn.id)));
    await this.ctx.storage.put("alexQueue", kept);
    return { acknowledged: queue.length - kept.length, queued: kept.length };
  }

  async fetch() {
    await this.alarm();
    return text("Retired duplicate generator. This endpoint is queue storage only.", 410);
  }
}

async function upstream(url) {
  const response = await fetch(url + "?t=" + Date.now(), {
    headers: { "user-agent": "emily-olivia-live-viewer" },
    cf: { cacheTtl: 0, cacheEverything: false }
  });
  if (!response.ok) return text("Upstream replay unavailable", 502);
  return response;
}

const ALEX_VIEWER = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0c0d10"><title>Alex · Emily + Olivia</title><style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#0c0d10;color:#ececf1;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{padding:0 12px 150px}.top{position:sticky;top:0;background:#0c0d10f5;padding:calc(14px + env(safe-area-inset-top)) 2px 11px;border-bottom:1px solid #252b36;z-index:3}.title{font-size:23px;font-weight:850}.sub{font-size:12px;color:#a3a9b3;margin-top:4px}.status{margin-top:8px;font-size:12px;color:#9ca3af}.status.live{color:#6ee7b7}.chat{max-width:760px;margin:14px auto}.msg{max-width:86%;background:#171a22;border:1px solid #2b3240;border-radius:16px;padding:11px 13px;margin:0 0 10px}.msg.olivia{margin-left:auto;background:#241d2a}.msg.alex{margin-left:auto;background:#2b2a20;border-color:#7a6b38}.who{font-size:10px;font-weight:850;letter-spacing:.08em;color:#d7c18a;margin-bottom:5px}.text{font-size:16px;line-height:1.45;white-space:pre-wrap}.when{font-size:9px;color:#707887;margin-top:6px}.lock{max-width:520px;margin:22vh auto 0;background:#151821;border:1px solid #2d313d;border-radius:18px;padding:18px}.keyrow,.composer-inner{display:flex;gap:8px}.keyrow input,.composer textarea{flex:1;min-width:0}input,textarea,select{background:#11141b;color:#fff;border:1px solid #394150;border-radius:12px;padding:11px 12px;font:inherit;outline:none}button{border:1px solid #4a5364;background:#171d28;color:#fff;border-radius:12px;padding:11px 14px;font-weight:800}.send{background:#d3bd82;color:#111;border-color:#d3bd82}.composer{position:fixed;left:0;right:0;bottom:0;background:#0c0d10fa;border-top:1px solid #2b3240;padding:8px 12px calc(10px + env(safe-area-inset-bottom));z-index:4}.composer-inner{max-width:760px;margin:auto;align-items:flex-end}.composer textarea{min-height:48px;max-height:130px;resize:vertical}.target{max-width:760px;margin:0 auto 7px;display:flex;gap:8px;align-items:center;font-size:11px;color:#9ca3af}.hidden{display:none!important}.hint{font-size:12px;color:#9ca3af;line-height:1.45;margin:6px 0 12px}</style></head><body>
<div id="lock" class="lock"><div class="title">Enter as Alex</div><div class="hint">Use your private Alex key. It stays only in this browser.</div><div class="keyrow"><input id="key" type="password" placeholder="Alex key"><button id="unlock">Enter</button></div><div id="lockStatus" class="status"></div></div>
<div id="app" class="hidden"><div class="top"><div class="title">Emily + Olivia + Alex</div><div class="sub">Your messages enter their live Stanford memory and reaction cycle.</div><div id="status" class="status">connecting…</div></div><main id="chat" class="chat"></main><div class="composer"><div class="target">To <select id="target"><option value="both">Emily & Olivia</option><option value="Emily">Emily</option><option value="Olivia">Olivia</option></select></div><div class="composer-inner"><textarea id="turn" maxlength="700" placeholder="Speak as Alex…"></textarea><button id="send" class="send">Send</button></div></div></div>
<script>(function(){
var lock=document.getElementById('lock'),app=document.getElementById('app'),keyInput=document.getElementById('key'),unlock=document.getElementById('unlock'),lockStatus=document.getElementById('lockStatus'),status=document.getElementById('status'),chat=document.getElementById('chat'),turn=document.getElementById('turn'),send=document.getElementById('send'),target=document.getElementById('target'),last='',busy=false;
var q=new URLSearchParams(location.search),passed=q.get('key')||'',alexKey=passed||localStorage.getItem('emilyOliviaAlexKey')||'';if(passed){localStorage.setItem('emilyOliviaAlexKey',passed);history.replaceState(null,'',location.pathname)}
function headers(){return {'Authorization':'Bearer '+alexKey}}
function tm(s){try{return new Date(s).toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}catch(e){return''}}
function msg(raw){if(!raw||typeof raw!=='object')return null;var speaker=raw.from_name||raw.speaker||'',text=raw.content||raw.text||'',at=raw.created_at||raw.at||'';if(!/^(Emily|Olivia|Alex)$/i.test(speaker)||!String(text).trim())return null;return{speaker:String(speaker),text:String(text),at:String(at),id:String(raw.id||'')}}
function localAlex(){try{return JSON.parse(localStorage.getItem('emilyOliviaAlexTurns')||'[]').map(msg).filter(Boolean)}catch(e){return[]}}
function rememberAlex(text,at,id){var rows=localAlex();rows.push({speaker:'Alex',text:text,at:at,id:id});rows=rows.slice(-100);localStorage.setItem('emilyOliviaAlexTurns',JSON.stringify(rows))}
async function auth(){if(!alexKey)return false;try{var r=await fetch('/api/alex/auth',{headers:headers(),cache:'no-store'});if(!r.ok)return false;lock.classList.add('hidden');app.classList.remove('hidden');refresh();return true}catch(e){return false}}
async function doUnlock(){alexKey=keyInput.value.trim();lockStatus.textContent='checking…';if(await auth()){localStorage.setItem('emilyOliviaAlexKey',alexKey);lockStatus.textContent=''}else{lockStatus.textContent='That key did not open Alex.';alexKey=''}}
unlock.onclick=doUnlock;keyInput.addEventListener('keydown',function(e){if(e.key==='Enter')doUnlock()});
function render(data){var rows=Array.isArray(data&&data.messages)?data.messages.map(msg).filter(Boolean):[];rows=rows.concat(localAlex()).sort(function(a,b){return Date.parse(a.at||0)-Date.parse(b.at||0)});var seen={};rows=rows.filter(function(x){var k=x.id?x.speaker+':'+x.id:x.speaker+':'+x.text+':'+x.at;if(seen[k])return false;seen[k]=1;return true});var sig=String(data&&data.session_id||'')+':'+rows.length+':'+(rows.length?rows[rows.length-1].text:'');status.className='status'+(data&&data.status==='running'?' live':'');status.textContent=(data&&data.status==='running'?'LIVE':'PAUSED')+' · '+rows.length+' visible room messages';if(sig===last)return;last=sig;var follow=window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-180||!chat.children.length;chat.innerHTML='';rows.slice(-180).forEach(function(x){var d=document.createElement('div');d.className='msg '+x.speaker.toLowerCase();var w=document.createElement('div');w.className='who';w.textContent=x.speaker;var t=document.createElement('div');t.className='text';t.textContent=x.text;var z=document.createElement('div');z.className='when';z.textContent=tm(x.at);d.appendChild(w);d.appendChild(t);d.appendChild(z);chat.appendChild(d)});if(follow)requestAnimationFrame(function(){window.scrollTo(0,document.documentElement.scrollHeight)})}
async function refresh(){if(busy)return;busy=true;try{var r=await fetch('/state?t='+Date.now(),{cache:'no-store'});if(r.ok)render(await r.json())}finally{busy=false}}
async function speak(){var spoken=turn.value.trim();if(!spoken||send.disabled)return;send.disabled=true;status.textContent='sending Alex…';try{var r=await fetch('/api/alex',{method:'POST',headers:Object.assign({'Content-Type':'application/json'},headers()),body:JSON.stringify({text:spoken,target:target.value})});if(r.status===401){localStorage.removeItem('emilyOliviaAlexKey');location.reload();return}var data=await r.json();if(!r.ok)throw new Error(data.error||'send failed');rememberAlex(spoken,data.at||new Date().toISOString(),data.id||crypto.randomUUID());turn.value='';status.className='status live';status.textContent='Alex queued · they will observe it on the next eligible turn';refresh()}catch(e){status.className='status';status.textContent=String(e.message||e)}finally{send.disabled=false;turn.focus()}}
send.onclick=speak;turn.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();speak()}});setInterval(refresh,3000);document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible')refresh()});if(alexKey){auth().then(function(ok){if(!ok){alexKey='';localStorage.removeItem('emilyOliviaAlexKey');keyInput.focus()}})}else{keyInput.focus()}
})();</script></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stub = env.COMMUNITY.getByName("alex-participant");

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
    if (url.pathname === "/alex" && request.method === "GET") return text(ALEX_VIEWER, 200, "text/html; charset=utf-8");
    if (url.pathname === "/api/alex/auth" && request.method === "GET") {
      if (!(await alexAuthorized(request))) return json({ error: "unauthorized" }, 401);
      return json({ ok: true, identity: "Alex" });
    }
    if (url.pathname === "/api/alex" && request.method === "POST") {
      if (!(await alexAuthorized(request))) return json({ error: "unauthorized" }, 401);
      try {
        const body = await request.json();
        const turn = String(body?.text || "").trim();
        if (!turn) return json({ error: "empty-turn" }, 400);
        if (turn.length > MAX_ALEX_TURN) return json({ error: "turn-too-long" }, 400);
        const result = await stub.enqueueAlex(turn, body?.target);
        return result.accepted ? json(result, 202) : json(result, 429);
      } catch (error) {
        return json({ error: "bad-request", detail: String(error?.message || error) }, 400);
      }
    }
    if (url.pathname === "/api/alex/pending" && request.method === "GET") {
      try {
        await requireGitHub(request);
        return json(await stub.pendingAlex());
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }
    if (url.pathname === "/api/alex/ack" && request.method === "POST") {
      try {
        await requireGitHub(request);
        const body = await request.json();
        return json(await stub.ackAlex(body?.ids));
      } catch (error) {
        return json({ error: "unauthorized", detail: String(error?.message || error) }, 401);
      }
    }
    if (url.pathname === "/start" || url.pathname === "/stop") {
      return text("Retired duplicate generator. Emily + Olivia run only through the Stanford Community workflow.", 410);
    }
    return text("Not found", 404);
  }
};
