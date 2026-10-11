// Stage 4 engine proofs (offline). Run from the repo root: node qa-resonator/stage4_verify.mjs
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const H = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
const RATE = 32000, B = 128, E3 = 440 * Math.pow(2, (52 - 69) / 12);
let failed = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };
const same = (a, b) => { for (let i = 0; i < a.length; i++) if (!Object.is(a[i], b[i])) return false; return true; };
const peak = (x) => { let m = 0; for (const v of x) m = Math.max(m, Math.abs(v)); return m; };
const diff = (a, b) => { let m = 0; for (let i = 0; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i])); return m; };

function run({ shape = 'String', geo = null, mic = null, hit = null, xm = [], extra = {}, notes = [[1, 0]], blocks = 250 }) {
  const p = H.makeProc(RATE), S = H.SHAPES[shape], g = geo || S.make(S.def), m = d => p.port.onmessage({ data: d });
  const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i*3]=q[0]; pos[i*3+1]=q[1]; pos[i*3+2]=q[2]; });
  const mi = mic ?? g.mic, hi = hit ?? g.hit;
  m({ t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: mi, hit: hi, axis: g.axis });
  for (const k in H.KNOBS) if (!['size','mag','hit','mic','m1r','m1a','m2r','m2a','m3r','m3a'].includes(k)) m({ t: 'p', k, v: k in extra ? extra[k] : H.KNOBS[k].val });
  m({ t: 'mic', i: mi, a: g.axis }); m({ t: 'mic2', i: mi, a: g.axis }); m({ t: 'hit', i: hi, a: g.axis });
  xm.forEach((x, q) => m({ t: 'xmic', k: q, ...x }));
  const L = new Float32Array(blocks * B), R = new Float32Array(blocks * B), bl = new Float32Array(B), br = new Float32Array(B);
  let ni = 0;
  for (let b = 0; b < blocks; b++) {
    while (ni < notes.length && notes[ni][0] <= b) { m({ t: 'note', f: E3 * Math.pow(2, notes[ni][1] / 12), v: 0.9 }); ni++; }
    bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * B); R.set(br, b * B);
  }
  return { L, R, p, g };
}

// 1. an extra mic panned hard left changes only the left channel
{ const S = H.SHAPES.String.make(H.SHAPES.String.def); const free = S.P.map((_, i) => i).filter(i => !S.F[i]);
  const a = run({}), b = run({ xm: [{ i: free[free.length - 2], g: 0.8, p: -1 }] });
  check('extra mic, pan hard left: right channel untouched', same(a.R, b.R), 'right bit-identical');
  check('extra mic, pan hard left: left channel gains the new mic', diff(a.L, b.L) > 0.02, `left changes by up to ${diff(a.L, b.L).toFixed(3)}`);
  const c = run({ xm: [{ i: free[1], g: 0.8, p: 1 }] });
  check('extra mic, pan hard right: left untouched, right changes', same(a.L, c.L) && diff(a.R, c.R) > 0.02, `right changes by up to ${diff(a.R, c.R).toFixed(3)}`); }

// 2. extra mics hear every voice (4 voices, chord); removing the mic restores the original
{ const S = H.SHAPES.String.make(H.SHAPES.String.def); const free = S.P.map((_, i) => i).filter(i => !S.F[i]);
  const chord = [[1, 0], [1, 4], [1, 7], [1, 12]];
  const a = run({ extra: { voices: 4 }, notes: chord }), b = run({ extra: { voices: 4 }, notes: chord, xm: [{ i: free[3], g: 0.8, p: -1 }] });
  check('extra mic in 4-voice mode adds sound', diff(a.L, b.L) > 0.02 && same(a.R, b.R), `left changes by up to ${diff(a.L, b.L).toFixed(3)}, right identical`);
  const c = run({ xm: [{ i: free[3], g: 0.8, p: -1 }, { i: free[5], g: 0.8, p: 1 }] });
  const p = c.p; p.port.onmessage({ data: { t: 'xmic', k: 0, i: -1 } }); p.port.onmessage({ data: { t: 'xmic', k: 1, i: -1 } });
  check('removing extra mics stops them', p.xmN === 0, `active extra mics after removal: ${p.xmN}`); }

// 3. invalid positions are refused
{ const r = run({}); const p = r.p, fixedIdx = r.g.F.findIndex(f => f);
  p.port.onmessage({ data: { t: 'xmic', k: 0, i: fixedIdx } }); const a = p.xmI[0];
  p.port.onmessage({ data: { t: 'xmic', k: 1, i: 999 } }); const b = p.xmI[1];
  check('extra mic on a pinned mass or a missing mass is refused', a === -1 && b === -1, `pinned → ${a}, #999 → ${b}`); }

// 4. worst case stays under the output ceiling: three extra mics at 150 %, all hard left, 8 voices, drive
{ const S = H.SHAPES.String.make(H.SHAPES.String.def); const free = S.P.map((_, i) => i).filter(i => !S.F[i]);
  const xm = [free[1], free[3], free[5]].map(i => ({ i, g: 1.5, p: -1 }));
  const chord = [[1, 0], [1, 3], [1, 7], [1, 10], [1, 12], [1, 15], [1, 19], [1, 24]];
  const r = run({ xm, extra: { voices: 8, drive: 3, nl: 4 }, notes: chord, blocks: 400 });
  let bad = 0; for (const v of r.L) if (!isFinite(v)) bad++; for (const v of r.R) if (!isFinite(v)) bad++;
  check('worst case (3 mics at 150 %, hard left, 8 voices, drive): peak under the ceiling, no NaN', peak(r.L) <= 0.78 && peak(r.R) <= 0.78 && bad === 0,
    `peak L ${peak(r.L).toFixed(3)}, R ${peak(r.R).toFixed(3)} (limit 0.78), non-finite samples ${bad}`); }

// 5. deterministic: the same extra-mic setup renders identically twice
{ const S = H.SHAPES.Drum.make(H.SHAPES.Drum.def); const free = S.P.map((_, i) => i).filter(i => !S.F[i]);
  const o = { shape: 'Drum', xm: [{ i: free[2], g: 0.9, p: -0.4 }, { i: free[free.length - 3], g: 0.6, p: 0.7 }] };
  const a = run(o), b = run(o);
  check('extra mics are deterministic', same(a.L, b.L) && same(a.R, b.R), 'two renders bit-identical'); }

// 6. calibrated: an extra mic at 100 % on the main mic's own ball adds about the main mic's level
{ const rms = x => { let e = 0; for (const v of x) e += v * v; return Math.sqrt(e / x.length); };
  const rows = Object.keys(H.SHAPES).map(shape => { const g = H.SHAPES[shape].make(H.SHAPES[shape].def);
    const a = run({ shape, blocks: 300 }), b = run({ shape, blocks: 300, xm: [{ i: g.mic, g: 1, p: 0 }] });
    return [shape, 20 * Math.log10(rms(b.L.map((v, i) => v - a.L[i])) / rms(a.L))]; });
  const dbs = rows.map(r => r[1]).sort((x, y) => x - y), med = (dbs[3] + dbs[4]) / 2;
  check('extra mic at 100 % ≈ main mic level (median within ±2 dB, every shape within ±8 dB)', Math.abs(med) <= 2 && dbs.every(d => Math.abs(d) <= 8),
    rows.map(r => `${r[0]} ${r[1] >= 0 ? '+' : ''}${r[1].toFixed(1)}`).join(' · ') + ` dB (median ${med.toFixed(1)})`); }
console.log(failed ? `\n${failed} check(s) FAILED` : '\nall Stage 4 engine proofs pass');
process.exit(failed ? 1 : 0);
