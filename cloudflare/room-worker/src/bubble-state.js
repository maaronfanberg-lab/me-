import { DurableObject } from "cloudflare:workers";

const STATE_KEY = "bubbleSimulationV1";

function finiteNumber(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clamp(value, lo, hi) {
  return Math.max(lo, Math.min(hi, value));
}

function cleanId(value) {
  const id = String(value || "").trim().toLowerCase();
  return /^[a-z0-9][a-z0-9._-]{5,80}$/.test(id) ? id : null;
}

function baseParams(raw = {}) {
  const out = {
    rho: finiteNumber(raw.rho, 997.0),
    mu: finiteNumber(raw.mu, 8.9e-4),
    sigma: finiteNumber(raw.sigma, 0.072),
    c: finiteNumber(raw.c, 1480.0),
    p0: finiteNumber(raw.p0, 101325.0),
    pv: finiteNumber(raw.pv, 2339.0),
    R0: finiteNumber(raw.R0, 10e-6),
    kappa: finiteNumber(raw.kappa, 1.4),
    drive_amplitude: finiteNumber(raw.drive_amplitude, 5000.0),
    drive_frequency: finiteNumber(raw.drive_frequency, 20000.0),
  };
  if (!(out.rho > 0 && out.c > 0 && out.R0 > 0 && out.kappa > 0)) throw new Error("invalid-bubble-parameters");
  if (out.mu < 0 || out.sigma < 0 || out.p0 < 0 || out.pv < 0 || out.drive_frequency < 0) {
    throw new Error("invalid-bubble-parameters");
  }
  return out;
}

function ringPositions(count, nearestSpacing) {
  if (count === 1) return [[0, 0, 0]];
  const radius = nearestSpacing / (2 * Math.sin(Math.PI / count));
  return Array.from({ length: count }, (_, i) => {
    const a = 2 * Math.PI * i / count;
    return [radius * Math.cos(a), radius * Math.sin(a), 0];
  });
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function compactSummary(s) {
  if (!s) return null;
  return {
    status: s.status,
    node_count: s.nodeCount,
    sim_time: s.simTime,
    end_time: s.endTime,
    macrostep: s.macrostep,
    iteration: s.iteration,
    dt: s.dt,
    version: s.version,
    coupling_residual_abs: s.lastResidualAbs,
    coupling_residual_rel: s.lastResidualRel,
    rollbacks: s.rollbacks,
    accepted_steps: s.acceptedSteps,
    warnings: s.warnings.slice(-12),
    last_step: s.history.length ? s.history[s.history.length - 1] : null,
    failure: s.failure || null,
  };
}

export class BubbleState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
  }

  async initialize(raw = {}) {
    const existing = await this.ctx.storage.get(STATE_KEY);
    if (existing && !raw.reset) return { accepted: false, reason: "already-exists", ...compactSummary(existing) };

    const nodeCount = clamp(Math.trunc(finiteNumber(raw.node_count, 12)), 2, 12);
    const model = String(raw.model || "km").toLowerCase() === "rp" ? "rp" : "km";
    const common = baseParams(raw.params || {});
    const radiusSpread = clamp(finiteNumber(raw.radius_spread_fraction, 0.02), 0, 0.20);
    const spacing = finiteNumber(raw.nearest_spacing_m, 1.0e-3);
    if (!(spacing > 20 * common.R0)) throw new Error("nearest_spacing_m must exceed 20 R0 for v1 far-field coupling");

    const macroDtDefault = common.drive_frequency > 0 ? 1.0 / (common.drive_frequency * 40.0) : 1e-6;
    const dt = finiteNumber(raw.macro_dt, macroDtDefault);
    const endTimeDefault = common.drive_frequency > 0 ? 5.0 / common.drive_frequency : 100 * dt;
    const endTime = finiteNumber(raw.end_time, endTimeDefault);
    const minDt = finiteNumber(raw.min_macro_dt, dt / 32.0);
    if (!(dt > 0 && endTime > 0 && minDt > 0 && minDt <= dt)) throw new Error("invalid-time-configuration");

    const paramsByNode = Array.from({ length: nodeCount }, (_, i) => {
      const phase = 2 * Math.PI * i / nodeCount;
      return { ...common, R0: common.R0 * (1 + radiusSpread * Math.cos(phase)) };
    });
    const checkpoints = paramsByNode.map((p) => [p.R0, 0.0]);
    const positions = ringPositions(nodeCount, spacing);

    const state = {
      schema: 1,
      status: "running",
      nodeCount,
      model,
      paramsByNode,
      positions,
      nearestSpacing: spacing,
      simTime: 0.0,
      endTime,
      macrostep: 0,
      iteration: 0,
      dt,
      initialDt: dt,
      minDt,
      maxIterations: clamp(Math.trunc(finiteNumber(raw.max_corrections, 3)), 1, 8),
      couplingRelTol: clamp(finiteNumber(raw.coupling_rel_tol, 1e-3), 1e-8, 0.5),
      couplingAbsTol: Math.max(0, finiteNumber(raw.coupling_abs_tol_pa, 0.5)),
      underRelax: clamp(finiteNumber(raw.under_relaxation, 0.65), 0.05, 1.0),
      rtol: clamp(finiteNumber(raw.rtol, 1e-8), 1e-12, 1e-3),
      checkpoints,
      couplingStart: Array(nodeCount).fill(0.0),
      couplingGuess: Array(nodeCount).fill(0.0),
      submissions: {},
      version: 1,
      lastResidualAbs: 0.0,
      lastResidualRel: 0.0,
      acceptedSteps: 0,
      rollbacks: 0,
      warnings: [
        "v1 inter-bubble coupling uses an instantaneous leading monopole p=K/r field; finite sound-travel retardation is not yet modeled."
      ],
      history: [],
      failure: "",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    await this.ctx.storage.put(STATE_KEY, state);
    return { accepted: true, ...compactSummary(state) };
  }

  async status() {
    const s = await this.ctx.storage.get(STATE_KEY);
    return s ? compactSummary(s) : { status: "missing" };
  }

  async task(node) {
    const s = await this.ctx.storage.get(STATE_KEY);
    if (!s) return { status: "missing" };
    const n = Math.trunc(Number(node));
    if (!(n >= 0 && n < s.nodeCount)) return { status: "invalid-node" };
    if (s.status !== "running") return compactSummary(s);

    const key = String(n);
    if (s.submissions[key]) {
      return {
        status: "waiting",
        node: n,
        macrostep: s.macrostep,
        iteration: s.iteration,
        version: s.version,
        submitted_nodes: Object.keys(s.submissions).length,
        required_nodes: s.nodeCount,
      };
    }

    const tEnd = Math.min(s.simTime + s.dt, s.endTime);
    return {
      status: "work",
      node: n,
      macrostep: s.macrostep,
      iteration: s.iteration,
      version: s.version,
      t_start: s.simTime,
      t_end: tEnd,
      checkpoint: s.checkpoints[n],
      coupling_start: s.couplingStart[n],
      coupling_end: s.couplingGuess[n],
      model: s.model,
      params: s.paramsByNode[n],
      rtol: s.rtol,
    };
  }

  _couplingFromSubmissions(s) {
    const outputs = Array(s.nodeCount).fill(0.0);
    for (let target = 0; target < s.nodeCount; target += 1) {
      let pressure = 0.0;
      for (let source = 0; source < s.nodeCount; source += 1) {
        if (source === target) continue;
        const row = s.submissions[String(source)]?.result;
        const K = finiteNumber(row?.emitted_pressure_coeff, NaN);
        const d = distance(s.positions[target], s.positions[source]);
        if (!Number.isFinite(K) || !(d > 0)) throw new Error("invalid-coupling-submission");
        pressure += K / d;
      }
      outputs[target] = pressure;
    }
    return outputs;
  }

  async submit(node, stamp = {}, result = {}) {
    const s = await this.ctx.storage.get(STATE_KEY);
    if (!s) return { accepted: false, reason: "missing" };
    if (s.status !== "running") return { accepted: false, reason: s.status, ...compactSummary(s) };

    const n = Math.trunc(Number(node));
    if (!(n >= 0 && n < s.nodeCount)) return { accepted: false, reason: "invalid-node" };
    if (
      Math.trunc(Number(stamp.macrostep)) !== s.macrostep ||
      Math.trunc(Number(stamp.iteration)) !== s.iteration ||
      Math.trunc(Number(stamp.version)) !== s.version
    ) {
      return { accepted: false, reason: "stale", current: compactSummary(s) };
    }

    const R = finiteNumber(result.R, NaN);
    const U = finiteNumber(result.U, NaN);
    const K = finiteNumber(result.emitted_pressure_coeff, NaN);
    if (!(R > 0) || !Number.isFinite(U) || !Number.isFinite(K)) {
      return { accepted: false, reason: "invalid-result" };
    }
    if (!result.success || result.collapsed) {
      s.status = "failed";
      s.failure = `node-${n}-${result.collapsed ? "collapse-event" : "integration-failure"}`;
      s.updatedAt = Date.now();
      await this.ctx.storage.put(STATE_KEY, s);
      return { accepted: false, reason: s.failure, ...compactSummary(s) };
    }

    s.submissions[String(n)] = {
      result: {
        R,
        U,
        A: finiteNumber(result.A, 0),
        min_R: finiteNumber(result.min_R, R),
        max_R: finiteNumber(result.max_R, R),
        max_abs_U: finiteNumber(result.max_abs_U, Math.abs(U)),
        max_wall_mach: finiteNumber(result.max_wall_mach, 0),
        emitted_pressure_coeff: K,
        solver: String(result.solver || ""),
        nfev: Math.trunc(finiteNumber(result.nfev, 0)),
      },
      receivedAt: Date.now(),
    };

    if (Object.keys(s.submissions).length < s.nodeCount) {
      s.updatedAt = Date.now();
      await this.ctx.storage.put(STATE_KEY, s);
      return {
        accepted: true,
        phase: "waiting",
        submitted_nodes: Object.keys(s.submissions).length,
        required_nodes: s.nodeCount,
        macrostep: s.macrostep,
        iteration: s.iteration,
        version: s.version,
      };
    }

    const newCoupling = this._couplingFromSubmissions(s);
    let maxAbs = 0.0;
    let maxRel = 0.0;
    for (let i = 0; i < s.nodeCount; i += 1) {
      const delta = Math.abs(newCoupling[i] - s.couplingGuess[i]);
      maxAbs = Math.max(maxAbs, delta);
      maxRel = Math.max(maxRel, delta / Math.max(1.0, Math.abs(newCoupling[i]), Math.abs(s.couplingGuess[i])));
    }
    s.lastResidualAbs = maxAbs;
    s.lastResidualRel = maxRel;

    const converged = maxAbs <= s.couplingAbsTol || maxRel <= s.couplingRelTol;
    if (converged) {
      const previousStart = s.couplingStart.slice();
      s.checkpoints = Array.from({ length: s.nodeCount }, (_, i) => {
        const r = s.submissions[String(i)].result;
        return [r.R, r.U];
      });
      const acceptedIteration = s.iteration;
      const acceptedDt = Math.min(s.dt, s.endTime - s.simTime);
      s.simTime += acceptedDt;
      s.macrostep += 1;
      s.iteration = 0;
      s.acceptedSteps += 1;
      s.couplingStart = newCoupling;
      s.couplingGuess = newCoupling.map((value, i) => value + 0.35 * (value - previousStart[i]));
      const rows = Object.values(s.submissions).map((x) => x.result);
      s.history.push({
        macrostep: s.macrostep - 1,
        sim_time: s.simTime,
        dt: acceptedDt,
        corrections: acceptedIteration,
        coupling_residual_abs: maxAbs,
        coupling_residual_rel: maxRel,
        max_wall_mach: Math.max(...rows.map((r) => r.max_wall_mach)),
        min_radius: Math.min(...rows.map((r) => r.min_R)),
        max_radius: Math.max(...rows.map((r) => r.max_R)),
      });
      if (s.history.length > 200) s.history = s.history.slice(-200);
      if (acceptedIteration === 0 && s.dt < s.initialDt) s.dt = Math.min(s.initialDt, s.dt * 1.5);
      if (s.history[s.history.length - 1].max_wall_mach > 0.1) {
        s.warnings.push(`macrostep-${s.macrostep - 1}: wall Mach exceeded 0.1; Keller-Miksis weak-compressibility validity should be scrutinized.`);
        if (s.warnings.length > 40) s.warnings = s.warnings.slice(-40);
      }
      s.submissions = {};
      s.version += 1;
      if (s.simTime >= s.endTime * (1 - 1e-12)) {
        s.simTime = s.endTime;
        s.status = "complete";
      }
      s.updatedAt = Date.now();
      await this.ctx.storage.put(STATE_KEY, s);
      return { accepted: true, phase: s.status === "complete" ? "complete" : "advanced", ...compactSummary(s) };
    }

    if (s.iteration + 1 < s.maxIterations) {
      s.couplingGuess = s.couplingGuess.map((old, i) => old + s.underRelax * (newCoupling[i] - old));
      s.iteration += 1;
      s.submissions = {};
      s.version += 1;
      s.updatedAt = Date.now();
      await this.ctx.storage.put(STATE_KEY, s);
      return { accepted: true, phase: "correct", ...compactSummary(s) };
    }

    const nextDt = s.dt / 2.0;
    if (nextDt >= s.minDt * (1 - 1e-12)) {
      s.dt = nextDt;
      s.iteration = 0;
      s.rollbacks += 1;
      s.couplingGuess = s.couplingStart.slice();
      s.submissions = {};
      s.version += 1;
      s.history.push({
        macrostep: s.macrostep,
        sim_time: s.simTime,
        event: "rollback",
        next_dt: s.dt,
        coupling_residual_abs: maxAbs,
        coupling_residual_rel: maxRel,
      });
      if (s.history.length > 200) s.history = s.history.slice(-200);
      s.updatedAt = Date.now();
      await this.ctx.storage.put(STATE_KEY, s);
      return { accepted: true, phase: "rollback", ...compactSummary(s) };
    }

    s.status = "failed";
    s.failure = "coupling-nonconvergence-at-minimum-macrostep";
    s.updatedAt = Date.now();
    await this.ctx.storage.put(STATE_KEY, s);
    return { accepted: false, reason: s.failure, ...compactSummary(s) };
  }
}

export { cleanId };
