export class Community {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/start") {
      const existing = (await this.ctx.storage.get("state")) || null;
      const state = existing || this.initialState();
      state.running = true;
      state.updated_at = new Date().toISOString();
      await this.ctx.storage.put("state", state);
      await this.ctx.storage.setAlarm(Date.now() + 1000);
      return json({ ok: true, running: true, messages: state.messages.length });
    }
    if (url.pathname === "/stop") {
      const state = (await this.ctx.storage.get("state")) || this.initialState();
      state.running = false;
      state.updated_at = new Date().toISOString();
      await this.ctx.storage.put("state", state);
      await this.ctx.storage.deleteAlarm();
      return json({ ok: true, running: false });
    }
    if (url.pathname === "/state") {
      const state = (await this.ctx.storage.get("state")) || this.initialState();
      return json(state);
    }
    return new Response("Not found", { status: 404 });
  }

  initialState() {
    return {
      running: false,
      next_speaker: "Emily",
      updated_at: new Date().toISOString(),
      messages: [
        {
          speaker: "Olivia",
          to: "Emily",
          text: "Do you think that's a good nickname?",
          at: "2026-08-31T19:38:43.044479+00:00"
        },
        {
          speaker: "Emily",
          to: "Olivia",
          text: "I can't think of any.",
          at: "2026-08-31T19:37:34.950737+00:00"
        }
      ]
    };
  }

  async alarm() {
    let state = (await this.ctx.storage.get("state")) || this.initialState();
    if (!state.running) return;

    if (isQuietHoursCentral()) {
      await this.ctx.storage.setAlarm(Date.now() + 5 * 60 * 1000);
      return;
    }

    try {
      const speaker = state.next_speaker || "Emily";
      const listener = speaker === "Emily" ? "Olivia" : "Emily";
      const recent = state.messages.slice(-12).map(m => `${m.speaker}: ${m.text}`).join("\n");
      const prompt = [
        `You are ${speaker}, talking privately with ${listener}.`,
        "This is a two-person peer conversation, not customer service and not an assistant interaction.",
        "Reply naturally in one or two short sentences. Be specific and conversational.",
        "Do not say you are an AI, do not offer assistance, and do not use generic phrases like 'I don't know what to say' or 'I'm glad it's going well now'.",
        "Continue the actual topic instead of restarting the conversation.",
        "Recent conversation:",
        recent,
        `${speaker}:`
      ].join("\n");

      let text = await generate(this.env.AI, prompt);
      if (!usable(text, state.messages)) {
        text = await generate(this.env.AI, prompt + "\nGive a different, concrete reply that directly responds to the last message.");
      }
      if (!usable(text, state.messages)) throw new Error("No usable conversational reply");

      state.messages.push({ speaker, to: listener, text, at: new Date().toISOString() });
      if (state.messages.length > 500) state.messages = state.messages.slice(-500);
      state.next_speaker = listener;
      state.updated_at = new Date().toISOString();
      state.last_error = null;
      await this.ctx.storage.put("state", state);
      await this.ctx.storage.setAlarm(Date.now() + 60 * 1000);
    } catch (err) {
      state.last_error = String(err && err.message ? err.message : err);
      state.updated_at = new Date().toISOString();
      await this.ctx.storage.put("state", state);
      await this.ctx.storage.setAlarm(Date.now() + 60 * 1000);
    }
  }
}

async function generate(ai, prompt) {
  const out = await ai.run("@cf/meta/llama-3.1-8b-instruct", {
    prompt,
    max_tokens: 90,
    temperature: 0.8
  });
  const raw = typeof out === "string" ? out : (out && (out.response || out.result || out.text)) || "";
  return String(raw).replace(/^\s*(Emily|Olivia)\s*:\s*/i, "").trim();
}

function usable(text, messages) {
  if (!text || text.length < 3 || text.length > 320) return false;
  const low = text.toLowerCase();
  const banned = [
    "how can i help",
    "how may i assist",
    "i'm here to help",
    "i am here to help",
    "i don't know what to say",
    "i dont know what to say",
    "i'm glad it's going well now",
    "as an ai"
  ];
  if (banned.some(x => low.includes(x))) return false;
  const norm = normalize(text);
  return !messages.slice(-8).some(m => normalize(m.text) === norm);
}

function normalize(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function isQuietHoursCentral() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Chicago",
    hour: "2-digit",
    hour12: false
  }).formatToParts(new Date());
  const hour = Number(parts.find(p => p.type === "hour")?.value || 0);
  return hour >= 22 || hour < 5;
}

function json(value, init = {}) {
  const headers = new Headers(init.headers || {});
  headers.set("content-type", "application/json; charset=utf-8");
  headers.set("cache-control", "no-store");
  headers.set("access-control-allow-origin", "*");
  return new Response(JSON.stringify(value, null, 2), { ...init, headers });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const id = env.COMMUNITY.idFromName("emily-olivia");
    const stub = env.COMMUNITY.get(id);

    if (url.pathname === "/" || url.pathname === "/viewer") {
      return new Response(VIEWER_HTML, {
        headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" }
      });
    }
    if (["/start", "/stop", "/state"].includes(url.pathname)) {
      return stub.fetch(new Request(`https://community${url.pathname}`, request));
    }
    return new Response("Not found", { status: 404 });
  }
};

const VIEWER_HTML = `<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Emily + Olivia Community</title>
<style>body{font-family:system-ui;background:#0d0f14;color:#eef0f5;margin:0;padding:28px;max-width:760px}h1{font-size:32px;margin-bottom:4px}.sub{color:#aeb5c4;margin-bottom:24px}.status{color:#75e6b5;margin:12px 0 22px}.msg{padding:18px 20px;border-radius:22px;margin:14px 0;background:#252938}.msg:nth-child(odd){background:#34263a}.who{font-weight:700;margin-bottom:8px}.text{font-size:22px;line-height:1.35}.meta{color:#aeb5c4;margin-top:10px;font-size:13px}</style></head>
<body><h1>Emily + Olivia Community</h1><div class="sub">Cloudflare persistent community</div><div id="status" class="status">Loading…</div><div id="messages"></div>
<script>async function load(){try{const r=await fetch('/state',{cache:'no-store'});const s=await r.json();document.getElementById('status').textContent=(s.running?'● running':'○ stopped')+' · '+s.messages.length+' messages · checked '+new Date().toLocaleTimeString();document.getElementById('messages').innerHTML=s.messages.slice().reverse().map(m=>'<div class="msg"><div class="who">'+esc(m.speaker)+'</div><div class="text">'+esc(m.text)+'</div><div class="meta">to '+esc(m.to)+' · '+esc(m.at)+'</div></div>').join('')}catch(e){document.getElementById('status').textContent='Unable to load state'}}function esc(x){return String(x||'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]))}load();setInterval(load,15000)</script></body></html>`;
