#!/usr/bin/env python3
from pathlib import Path

path = Path('cloudflare/room-worker/src/index.js')
text = path.read_text(encoding='utf-8')
old = '''  async putLatest(feed, sourceSha = "") {
    const incomingCycle = Number(feed?.state?.cycle || 0);
    const current = await this.ctx.storage.get("latest");
    const currentCycle = Number(current?.feed?.state?.cycle || 0);
    if (current && incomingCycle < currentCycle) {
      return { accepted: false, cycle: currentCycle, reason: "older-cycle" };
    }
    const record = {
      feed,
      receivedAt: new Date().toISOString(),
      sourceSha,
    };
    await this.ctx.storage.put("latest", record);
    return { accepted: true, cycle: incomingCycle, receivedAt: record.receivedAt };
  }
'''
new = '''  async putLatest(feed, sourceSha = "") {
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
'''
if old not in text:
    if new in text:
        print('Room Worker reboot-order fix already present')
        raise SystemExit(0)
    raise SystemExit('expected putLatest baseline block not found; refusing to patch')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('patched RoomState.putLatest with boot-aware timestamp ordering')
