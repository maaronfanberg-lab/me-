// Stage I proof: the engine messages two pages actually sent (recorded in the browser by i1_browser.py),
// replayed into the same engine. If the Tank-only page and the page before Stage I sent the same things for
// the same taps, the sound is bit-identical.
//   node qa-resonator/i1_replay.mjs before.json after.json [page.html]
// Each file: {rate, msgs:[{...message}]} in the order the page posted them. Replay: everything from the
// first Tank body on (plus asyncCal), except 'perf' (the CPU governor depends on timing, not on the page),
// all at once; 0.2 s of sound; then the recorded notes; 3 s more.
import fs from 'node:fs';
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const [fa, fb] = process.argv.slice(2, 4);
const page = process.argv[4] || path.join(root, 'apps/resonator-next.html');
const H = await import('./harness.mjs?src=' + page);
const B = 128;
const typed = (m) => {   // the recorder wrote typed arrays as {__t: name, v: [...]}
  const o = {};
  for (const [k, v] of Object.entries(m)) o[k] = v && v.__t ? new globalThis[v.__t](v.v) : v;
  return o;
};
function replay(file) {
  const { rate, msgs } = JSON.parse(fs.readFileSync(file, 'utf8'));
  const first = msgs.findIndex(m => m.t === 'struct' && m.n === 58);   // the Tank at its default Size (7 rings of 7 + caps)
  if (first < 0) throw new Error(file + ': no Tank body in the recording');
  const setup = [], notes = [];
  msgs.forEach((m, i) => {
    if (m.t === 'perf') return;
    if (i < first && m.t !== 'asyncCal') return;
    (m.t === 'note' || m.t === 'off' ? notes : setup).push(typed(m));
  });
  const p = H.makeProc(rate), send = d => p.port.onmessage({ data: d });
  setup.forEach(send);
  const L = [], R = [], bl = new Float32Array(B), br = new Float32Array(B);
  const run = secs => { for (let b = 0; b < Math.ceil(secs * rate / B); b++) { bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.push(...bl); R.push(...br); } };
  run(0.2); notes.forEach(send); run(3);
  const kinds = {}; setup.forEach(m => { kinds[m.t] = (kinds[m.t] || 0) + 1; });
  let pk = 0; for (const v of L) pk = Math.max(pk, Math.abs(v));
  return { L, R, kinds, notes: notes.length, pk, last: Object.fromEntries(setup.filter(m => m.t === 'p').map(m => [m.k, m.v])) };
}
const a = replay(fa), b = replay(fb);
let same = a.L.length === b.L.length, diff = 0;
for (let i = 0; i < Math.min(a.L.length, b.L.length); i++) { if (!Object.is(a.L[i], b.L[i]) || !Object.is(a.R[i], b.R[i])) same = false; diff = Math.max(diff, Math.abs(a.L[i] - b.L[i]), Math.abs(a.R[i] - b.R[i])); }
const keys = new Set([...Object.keys(a.last), ...Object.keys(b.last)]);
const differ = [...keys].filter(k => a.last[k] !== b.last[k]).map(k => `${k}: ${a.last[k]} → ${b.last[k]}`);
console.log(JSON.stringify({ same, maxDiff: diff, peak: [a.pk, b.pk], notes: [a.notes, b.notes], kinds: [a.kinds, b.kinds], paramDiffers: differ }));
process.exit(same && a.pk > 0.01 && a.notes > 0 ? 0 : 1);
