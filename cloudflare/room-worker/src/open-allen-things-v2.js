import base, { RoomState, ThingsState as BaseThingsState } from "./open-allen-things.js";
import { BubbleState, handleBubbleApi } from "./bubble-api.js";

export { RoomState, BubbleState };

const STALE_JOB_MS = 15 * 60 * 1000;

export class ThingsState extends BaseThingsState {
  async pruneStaleJobs() {
    const now = Date.now();
    const queue = (await this.ctx.storage.get("thingsQueue")) || [];
    const kept = queue.filter((job) => {
      const createdAt = Number(job?.createdAt || 0);
      const leaseUntil = Number(job?.leaseUntil || 0);
      if (leaseUntil > now) return true;
      if (!createdAt) return false;
      return now - createdAt < STALE_JOB_MS;
    });
    if (kept.length !== queue.length) {
      await this.ctx.storage.put("thingsQueue", kept);
    }
    return { removed: queue.length - kept.length, queued: kept.length };
  }

  async enqueue(term, context, ip) {
    await this.pruneStaleJobs();
    return super.enqueue(term, context, ip);
  }

  async pending(limit = 4) {
    await this.pruneStaleJobs();
    return super.pending(limit);
  }

  async result(id) {
    await this.pruneStaleJobs();
    return super.result(id);
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/bubble/")) {
      return handleBubbleApi(request, env);
    }
    return base.fetch(request, env, ctx);
  },
};
