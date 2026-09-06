(() => {
  "use strict";

  const STATE_URL = "https://raw.githubusercontent.com/maaronfanberg-lab/me-/cedar-live-state/cedar-state.json";
  const POLL_MS = 3000;
  const coords = {
    square:[50,48], kitchen:[23,22], workshop:[77,22],
    greenhouse:[18,72], clinic:[50,82], water_tower:[82,70],
  };
  const els = {
    liveBox: document.querySelector("#liveBox"),
    statusText: document.querySelector("#statusText"),
    freshness: document.querySelector("#freshness"),
    tick: document.querySelector("#tickValue"),
    agents: document.querySelector("#agentValue"),
    model: document.querySelector("#modelValue"),
    temp: document.querySelector("#tempValue"),
    edgeLayer: document.querySelector("#edgeLayer"),
    locationLayer: document.querySelector("#locationLayer"),
    agentGrid: document.querySelector("#agentGrid"),
    decisions: document.querySelector("#decisions"),
    detail: document.querySelector("#agentDetail"),
    events: document.querySelector("#events"),
    sessionLine: document.querySelector("#sessionLine"),
  };

  let state = null;
  let selectedAgent = null;
  let lastFingerprint = "";
  let lastFetchOk = false;

  const esc = (value) => String(value ?? "")
    .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;").replaceAll("'","&#039;");
  const titleCase = (value) => String(value || "").replaceAll("_"," ").replace(/\b\w/g, m => m.toUpperCase());

  function color(name) {
    let hash = 0;
    for (const ch of String(name)) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
    return `hsl(${Math.abs(hash)%360} 42% 46%)`;
  }

  function actionSummary(event) {
    const action = event.action || event.proposed_action || event.proposed || {};
    const type = action.type || event.proposed_type || "unknown";
    if (type === "move") return `move → ${action.location || event.outcome?.to || "?"}`;
    if (type === "talk") return `talk → ${action.target || "?"}`;
    if (type === "help") return `help → ${action.target || "?"}`;
    if (type === "work") return `work · ${action.resource || "?"}`;
    return type;
  }

  function secondsOld() {
    if (!state?.updated_at) return null;
    const t = Date.parse(state.updated_at);
    return Number.isFinite(t) ? Math.max(0, Math.floor((Date.now() - t) / 1000)) : null;
  }

  function renderStatus() {
    const age = secondsOld();
    const nominal = String(state?.status || (lastFetchOk ? "offline" : "connecting"));
    const stale = nominal === "live" && age !== null && age > 30;
    let label = "OFFLINE";
    let cls = "";
    if (nominal === "starting") { label = "STARTING FALCON"; cls = "status-starting"; }
    else if (nominal === "live" && !stale) { label = "LIVE"; cls = "status-live"; }
    else if (nominal === "live" && stale) { label = "LIVE FEED STALE"; cls = "status-starting"; }
    else if (nominal === "complete") { label = "SESSION ENDED"; }
    else if (nominal === "error") { label = "SESSION ERROR"; cls = "status-error"; }
    else if (!lastFetchOk) { label = "CONNECTING"; cls = "status-starting"; }

    els.liveBox.className = `live-box ${cls}`.trim();
    els.statusText.textContent = label;
    if (age === null) els.freshness.textContent = state?.note || "Waiting for the live feed.";
    else if (age < 2) els.freshness.textContent = "Updated just now.";
    else if (age < 60) els.freshness.textContent = `Updated ${age}s ago.`;
    else els.freshness.textContent = `Last update ${Math.floor(age/60)}m ${age%60}s ago.`;
  }

  function renderEdges() {
    if (!state?.locations) return;
    const seen = new Set();
    const lines = [];
    for (const [name, loc] of Object.entries(state.locations)) {
      for (const neighbor of loc.neighbors || []) {
        const key = [name, neighbor].sort().join("|");
        if (seen.has(key)) continue;
        seen.add(key);
        const a = coords[name], b = coords[neighbor];
        if (!a || !b) continue;
        lines.push(`<line x1="${a[0]*10}" y1="${a[1]*6.8}" x2="${b[0]*10}" y2="${b[1]*6.8}"></line>`);
      }
    }
    els.edgeLayer.innerHTML = lines.join("");
  }

  function renderMap() {
    if (!state?.locations || !state?.agents) {
      els.locationLayer.innerHTML = '<div class="empty">Cedar has not published a world snapshot yet.</div>';
      return;
    }
    const nodes = [];
    for (const [name, loc] of Object.entries(state.locations)) {
      const [x,y] = coords[name] || [50,50];
      const here = Object.values(state.agents).filter(a => a.location === name);
      const resources = Object.entries(loc.resources || {}).map(([k,v]) => `${titleCase(k)} ${v}`).join(" · ") || "No tracked resources";
      const agents = here.map(a =>
        `<button type="button" class="agent-dot" data-agent="${esc(a.name)}" style="background:${color(a.name)}">${esc(a.name)}</button>`
      ).join("");
      nodes.push(`<div class="location" style="left:${x}%;top:${y}%">
        <h3>${esc(titleCase(name))}</h3>
        <div class="resources">${esc(resources)}</div>
        <div class="agents">${agents || '<span class="resources">empty</span>'}</div>
      </div>`);
    }
    els.locationLayer.innerHTML = nodes.join("");
    els.locationLayer.querySelectorAll("[data-agent]").forEach(btn => btn.addEventListener("click", () => {
      selectedAgent = btn.dataset.agent;
      renderAgents();
      renderAgentDetail();
    }));
  }

  function currentDecisions() {
    const events = state?.recent_events || [];
    const tick = Number(state?.tick || 0);
    return events.filter(e => e.kind === "decision" && Number(e.tick) === tick);
  }

  function renderDecisions() {
    const rows = currentDecisions();
    if (!rows.length) {
      els.decisions.className = "empty";
      els.decisions.textContent = state?.status === "starting" ? "Falcon is starting." : "No decision has arrived for this tick yet.";
      return;
    }
    els.decisions.className = "";
    els.decisions.innerHTML = rows.map(e => {
      const feasible = (e.feasible_action_types || []).map(x => `<span>${esc(x)}</span>`).join("");
      return `<article class="decision">
        <div class="decision-top"><b>${esc(e.actor)}</b><span class="chip ${e.accepted === false ? "bad" : ""}">${esc(actionSummary(e))}</span></div>
        <div class="small">${esc(titleCase(e.location))} · energy ${esc(e.energy)} · ${e.accepted === false ? `rejected: ${esc(e.rejection_reason || "unknown")}` : "accepted"}</div>
        <div class="feasible">${feasible}</div>
      </article>`;
    }).join("");
  }

  function renderAgents() {
    if (!state?.agents) { els.agentGrid.innerHTML = ""; return; }
    const rows = Object.values(state.agents);
    els.agentGrid.innerHTML = rows.map(a => `<button type="button" class="agent-card ${selectedAgent === a.name ? "active" : ""}" data-card="${esc(a.name)}">
      <b>${esc(a.name)}</b><span>${esc(titleCase(a.location))} · energy ${esc(a.energy)}</span>
    </button>`).join("");
    els.agentGrid.querySelectorAll("[data-card]").forEach(btn => btn.addEventListener("click", () => {
      selectedAgent = btn.dataset.card;
      renderAgents();
      renderAgentDetail();
    }));
  }

  function recentAgentDecisions(name) {
    return (state?.recent_events || []).filter(e => e.kind === "decision" && e.actor === name).slice(-4).reverse();
  }

  function renderAgentDetail() {
    const a = state?.agents?.[selectedAgent];
    if (!a) {
      els.detail.className = "empty";
      els.detail.textContent = "Tap a resident on the map.";
      return;
    }
    const memories = (a.memories || []).slice(-5).reverse();
    const decisions = recentAgentDecisions(a.name);
    els.detail.className = "agent-detail";
    els.detail.innerHTML = `
      <div class="decision-top"><b>${esc(a.name)}</b><span class="chip">${esc(titleCase(a.location))}</span></div>
      <p class="small">${esc((a.traits || []).join(" · "))} · energy ${esc(a.energy)}</p>
      <p><b>Goals</b><br>${(a.goals || []).map(g => esc(g)).join("<br>")}</p>
      <p><b>Recent decisions</b><br>${decisions.length ? decisions.map(d => `tick ${esc(d.tick)}: ${esc(actionSummary(d))}`).join("<br>") : "none yet"}</p>
      <p><b>Recent memories</b><br>${memories.length ? memories.map(m => `tick ${esc(m.tick)}: ${esc(m.text)}`).join("<br>") : "none yet"}</p>`;
  }

  function eventText(e) {
    if (e.kind === "incident") return e.description || `${e.resource} changed at ${e.location}`;
    if (e.kind === "action") return `${e.actor}: ${actionSummary(e)}`;
    if (e.kind === "decision" && e.accepted === false) return `${e.actor}: ${actionSummary(e)} rejected (${e.rejection_reason || "unknown"})`;
    if (e.kind === "backend_error") return `${e.actor}: Falcon backend error`;
    return null;
  }

  function renderEvents() {
    const rows = (state?.recent_events || []).filter(e =>
      e.kind === "incident" || e.kind === "action" || e.kind === "backend_error" || (e.kind === "decision" && e.accepted === false)
    ).slice(-14).reverse();
    if (!rows.length) {
      els.events.className = "empty";
      els.events.textContent = "No events yet.";
      return;
    }
    els.events.className = "";
    els.events.innerHTML = rows.map(e => `<div class="event ${e.kind === "incident" ? "incident" : ""}">
      <div class="event-top"><span class="small">tick ${esc(e.tick)}</span><span class="chip">${esc(e.kind)}</span></div>
      <div>${esc(eventText(e) || "Recorded event")}</div>
    </div>`).join("");
  }

  function render() {
    renderStatus();
    els.tick.textContent = state?.tick ?? "–";
    els.agents.textContent = state?.agents ? Object.keys(state.agents).length : "–";
    els.model.textContent = state?.model ? String(state.model).replace(/^.*\//,"").slice(0,18) : "–";
    els.temp.textContent = state?.temperature ?? "–";
    if (state?.session_id) els.sessionLine.textContent = `Session ${state.session_id} · seed ${state.seed} · read-only live state`;
    renderEdges();
    renderMap();
    if (!selectedAgent && state?.agents) selectedAgent = Object.keys(state.agents)[0] || null;
    renderDecisions();
    renderAgents();
    renderAgentDetail();
    renderEvents();
  }

  async function poll() {
    try {
      const response = await fetch(`${STATE_URL}?t=${Date.now()}`, {cache:"no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const next = await response.json();
      lastFetchOk = true;
      const fingerprint = `${next.session_id}|${next.updated_at}|${next.tick}|${next.status}`;
      state = next;
      if (fingerprint !== lastFingerprint) {
        lastFingerprint = fingerprint;
        render();
      } else {
        renderStatus();
      }
    } catch (error) {
      lastFetchOk = false;
      if (!state) state = {status:"offline", note:`Live feed unavailable: ${error.message}`};
      renderStatus();
    }
  }

  poll();
  window.setInterval(poll, POLL_MS);
  window.setInterval(() => { if (state) renderStatus(); }, 1000);
})();
