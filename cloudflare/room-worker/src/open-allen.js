import base, { RoomState } from "./index.js";

export { RoomState };

const MAX_TURN = 700;
const ROOM_HISTORY_URL = "https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/feed.json";

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

function marketSymbol(value) {
  const symbol = String(value || "WMT").trim().toUpperCase();
  return /^[A-Z0-9.^=-]{1,18}$/.test(symbol) ? symbol : null;
}

async function marketData(url) {
  const symbol = marketSymbol(url.searchParams.get("symbol"));
  if (!symbol) return json({ error: "invalid-symbol" }, 400);

  const allowedIntervals = new Set(["1m", "2m", "5m", "15m", "30m", "60m", "1d"]);
  const allowedRanges = new Set(["1d", "5d", "1mo", "3mo", "6mo", "1y"]);
  const interval = allowedIntervals.has(url.searchParams.get("interval")) ? url.searchParams.get("interval") : "1m";
  const range = allowedRanges.has(url.searchParams.get("range")) ? url.searchParams.get("range") : "1d";
  const includePrePost = url.searchParams.get("prepost") === "0" ? "false" : "true";

  const yahoo = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`);
  yahoo.searchParams.set("interval", interval);
  yahoo.searchParams.set("range", range);
  yahoo.searchParams.set("includePrePost", includePrePost);
  yahoo.searchParams.set("events", "div,splits");

  try {
    const upstream = await fetch(yahoo.toString(), {
      headers: {
        accept: "application/json,text/plain,*/*",
        "user-agent": "Mozilla/5.0 CavityField/1.0",
      },
      cf: { cacheTtl: 0, cacheEverything: false },
    });
    const text = await upstream.text();
    if (!upstream.ok) {
      return json({ error: "market-upstream", status: upstream.status, detail: text.slice(0, 240) }, 502);
    }
    let payload;
    try {
      payload = JSON.parse(text);
    } catch {
      return json({ error: "market-invalid-json" }, 502);
    }
    return json({ source: "Yahoo Finance chart", fetchedAt: new Date().toISOString(), symbol, interval, range, payload });
  } catch (error) {
    return json({ error: "market-fetch-failed", detail: String(error?.message || error) }, 502);
  }
}

async function earthquakeData() {
  const usgs = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson";
  try {
    const upstream = await fetch(usgs, {
      headers: {
        accept: "application/geo+json,application/json,text/plain,*/*",
        "user-agent": "FastNonsensePredictor/1.0",
      },
      cf: { cacheTtl: 0, cacheEverything: false },
    });
    const text = await upstream.text();
    if (!upstream.ok) {
      return json({ error: "earthquake-upstream", status: upstream.status, detail: text.slice(0, 240) }, 502);
    }
    let payload;
    try {
      payload = JSON.parse(text);
    } catch {
      return json({ error: "earthquake-invalid-json" }, 502);
    }
    return json(payload);
  } catch (error) {
    return json({ error: "earthquake-fetch-failed", detail: String(error?.message || error) }, 502);
  }
}

const RESILIENT_VIEWER = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#08090d"><title>The Room — Live</title><style>
html,body{margin:0;min-height:100%;background:#08090d;color:#f5f3ee;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}body{padding:0 12px 70px}.top{position:sticky;top:0;background:#08090df5;padding:calc(14px + env(safe-area-inset-top)) 2px 11px;border-bottom:1px solid #252b36;z-index:2}.title{font-size:24px;font-weight:850}.sub{font-size:11px;color:#a3a9b3;margin-top:4px}.status{margin-top:9px;font-size:12px;color:#e0bf79}.status.live{color:#98dfc8}.chat{max-width:760px;margin:14px auto}.beat{font-size:10px;color:#6f7783;text-align:center;margin:18px 0 10px}.msg{background:#11141b;border:1px solid #2b3240;border-radius:16px;padding:11px 13px;margin:0 0 10px}.who{font-size:10px;font-weight:800;letter-spacing:.1em;color:#d7c18a;margin-bottom:6px}.text{font-size:16px;line-height:1.45}.when{font-size:9px;color:#707887;margin-top:7px}.err{padding:24vh 18px;text-align:center;color:#a3a9b3;line-height:1.5}</style></head><body>
<div class="top"><div class="title">The Room</div><div class="sub">Sarah · Mara · Owen · Jules · Allen</div><div id="status" class="status">connecting…</div></div><main id="chat" class="chat"><div class="err">Opening the Room…</div></main>
<script>(function(){
var status=document.getElementById('status'),chat=document.getElementById('chat'),last='',busy=false,CACHE='roomLastGoodFeedV2',GH=${JSON.stringify(ROOM_HISTORY_URL)};
function tm(s){try{return new Date(s).toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}catch(e){return''}}
function nm(x,m){return x.speaker==='allen'?'Allen':((m[x.speaker]&&m[x.speaker].name)||x.speaker||'')}
function valid(r){var f=r&&r.feed;return !!(f&&f.state&&Array.isArray(f.conversation)&&f.conversation.length)}
function stamp(r){var f=r&&r.feed||{},st=f.state||{},s=f.generated_at||st.last_run||r&&r.receivedAt||'';var n=Date.parse(s);return Number.isFinite(n)?n:0}
function boot(r){return String(r&&r.feed&&r.feed.state&&r.feed.state.boot_id||'')}
function save(r){try{if(valid(r))localStorage.setItem(CACHE,JSON.stringify(r))}catch(e){}}
function load(){try{var r=JSON.parse(localStorage.getItem(CACHE)||'null');return valid(r)?r:null}catch(e){return null}}
function render(r,source){var f=r.feed||{},c=Array.isArray(f.conversation)?f.conversation:[],m=f.minds&&f.minds.entities||{},st=f.state||{},sig=c.length?String(c[c.length-1].id||'')+':'+c.length:'';var when=stamp(r),age=when?Math.max(0,Math.floor((Date.now()-when)/1000)):9999;status.className='status'+(source==='relay'&&age<15?' live':'');status.textContent=(source==='relay'?(age<15?'LIVE':'RELAY'):source==='github'?'GITHUB AUTHORITATIVE':'CACHED')+' · beat '+(st.cycle||'—')+' · '+c.length+' saved · '+age+'s';if(sig===last)return;last=sig;chat.innerHTML='';var start=Math.max(0,c.length-80),prev='';for(var i=start;i<c.length;i++){var x=c[i]||{},b=x.beat_id||'';if(b!==prev){var h=document.createElement('div');h.className='beat';h.textContent='BEAT '+(b?b.slice(-6):'—');chat.appendChild(h);prev=b}var d=document.createElement('div');d.className='msg';var w=document.createElement('div');w.className='who';w.textContent=nm(x,m);var t=document.createElement('div');t.className='text';t.textContent=x.text||'';var q=document.createElement('div');q.className='when';q.textContent=tm(x.at);d.appendChild(w);d.appendChild(t);d.appendChild(q);chat.appendChild(d)}if(c.length&&source==='relay')window.scrollTo(0,document.body.scrollHeight)}
async function relay(){var r=await fetch('/api/feed?fresh='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('relay '+r.status);var data=await r.json();if(!valid(data))throw new Error('relay invalid');return data}
async function github(){var r=await fetch(GH+'?fresh='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('github '+r.status);var f=await r.json();var data={feed:f,receivedAt:f.generated_at||(f.state&&f.state.last_run)||new Date().toISOString()};if(!valid(data))throw new Error('github invalid');return data}
function choose(live,gh){if(valid(live)&&valid(gh)){var lt=stamp(live),gt=stamp(gh);if(boot(live)!==boot(gh))return gt>=lt?{r:gh,s:'github'}:{r:live,s:'relay'};return gt>lt?{r:gh,s:'github'}:{r:live,s:'relay'}}if(valid(live))return{r:live,s:'relay'};if(valid(gh))return{r:gh,s:'github'};return null}
async function refresh(){if(busy)return;busy=true;try{var results=await Promise.allSettled([relay(),github()]);var live=results[0].status==='fulfilled'?results[0].value:null,gh=results[1].status==='fulfilled'?results[1].value:null,pick=choose(live,gh);if(pick){save(pick.r);render(pick.r,pick.s);return}var cached=load();if(cached){render(cached,'cache');return}status.className='status';status.textContent='Room sources unavailable';chat.innerHTML='<div class="err">The live relay and GitHub history are temporarily unreachable. The Room history has not been declared empty.</div>'}finally{busy=false}}
var cached=load();if(cached)render(cached,'cache');refresh();setInterval(refresh,2000);document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible')refresh()});
})();</script></body></html>`;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/api/market" && request.method === "GET") {
      return marketData(url);
    }

    if (url.pathname === "/api/earthquakes" && request.method === "GET") {
      return earthquakeData();
    }

    // Compare live relay state with authoritative GitHub history. A successful
    // relay response is not enough: stale or wrong-boot data must not outrank a
    // newer authoritative feed merely because its HTTP request succeeded.
    if (url.pathname === "/" && (request.method === "GET" || request.method === "HEAD")) {
      return new Response(request.method === "HEAD" ? null : RESILIENT_VIEWER, {
        status: 200,
        headers: {
          "content-type": "text/html; charset=utf-8",
          "cache-control": "no-store",
          "x-content-type-options": "nosniff",
          "referrer-policy": "no-referrer",
        },
      });
    }

    // Allen is intentionally an open participant. The Room page itself is the
    // input surface, so no browser key or bearer token is required to speak.
    if (url.pathname === "/api/allen/auth" && request.method === "GET") {
      return json({ ok: true, identity: "Allen", public: true });
    }

    if (url.pathname === "/api/allen" && request.method === "POST") {
      try {
        const body = await request.json();
        const text = String(body?.text || "").trim();
        if (!text) return json({ error: "empty-turn" }, 400);
        if (text.length > MAX_TURN) return json({ error: "turn-too-long", max: MAX_TURN }, 400);
        const stub = env.ROOM.getByName("main");
        const result = await stub.enqueueAllen(text);
        return json(result, result.accepted ? 202 : 429);
      } catch (error) {
        return json({ error: "invalid-request", detail: String(error?.message || error) }, 400);
      }
    }

    if (url.pathname === "/allen" && (request.method === "GET" || request.method === "HEAD")) {
      return Response.redirect(new URL("/", request.url), 302);
    }

    return base.fetch(request, env, ctx);
  },
};