import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const sourcePath = process.argv[2] || "cloudflare/room-worker/src/index.js";
const source = await fs.readFile(sourcePath, "utf8");
const hashPattern = /const ALLEN_KEY_SHA256 = "([0-9a-f]{64})";/;
const hashMatch = source.match(hashPattern);

if (!hashMatch) {
  console.error(JSON.stringify({
    pass: false,
    invariant: "hash-fallback-present",
    reason: "ALLEN_KEY_SHA256 verifier is absent; Allen still depends on ROOM_ALLEN_KEY",
  }));
  process.exit(1);
}

const testKey = "simulator-only-allen-token-with-high-entropy-shape-6Vw4Qm9N2x";
const testHash = crypto.createHash("sha256").update(testKey, "utf8").digest("hex");
const importLine = 'import { DurableObject } from "cloudflare:workers";';
assert.ok(source.includes(importLine), "Worker import shape changed");

let runnable = source.replace(
  importLine,
  "class DurableObject { constructor(ctx, env) { this.ctx = ctx; this.env = env; } }",
);
runnable = runnable.replace(hashPattern, `const ALLEN_KEY_SHA256 = "${testHash}";`);

const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "room-allen-auth-"));
const tmpFile = path.join(tmpDir, "worker.mjs");
await fs.writeFile(tmpFile, runnable, "utf8");

try {
  const worker = await import(`${pathToFileURL(tmpFile).href}?t=${Date.now()}`);
  const queued = [];
  const stub = {
    async enqueueAllen(text) {
      queued.push(text);
      return { accepted: true, id: "sim-allen", at: new Date().toISOString(), queued: queued.length };
    },
    async getLatest() {
      return {
        feed: { state: { cycle: 1 }, conversation: [], minds: { entities: {} } },
        receivedAt: new Date().toISOString(),
      };
    },
  };
  const baseEnv = { ROOM: { getByName() { return stub; } } };

  function request(pathname, { key = "", method = "GET", body } = {}) {
    const headers = {};
    if (key) headers.Authorization = `Bearer ${key}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    return new Request(`https://sim.invalid${pathname}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }

  const fallbackGood = await worker.default.fetch(
    request("/api/allen/auth", { key: testKey }),
    baseEnv,
  );
  assert.equal(fallbackGood.status, 200, "hash-backed Allen token must authenticate without ROOM_ALLEN_KEY");
  assert.deepEqual(await fallbackGood.json(), { ok: true, identity: "Allen" });

  const fallbackBad = await worker.default.fetch(
    request("/api/allen/auth", { key: "wrong-token" }),
    baseEnv,
  );
  assert.equal(fallbackBad.status, 401, "wrong fallback token must be rejected");

  const noToken = await worker.default.fetch(request("/api/allen/auth"), baseEnv);
  assert.equal(noToken.status, 401, "missing token must be unauthorized, not key-not-configured");

  const legacyEnv = { ...baseEnv, ROOM_ALLEN_KEY: "legacy-secret" };
  const legacyGood = await worker.default.fetch(
    request("/api/allen/auth", { key: "legacy-secret" }),
    legacyEnv,
  );
  assert.equal(legacyGood.status, 200, "existing ROOM_ALLEN_KEY path must remain compatible");

  const post = await worker.default.fetch(
    request("/api/allen", { key: testKey, method: "POST", body: { text: "simulated Allen turn" } }),
    baseEnv,
  );
  assert.equal(post.status, 202, "hash-backed Allen token must be allowed to queue a turn");
  assert.deepEqual(queued, ["simulated Allen turn"]);

  console.log(JSON.stringify({
    pass: true,
    checks: [
      "fallback-auth-without-env-secret",
      "wrong-token-rejected",
      "missing-token-401",
      "legacy-cloudflare-secret-compatible",
      "fallback-post-queues-allen",
    ],
  }));
} finally {
  await fs.rm(tmpDir, { recursive: true, force: true });
}
