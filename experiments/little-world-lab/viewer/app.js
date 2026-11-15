(() => {
  "use strict";

  const coords = {
    square: [50, 48],
    kitchen: [23, 22],
    workshop: [77, 22],
    greenhouse: [18, 72],
    clinic: [50, 82],
    water_tower: [82, 70],
  };

  const els = {
    temperature: document.querySelector("#temperatureSelect"),
    seed: document.querySelector("#seedSelect"),
    speed: document.querySelector("#speedSelect"),
    play: document.querySelector("#playButton"),
    back: document.querySelector("#backButton"),
    next: document.querySelector("#nextButton"),
    slider: document.querySelector("#tickSlider"),
    tick: document.querySelector("#tickNumber"),
    tickTotal: document.querySelector("#tickTotal"),
    tickSummary: document.querySelector("#tickSummary"),
    sourceLine: document.querySelector("#sourceLine"),
    footerSource: document.querySelector("#footerSource"),
    edgeLayer: document.querySelector("#edgeLayer"),
    locationLayer: document.querySelector("#locationLayer"),
    incidentBadge: document.querySelector("#incidentBadge"),
    decisionHeading: document.querySelector("#decisionHeading"),
    decisionCount: document.querySelector("#decisionCount"),
    decisions: document.querySelector("#decisions"),
    agentGrid: document.querySelector("#agentGrid"),
    agentDetailName: document.querySelector("#agentDetailName"),
    agentDetail: document.querySelector("#agentDetail"),
    eventCount: document.querySelector("#eventCount"),
    eventStream: document.querySelector("#eventStream"),
  };

  let data = null;
  let currentCondition = null;
  let tick = 0;
  let timer = null;
  let selectedAgent = null;

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const titleCase = (value) => String(value).replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase());

  function agentColor(name) {
    let hash = 0;
    for (const ch of name) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue} 38% 43%)`;
  }

  function actionSummary(event) {
    const action = event.action || event.proposed_action || {};
    const type = action.type || event.proposed_type || "unknown";
    if (type === "move") return `move → ${action.location || event.outcome?.to || "?"}`;
    if (type === "talk") return `talk → ${action.target || "?"}`;
    if (type === "help") return `help → ${action.target || "?"}`;
    if (type === "work") return `work · ${action.resource || "?"}`;
    return type;
  }

  function conditionFor(temp, seed) {
    return data.conditions.find((row) => String(row.temperature) === String(temp) && String(row.seed) === String(seed));
  }

  function rebuildCondition() {
    currentCondition = conditionFor(els.temperature.value, els.seed.value);
    if (!currentCondition) return;
    els.slider.max = String(currentCondition.ticks);
    els.tickTotal.textContent = `/ ${currentCondition.ticks}`;
    tick = Math.min(tick, currentCondition.ticks);
    els.slider.value = String(tick);
    render();
  }

  function initialState() {
    const agents = Object.fromEntries(data.world.agents.map((agent) => [agent.name, {
      location: agent.location,
      lastDecision: null,
      lastAction: null,
    }]));
    const resources = Object.fromEntries(Object.entries(data.world.locations).map(([name, loc]) => [name, {...loc.resources}]));
    return {agents, resources};
  }

  function stateAt(targetTick) {
    const state = initialState();
    const visibleEvents = [];
    const decisionsThisTick = [];
    const incidentsThisTick = [];

    for (const event of currentCondition.events) {
      if (Number(event.tick) > targetTick) continue;
      visibleEvents.push(event);

      if (event.kind === "decision") {
        if (state.agents[event.actor]) state.agents[event.actor].lastDecision = event;
        if (Number(event.tick) === targetTick) decisionsThisTick.push(event);
      }
      if (event.kind === "incident") {
        if (state.resources[event.location] && event.resource) {
          state.resources[event.location][event.resource] = event.after;
        }
        if (Number(event.tick) === targetTick) incidentsThisTick.push(event);
      }
      if (event.kind === "action") {
        if (state.agents[event.actor]) state.agents[event.actor].lastAction = event;
        if (event.action?.type === "move" && event.outcome?.ok && state.agents[event.actor]) {
          state.agents[event.actor].location = event.outcome.to;
        }
      }
    }
    return {...state, visibleEvents, decisionsThisTick, incidentsThisTick};
  }

  function renderEdges() {
    const seen = new Set();
    const lines = [];
    for (const [name, loc] of Object.entries(data.world.locations)) {
      for (const neighbor of loc.neighbors) {
        const key = [name, neighbor].sort().join("|");
        if (seen.has(key)) continue;
        seen.add(key);
        const a = coords[name];
        const b = coords[neighbor];
        if (!a || !b) continue;
        lines.push(`<line x1="${a[0] * 10}" y1="${a[1] * 6.8}" x2="${b[0] * 10}" y2="${b[1] * 6.8}"></line>`);
      }
    }
    els.edgeLayer.innerHTML = lines.join("");
  }

  function renderMap(state) {
    const nodes = [];
    for (const [name] of Object.entries(data.world.locations)) {
      const [x, y] = coords[name] || [50, 50];
      const agentsHere = Object.entries(state.agents).filter(([, row]) => row.location === name).map(([agentName]) => agentName);
      const resources = Object.entries(state.resources[name] || {}).map(([resource, amount]) => `${titleCase(resource)} ${amount}`).join(" · ") || "No tracked resources";
      const dots = agentsHere.map((agentName) => `<button class="agent-dot" data-agent="${escapeHtml(agentName)}" style="background:${agentColor(agentName)}" type="button">${escapeHtml(agentName)}</button>`).join("");
      nodes.push(`
        <div class="location-node" style="left:${x}%;top:${y}%">
          <h3>${escapeHtml(titleCase(name))}</h3>
          <div class="resources">${escapeHtml(resources)}</div>
          <div class="agent-pile">${dots || '<span class="resources">empty</span>'}</div>
        </div>`);
    }
    els.locationLayer.innerHTML = nodes.join("");
    els.locationLayer.querySelectorAll("[data-agent]").forEach((button) => {
      button.addEventListener("click", () => {
        selectedAgent = button.dataset.agent;
        renderAgentGrid(state);
        renderAgentDetail(state);
      });
    });
  }

  function renderDecisions(state) {
    const rows = state.decisionsThisTick;
    els.decisionHeading.textContent = `Tick ${tick}`;
    els.decisionCount.textContent = String(rows.length);
    if (!rows.length) {
      els.decisions.className = "decisions empty-state";
      els.decisions.textContent = tick === 0 ? "No decisions yet. Tick 0 is the starting world." : "No recorded actor decisions at this tick.";
      return;
    }
    els.decisions.className = "decisions";
    els.decisions.innerHTML = rows.map((event) => {
      const accepted = event.accepted !== false;
      const feasible = (event.feasible_action_types || []).map((x) => `<span>${escapeHtml(x)}</span>`).join("");
      return `
        <article class="decision">
          <div class="decision-top">
            <strong>${escapeHtml(event.actor)}</strong>
            <span class="action-chip ${accepted ? "" : "rejected"}">${escapeHtml(actionSummary(event))}</span>
          </div>
          <p class="decision-line"><b>At:</b> ${escapeHtml(titleCase(event.location || "?"))} · <b>energy:</b> ${escapeHtml(event.energy)}</p>
          <p class="decision-line"><b>WorldEngine:</b> ${accepted ? "accepted" : `rejected · ${escapeHtml(event.rejection_reason || "unknown")}`}</p>
          <div class="feasible-list" title="Feasible action types">${feasible}</div>
        </article>`;
    }).join("");
  }

  function renderAgentGrid(state) {
    els.agentGrid.innerHTML = data.world.agents.map((agent) => {
      const row = state.agents[agent.name];
      const last = row.lastDecision ? actionSummary(row.lastDecision) : "no decision yet";
      return `
        <button type="button" class="agent-card ${selectedAgent === agent.name ? "active" : ""}" data-agent-card="${escapeHtml(agent.name)}">
          <span class="agent-name-row"><span class="avatar" style="background:${agentColor(agent.name)}">${escapeHtml(agent.name.slice(0,2).toUpperCase())}</span><strong>${escapeHtml(agent.name)}</strong></span>
          <small>${escapeHtml(titleCase(row.location))}</small>
          <small>${escapeHtml(last)}</small>
        </button>`;
    }).join("");
    els.agentGrid.querySelectorAll("[data-agent-card]").forEach((button) => {
      button.addEventListener("click", () => {
        selectedAgent = button.dataset.agentCard;
        renderAgentGrid(state);
        renderAgentDetail(state);
      });
    });
  }

  function renderAgentDetail(state) {
    if (!selectedAgent) {
      els.agentDetailName.textContent = "Select an agent";
      els.agentDetail.className = "agent-detail empty-state";
      els.agentDetail.textContent = "Traits, goals, current location, recent recorded decisions, and checkpoint memories appear here.";
      return;
    }
    const agent = data.world.agents.find((a) => a.name === selectedAgent);
    const current = state.agents[selectedAgent];
    const checkpoint = currentCondition.final_agents[selectedAgent] || {};
    const memories = (checkpoint.memories || []).filter((memory) => Number(memory.tick) <= tick).slice(-5).reverse();
    const recentEvents = state.visibleEvents.filter((event) => event.actor === selectedAgent && event.kind === "decision").slice(-3).reverse();
    els.agentDetailName.textContent = selectedAgent;
    els.agentDetail.className = "agent-detail";
    els.agentDetail.innerHTML = `
      <span class="detail-location">${escapeHtml(titleCase(current.location))}</span>
      <div class="detail-section"><h3>Traits</h3><div>${escapeHtml(agent.traits.join(" · "))}</div></div>
      <div class="detail-section"><h3>Goals</h3><ul>${agent.goals.map((goal) => `<li>${escapeHtml(goal)}</li>`).join("")}</ul></div>
      <div class="detail-section"><h3>Recent decisions</h3>${recentEvents.length ? recentEvents.map((event) => `<div class="memory">Tick ${event.tick}: ${escapeHtml(actionSummary(event))}${event.accepted === false ? ` · rejected (${escapeHtml(event.rejection_reason)})` : ""}</div>`).join("") : '<div class="memory">No recorded decisions yet.</div>'}</div>
      <div class="detail-section"><h3>Checkpoint memories by this tick</h3>${memories.length ? memories.map((memory) => `<div class="memory">Tick ${memory.tick}: ${escapeHtml(memory.text)}</div>`).join("") : '<div class="memory">No checkpoint memory recorded yet.</div>'}</div>`;
  }

  function eventText(event) {
    if (event.kind === "incident") return event.description || `${event.resource} changed at ${event.location}`;
    if (event.kind === "action") {
      const suffix = event.outcome?.ok === false ? " (not resolved)" : "";
      return `${event.actor}: ${actionSummary(event)}${suffix}`;
    }
    if (event.kind === "decision" && event.accepted === false) return `${event.actor} proposed ${actionSummary(event)}; WorldEngine rejected it: ${event.rejection_reason || "unknown"}.`;
    return null;
  }

  function renderEventStream(state) {
    const displayEvents = state.visibleEvents.filter((event) => event.kind === "incident" || event.kind === "action" || (event.kind === "decision" && event.accepted === false)).slice(-18).reverse();
    els.eventCount.textContent = String(displayEvents.length);
    if (!displayEvents.length) {
      els.eventStream.innerHTML = '<div class="empty-state">The record begins when tick 1 starts.</div>';
      return;
    }
    els.eventStream.innerHTML = displayEvents.map((event) => `
      <div class="event-row ${event.kind === "incident" ? "incident" : ""}">
        <div class="event-meta"><span>tick ${escapeHtml(event.tick)}</span><span>${escapeHtml(event.kind)}</span></div>
        <div>${escapeHtml(eventText(event) || "Recorded event")}</div>
      </div>`).join("");
  }

  function renderSummary(state) {
    const actions = state.visibleEvents.filter((event) => event.kind === "action");
    const incidents = state.visibleEvents.filter((event) => event.kind === "incident");
    const rejected = state.visibleEvents.filter((event) => event.kind === "decision" && event.accepted === false);
    if (tick === 0) els.tickSummary.textContent = "Initial state";
    else els.tickSummary.textContent = `${actions.length} resolved actions · ${incidents.length} incidents · ${rejected.length} rejected proposals so far`;

    if (state.incidentsThisTick.length) {
      els.incidentBadge.classList.remove("hidden");
      els.incidentBadge.textContent = state.incidentsThisTick.map((row) => row.description).join(" ");
    } else {
      els.incidentBadge.classList.add("hidden");
      els.incidentBadge.textContent = "";
    }
  }

  function render() {
    if (!data || !currentCondition) return;
    els.tick.textContent = String(tick);
    els.slider.value = String(tick);
    const state = stateAt(tick);
    renderSummary(state);
    renderMap(state);
    renderDecisions(state);
    renderAgentGrid(state);
    renderAgentDetail(state);
    renderEventStream(state);
  }

  function pause() {
    if (timer) window.clearInterval(timer);
    timer = null;
    els.play.textContent = "Play";
  }

  function play() {
    if (timer) {
      pause();
      return;
    }
    if (tick >= currentCondition.ticks) tick = 0;
    els.play.textContent = "Pause";
    const delay = Number(els.speed.value) || 900;
    timer = window.setInterval(() => {
      tick += 1;
      if (tick > currentCondition.ticks) {
        tick = currentCondition.ticks;
        pause();
      }
      render();
    }, delay);
  }

  function populateSelectors() {
    const temps = [...new Set(data.conditions.map((row) => row.temperature))].sort((a,b) => a-b);
    const seeds = [...new Set(data.conditions.map((row) => row.seed))].sort((a,b) => a-b);
    els.temperature.innerHTML = temps.map((temp) => `<option value="${temp}">${temp}</option>`).join("");
    els.seed.innerHTML = seeds.map((seed) => `<option value="${seed}">${seed}</option>`).join("");
    els.temperature.value = String(temps[0]);
    els.seed.value = String(seeds[0]);
  }

  function bindEvents() {
    els.temperature.addEventListener("change", () => { pause(); rebuildCondition(); });
    els.seed.addEventListener("change", () => { pause(); rebuildCondition(); });
    els.speed.addEventListener("change", () => { if (timer) { pause(); play(); } });
    els.play.addEventListener("click", play);
    els.back.addEventListener("click", () => { pause(); tick = Math.max(0, tick - 1); render(); });
    els.next.addEventListener("click", () => { pause(); tick = Math.min(currentCondition.ticks, tick + 1); render(); });
    els.slider.addEventListener("input", () => { pause(); tick = Number(els.slider.value); render(); });
  }

  async function start() {
    try {
      const response = await fetch("replay-data.json", {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
      populateSelectors();
      currentCondition = conditionFor(els.temperature.value, els.seed.value);
      selectedAgent = data.world.agents[0]?.name || null;
      renderEdges();
      bindEvents();
      const source = data.source;
      els.sourceLine.textContent = `Run #${source.run_number} · Falcon3-1B · ${data.conditions.length} recorded timelines`;
      els.footerSource.innerHTML = `Source: <a href="https://github.com/maaronfanberg-lab/me-/actions/runs/${encodeURIComponent(source.run_id)}" target="_blank" rel="noreferrer">GitHub Actions run #${escapeHtml(source.run_number)}</a> · artifact ${escapeHtml(source.artifact_id)}.`;
      render();
    } catch (error) {
      document.body.innerHTML = `<main class="shell"><section class="card" style="padding:24px"><h1>Cedar Hollow</h1><p>Replay data could not be loaded: ${escapeHtml(error.message)}</p></section></main>`;
    }
  }

  start();
})();
