// One steady-state cost measurement in a fresh process (several engine copies in one process share
// compiled code and distort each other's timing; the phone runs exactly one). Prints a fraction of
// real time spent in process(), after a 1.5 s warm-up. Used by p1_verify.mjs.
//   node qa-resonator/p1_cost_one.mjs <page.html> '<json options>'
const [, , src, json] = process.argv;
const H = await import('./harness.mjs?src=' + src);
const o = JSON.parse(json), rate = 32000;
const p = H.makeProc(rate), S = H.SHAPES[o.shape || 'String'], g = S.make(S.def), NN = g.P.length;
const pos = new Float32Array(NN * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
const m = d => p.port.onmessage({ data: d });
m({ t: 'struct', n: NN, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
const params = o.params || {};
for (const k in H.KNOBS) if (!['size', 'mag', 'hit', 'mic', 'm1r', 'm1a', 'm2r', 'm2a', 'm3r', 'm3a'].includes(k)) m({ t: 'p', k, v: k in params ? params[k] : H.KNOBS[k].val });
m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
if (o.perf) m({ t: 'perf', ...o.perf });
const notes = o.notes ?? Array.from({ length: 64 }, (_, i) => ({ at: i * 0.25, semi: [0, 3, 5, 7, 10, 12, 7, 3][i % 8], v: i % 2 ? 0.55 : 0.9 }));
const secs = o.secs || 6, warm = 1.5, B = 128, nb = Math.ceil(secs * rate / B);
const L = new Float32Array(B), R = new Float32Array(B);
let ni = 0, busy = 0, frames = 0;
for (let b = 0; b < nb; b++) {
  const t = b * B / rate;
  while (ni < notes.length && notes[ni].at <= t) { const n = notes[ni++]; m({ t: 'note', f: 440 * Math.pow(2, (52 + n.semi - 69) / 12), v: n.v }); }
  const t0 = performance.now(); p.process([], [[L, R]]); const dt = performance.now() - t0;
  if (t >= warm) { busy += dt; frames += B; }
}
process.stdout.write(String(busy / 1000 / (frames / rate)));
