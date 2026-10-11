// Stage 1 engine proofs (offline). Run from the repo root: node qa-resonator/stage1_verify.mjs
//  T1  live page vs preview page, ordinary (synchronous) tuning: bit-identical audio across shapes,
//      sizes, features, strike modes and pickups.
//  T2  preview page with the shadow-engine (asynchronous) tuning vs its own synchronous tuning:
//      bit-identical audio through load, notes, Stiffness, Substrate and mass moves.
//  T3  the octave trap: the live page drops an octave, the preview page must not.
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const LIVE = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator.html'));
const NEXT = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
let failed = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };
const same = (a, b) => { if (a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (!Object.is(a[i], b[i])) return false; return true; };

// ---------- T1 ----------
{
  const configs = [];
  for (const shape of Object.keys(NEXT.SHAPES)) { const S = NEXT.SHAPES[shape];
    for (const n of [...new Set([S.min, S.def, S.max])]) configs.push({ shape, n }); }
  for (const params of [{ att: 0.8 }, { regime: 1 }, { infer: 1, voices: 4, spread: 1 }, { mem: 1 }, { bow: 0.16 },
    { att: 0.8, fxCho: 0.6, fxDly: 0.6, fxWow: 0.6, fxTrem: 0.6, fxSat: 0.6 }, { voices: 8, nl: 4, drive: 3 },
    { width: 1, spImg: 1, spRefl: 1, spRot: 1 }, { fbAmt: 0.8, amp: 1, cab: 1 }]) configs.push({ params });
  configs.push({ mode: 1 }, { pk: 1 }, { pk: 2 }, { mods: [{ d: 'tune', r: 4, a: 1, sh: 4 }] }, { hitF: 0.5, micF: 0.1 });
  let ok = 0; const bad = [];
  for (const c of configs) {
    const a = LIVE.render({ secs: 2, rate: 32000, ...c }), b = NEXT.render({ secs: 2, rate: 32000, ...c });
    if (same(a.L, b.L) && same(a.R, b.R)) ok++; else bad.push(JSON.stringify(c));
  }
  check('T1 live vs preview, synchronous tuning, bit-identical', bad.length === 0, `${ok}/${configs.length} configs identical` + (bad.length ? ' · differ: ' + bad.join(' ') : ''));
}

// ---------- T2 ----------
// Drive two preview engines with the same message script: one tunes itself (synchronous), the other
// gets its tables from a shadow engine exactly the way the page's tuner delivers them.
function scriptFor(H, shape) {
  const S = H.SHAPES[shape], g = S.make(S.def);
  const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  const struct = { t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis };
  const knobs = Object.keys(H.KNOBS).filter(k => !['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k)).map(k => ({ t: 'p', k, v: H.KNOBS[k].val }));
  const free = g.P.map((_, i) => i).filter(i => !g.F[i]), mid = free[Math.floor(free.length / 2)];
  const E3 = 440 * Math.pow(2, (52 - 69) / 12), note = (semi, v = 0.9) => ({ t: 'note', f: E3 * Math.pow(2, semi / 12), v });
  const p0 = g.P[mid];
  return [  // [time in blocks, message]
    [0, struct], ...knobs.map(m => [0, m]), [0, { t: 'mic', i: g.mic, a: g.axis }], [0, { t: 'hit', i: g.hit, a: g.axis }],
    [2, note(0)], [60, note(7)],
    [120, { t: 'p', k: 'ratio', v: 9.5 }], [125, note(3)],
    [200, { t: 'p', k: 'sub', v: 0.004 }], [205, note(5)],
    [280, { t: 'mv', i: mid, x: p0[0] + 0.03, y: p0[1] + 0.02, z: p0[2] }], [285, note(0, 0.6)],
  ];
}
function run(H, shape, async) {
  const p = H.makeProc(32000), shadow = async ? H.makeProc(32000) : null;
  const send = d => p.port.onmessage({ data: d });
  if (async) send({ t: 'asyncCal', v: 1 });
  const script = scriptFor(H, shape), B = 128, nb = 360, L = new Float32Array(nb * B), R = new Float32Array(nb * B), bl = new Float32Array(B), br = new Float32Array(B);
  let si = 0, pendingRecal = false;
  for (let b = 0; b < nb; b++) {
    while (si < script.length && script[si][0] <= b) {
      const m = script[si++][1];
      if (!async) { send(m); continue; }
      if (m.t === 'struct') {
        // the page's tuner: the shadow takes the body without tuning it, folds in the burst of
        // messages that follows (up to the next note), tunes once, and the engine receives the body
        // with that table, then the burst
        const real = shadow.calibrate; shadow.calibrate = () => {};
        shadow.port.onmessage({ data: m }); shadow.calibrate = real;
        const burst = [];
        while (si < script.length && script[si][0] <= b && script[si][1].t !== 'note' && script[si][1].t !== 'struct') burst.push(script[si++][1]);
        for (const x of burst) shadow.port.onmessage({ data: x });
        shadow.calibrate(); shadow.calDirty = false;
        send(Object.assign({}, m, { cal: shadow.calState() }));
        for (const x of burst) send(x);
        pendingRecal = false; continue;
      }
      if (m.t !== 'note') { shadow.port.onmessage({ data: m }); if (shadow.calDirty) pendingRecal = true; send(m); continue; }
      if (pendingRecal) { shadow.calibrate(); shadow.calDirty = false; send({ t: 'cal', cal: shadow.calState() }); pendingRecal = false; }
      send(m);
    }
    bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * B); R.set(br, b * B);
  }
  return { L, R };
}
{
  const rows = [];
  for (const shape of Object.keys(NEXT.SHAPES)) {
    const a = run(NEXT, shape, false), b = run(NEXT, shape, true);
    rows.push([shape, same(a.L, b.L) && same(a.R, b.R)]);
  }
  check('T2 shadow-engine tuning vs synchronous tuning, bit-identical', rows.every(r => r[1]), rows.map(r => r[0] + (r[1] ? ' ✓' : ' ✗')).join(' · '));
}

// ---------- T3 ----------
{
  const NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];
  const name = f => { const m = Math.round(69 + 12 * Math.log2(f / 440)); return NAMES[(m % 12 + 12) % 12] + (Math.floor(m / 12) - 1); };
  const E3 = 440 * Math.pow(2, (52 - 69) / 12);
  const trap = (H, shape) => {
    const p = H.makeProc(32000), S = H.SHAPES[shape], g = S.make(S.def), m = d => p.port.onmessage({ data: d });
    const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
    m({ t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
    for (const k in H.KNOBS) if (!['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k)) m({ t: 'p', k, v: H.KNOBS[k].val });
    m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
    const heard = () => { m({ t: 'note', f: E3, v: 0.9 }); const kT = p.vkTt[0], q = p.kLfor(kT); return p.modeSpectrum(kT, q.kL, Math.max(p.sub, p.anchored ? 0 : 1e-5) * kT)[0].f; };
    const free = g.P.map((_, i) => i).filter(i => !g.F[i]);
    const a = heard(); m({ t: 'hit', i: free[1], a: g.axis }); heard(); m({ t: 'p', k: 'ratio', v: 6.45 }); const c = heard();
    return [name(a), name(c)];
  };
  for (const shape of ['String', 'Twins']) {
    const live = trap(LIVE, shape), next = trap(NEXT, shape);
    check(`T3 octave trap, ${shape}`, next[0] === 'E3' && next[1] === 'E3', `live: ${live[0]} → ${live[1]} · preview: ${next[0]} → ${next[1]}`);
  }
}
console.log(failed ? `\n${failed} check(s) FAILED` : '\nall Stage 1 engine proofs pass');
process.exit(failed ? 1 : 0);
