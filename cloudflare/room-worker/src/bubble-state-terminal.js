import { BubbleState as BaseBubbleState, cleanId } from "./bubble-state.js";

const STATE_KEY = "bubbleSimulationV1";

function finiteNumber(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * BubbleState wrapper that distinguishes a resolved physical collapse from a
 * numerical/software failure. A collapse is a successful terminal event for
 * the coupled run, so every worker can stop cleanly on its next coordinator
 * interaction instead of reporting a failed cluster.
 */
export class BubbleState extends BaseBubbleState {
  async status() {
    const summary = await super.status();
    const state = await this.ctx.storage.get(STATE_KEY);
    if (!state || !state.terminalEvent) return summary;
    return { ...summary, terminal_event: state.terminalEvent };
  }

  async task(node) {
    const result = await super.task(node);
    if (result?.status !== "complete") return result;
    const state = await this.ctx.storage.get(STATE_KEY);
    if (!state?.terminalEvent) return result;
    return { ...result, terminal_event: state.terminalEvent };
  }

  async submit(node, stamp = {}, result = {}) {
    if (!(result?.success && result?.collapsed)) {
      return super.submit(node, stamp, result);
    }

    const state = await this.ctx.storage.get(STATE_KEY);
    if (!state) return { accepted: false, reason: "missing" };
    if (state.status !== "running") {
      const summary = await this.status();
      return { accepted: false, reason: state.status, ...summary };
    }

    const n = Math.trunc(Number(node));
    if (!(n >= 0 && n < state.nodeCount)) return { accepted: false, reason: "invalid-node" };
    if (
      Math.trunc(Number(stamp.macrostep)) !== state.macrostep ||
      Math.trunc(Number(stamp.iteration)) !== state.iteration ||
      Math.trunc(Number(stamp.version)) !== state.version
    ) {
      return { accepted: false, reason: "stale", current: await this.status() };
    }

    const R = finiteNumber(result.R, NaN);
    const U = finiteNumber(result.U, NaN);
    const K = finiteNumber(result.emitted_pressure_coeff, NaN);
    if (!(R > 0) || !Number.isFinite(U) || !Number.isFinite(K)) {
      return { accepted: false, reason: "invalid-result" };
    }

    state.status = "complete";
    state.failure = "";
    state.terminalEvent = {
      type: "physical-collapse",
      node: n,
      macrostep: state.macrostep,
      iteration: state.iteration,
      sim_time: finiteNumber(result.t_end, state.simTime),
      R,
      U,
      max_wall_mach: finiteNumber(result.max_wall_mach, 0),
      solver: String(result.solver || ""),
      recorded_at: Date.now(),
    };
    state.history.push({
      macrostep: state.macrostep,
      sim_time: state.terminalEvent.sim_time,
      event: "physical-collapse",
      node: n,
      radius: R,
      wall_velocity: U,
      max_wall_mach: state.terminalEvent.max_wall_mach,
    });
    if (state.history.length > 200) state.history = state.history.slice(-200);
    state.updatedAt = Date.now();
    await this.ctx.storage.put(STATE_KEY, state);

    return { accepted: true, phase: "complete", ...(await this.status()) };
  }
}

export { cleanId };
