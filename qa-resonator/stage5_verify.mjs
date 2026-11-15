// Stage 5 engine proofs (offline): envelopes and envelope followers as modulators, and Depth 0 returning
// the destination to its own setting. Run from the repo root: node qa-resonator/stage5_verify.mjs
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const LIVE = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator.html'));
const H = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
const RATE = 32000, B = 128, E3 = 440 * Math.pow(2, (52 - 69) / 12);
let failed = 0;
const check = (name, ok, detail) => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };
const same = (a, b) => { if (a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (!Object.is(a[i], b[i])) return false; return true; };
const peak = x => { let m = 0; for (const v of x) m = Math.max(m, Math.abs(v)); return m; };
const rms = (x, a = 0, b = x.length) => { let e = 0; for (let i = a; i < b; i++) e += x[i] * x[i]; return Math.sqrt(e / (b - a)); };

function proc(M, shape = 'String', extra = {}) {
  const p = M.makeProc(RATE), S = M.SHAPES[shape], g = S.make(S.def), m = d => p.port.onmessage({ data: d });
  const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i*3]=q[0]; pos[i*3+1]=q[1]; pos[i*3+2]=q[2]; });
  m({ t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: g.mic, hit: g.hit, axis: g.axis });
  for (const k in M.KNOBS) if (!['size','mag','hit','mic','m1r','m1a','m2r','m2a','m3r','m3a'].includes(k) && !/^m[123](at|dc|su|rl|fa|fr|se)$/.test(k)) m({ t: 'p', k, v: k in extra ? extra[k] : M.KNOBS[k].val });
  m({ t: 'mic', i: g.mic, a: g.axis }); m({ t: 'mic2', i: g.mic, a: g.axis }); m({ t: 'hit', i: g.hit, a: g.axis });
  return { p, m, g };
}
// the page's message for an envelope / follower modulator
const SENS = Math.pow(64, 0.36);   // the page's default sensitivity (+13 dB)
const env = (i, d, a, { A = 0.005, D = 0.3, S = 0, R = 0.3, inv = 0 } = {}) => ({ t: 'mod', i, d, r: 1, a, sh: 0, ty: 1, inv, src: 0, A, D, S, R, fa: 0.022, fr: 0.05, sens: SENS });
const fol = (i, d, a, { src = 0, fa = 0.022, fr = 0.05, sens = SENS, inv = 0 } = {}) => ({ t: 'mod', i, d, r: 1, a, sh: 0, ty: 2, inv, src, A: 0.005, D: 0.3, S: 0, R: 0.3, fa, fr, sens });
const note = (semi = 0) => ({ t: 'note', f: E3 * Math.pow(2, semi / 12), v: 0.9 });
const off = (semi = 0) => ({ t: 'off', f: E3 * Math.pow(2, semi / 12) });
function render(p, blocks, script = {}, input = null) {
  const L = new Float32Array(blocks * B), R = new Float32Array(blocks * B), bl = new Float32Array(B), br = new Float32Array(B);
  for (let b = 0; b < blocks; b++) {
    for (const d of script[b] || []) p.port.onmessage({ data: d });
    bl.fill(0); br.fill(0); p.process(input ? [[input(b)]] : [], [[bl, br]]); L.set(bl, b * B); R.set(br, b * B);
  }
  return { L, R };
}
// per-sample trace of one modulator's value (1-sample blocks)
function trace(p, samples, at = {}, input = null, k = 0) {
  const out = new Float64Array(samples), bl = new Float32Array(1), br = new Float32Array(1);
  for (let n = 0; n < samples; n++) {
    for (const d of at[n] || []) p.port.onmessage({ data: d });
    p.process(input ? [[Float32Array.of(input(n))]] : [], [[bl, br]]); out[n] = p.mods[k].e;
  }
  return out;
}

// 1. LFOs are untouched: live vs preview, every wave, several destinations, bit-identical
{ let ok = 0, n = 0; const bad = [];
  for (const sh of [0, 1, 2, 3, 4]) for (const [d, r, a] of [['tune', 3, 0.2], ['loss', 0.7, 0.5], ['tone', 9, 0.6], ['drive', 40, 0.3]]) {
    const run = M => { const { p } = proc(M); p.port.onmessage({ data: { t: 'mod', i: 1, d, r, a, sh } }); return render(p, 160, { 2: [note(0)], 80: [note(5)] }); };
    const x = run(LIVE), y = run(H); n++; if (same(x.L, y.L) && same(x.R, y.R)) ok++; else bad.push(`${d}/${sh}`); }
  check('LFOs unchanged: live vs preview, 5 waves × 4 destinations, bit-identical', ok === n, `${ok}/${n} identical` + (bad.length ? ' · differ: ' + bad.join(' ') : '')); }

// 2. Depth 0 returns the destination to its own setting (the live page leaves it stuck)
{ const stuck = M => { const { p, m } = proc(M); m({ t: 'mod', i: 0, d: 'tune', r: 0.3, a: 0.5, sh: 0 }); render(p, 300);
    const during = p.tune; m({ t: 'mod', i: 0, d: 'tune', r: 0.3, a: 0, sh: 0 }); render(p, 20); return [during, p.tune]; };
  const lv = stuck(LIVE), nx = stuck(H);
  const { p, m } = proc(H); m(env(0, 'loss', 0.8, { A: 0.002, D: 2, S: 0.5 })); render(p, 40, { 1: [note(0)] }); const mid = p.loss;
  m(Object.assign(env(0, 'loss', 0, { A: 0.002, D: 2, S: 0.5 }))); render(p, 4);
  check('Depth 0 returns the destination to its own setting (LFO and envelope)', Math.abs(nx[0]) > 50 && nx[1] === 0 && mid > H.KNOBS.loss.val + 0.1 && p.loss === H.KNOBS.loss.val,
    `Pitch: LFO at 50% → ${nx[0].toFixed(0)} cents, Depth 0 → ${nx[1]} (live page stays at ${lv[1].toFixed(0)}) · Damping: envelope → ${mid.toFixed(2)}, Depth 0 → ${p.loss} (own setting ${H.KNOBS.loss.val})`); }

// 3. envelope timing: each segment arrives in its set time (derived from the curve: attack aims at 1.5,
//    decay/release aim 0.05 past their goal), sample-exact within 1 ms
{ const A = 0.010, D = 0.100, S = 0.5, R = 0.200, fs = RATE;
  const { p, m } = proc(H); m(env(0, 'tone', 0.5, { A, D, S, R }));
  const tr = trace(p, Math.round(0.6 * fs), { 10: [note(0)], [10 + Math.round(0.25 * fs)]: [off(0)] });
  const t1 = tr.findIndex(v => v >= 1) - 10, tS = tr.findIndex((v, n) => n > 10 + t1 && v <= S) - (10 + t1);
  const r0 = 10 + Math.round(0.25 * fs), tz = tr.findIndex((v, n) => n > r0 && v <= 0) - r0;
  const expR = R * Math.log((S + 0.05) / 0.05) / Math.log(21);   // release from S, not from 1
  const ms = x => (1000 * x / fs).toFixed(2);
  check('envelope segments arrive in their set times', Math.abs(t1 - A * fs) <= 32 && Math.abs(tS - D * fs) <= 32 && Math.abs(tz - expR * fs) <= 32,
    `attack ${ms(t1)} ms (set 10) · decay to 50% ${ms(tS)} ms (set 100) · release from 50% ${ms(tz)} ms (expected ${(1000 * expR).toFixed(2)})`); }

// 4. retrigger during release continues from where it is (no jump), and the gate waits for the last key
{ const { p, m } = proc(H); m(env(0, 'tone', 0.5, { A: 0.02, D: 0.05, S: 0.8, R: 0.4 }));
  const at = { 10: [note(0)], 4000: [off(0)], 6000: [note(3)] };
  const tr = trace(p, 9000, at); let jump = 0; for (let n = 1; n < tr.length; n++) jump = Math.max(jump, Math.abs(tr[n] - tr[n - 1]));
  const before = tr[5999], after = tr[6000];
  const g = proc(H); g.m(env(0, 'tone', 0.5, { A: 0.002, D: 0.05, S: 0.6, R: 0.2 }));
  const tg = trace(g.p, 12000, { 10: [note(0)], 200: [note(4)], 3000: [off(0)], 8000: [off(4)] });
  check('retrigger continues from the current level; release waits for the last key', after >= before && jump < 0.02 && Math.abs(tg[7999] - 0.6) < 1e-9 && tg[11999] < 0.6 * 0.5,
    `retrigger at ${before.toFixed(3)} → ${after.toFixed(3)}, largest step ${jump.toFixed(4)} · one of two keys up: ${tg[7999].toFixed(3)} (sustain 0.6) · both up: ${tg[11999].toFixed(3)}`); }

// 5. an envelope on Tone is heard: with Tone muffled, the attack opens up (spectral centroid, first 60 ms),
//    and once the envelope has finished the sound matches the plain one again
{ const cen = (x, a, b) => { // centroid via a direct DFT over 64 bins up to 8 kHz on a Hann window
    const N = b - a; let num = 0, den = 0;
    for (let k = 1; k <= 64; k++) { const f = k * 125; let re = 0, im = 0; for (let n = 0; n < N; n++) { const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * n / N), v = x[a + n] * w; re += v * Math.cos(2 * Math.PI * f * n / RATE); im -= v * Math.sin(2 * Math.PI * f * n / RATE); } const pw = re * re + im * im; num += f * pw; den += pw; }
    return num / den; };
  const base = proc(H, 'String', { tone: 400 }), withEnv = proc(H, 'String', { tone: 400 });
  withEnv.m(env(0, 'tone', 1, { A: 0.002, D: 0.25, S: 0 }));
  const a = render(base.p, 160, { 2: [note(0)] }), b = render(withEnv.p, 160, { 2: [note(0)] });
  const s0 = 2 * B, w = Math.round(0.06 * RATE), l0 = Math.round(0.45 * RATE), l1 = Math.round(0.6 * RATE);
  const ca = cen(a.L, s0, s0 + w), cb = cen(b.L, s0, s0 + w), la = cen(a.L, l0, l1), lb = cen(b.L, l0, l1);
  check('an envelope on Tone opens the attack, then the sound returns to plain', cb > 1.25 * ca && Math.abs(lb / la - 1) < 0.05,
    `spectral centroid, first 60 ms: ${ca.toFixed(0)} Hz plain, ${cb.toFixed(0)} Hz with (+${(100 * (cb / ca - 1)).toFixed(0)}%) · 0.45–0.6 s: ${la.toFixed(0)} vs ${lb.toFixed(0)} Hz`); }

// 6. follower step response matches the detector's equations (smooth decoupled peak detector):
//    rise y = 1 − e^(−t/τA); fall y = (τR e^(−t/τR) − τA e^(−t/τA)) / (τR − τA)
{ const fa = 0.010, fr = 0.060, fs = RATE;
  const { p, m } = proc(H); m(fol(0, 'tone', 0.5, { src: 4, fa, fr, sens: 1 }));
  const on = Math.round(0.3 * fs), tr = trace(p, Math.round(0.7 * fs), {}, n => (n < on ? 0.5 : 0));
  const rise = tr.findIndex(v => v >= 0.5 * (1 - Math.exp(-1))), fall = tr.findIndex((v, n) => n > on && v <= 0.5 * Math.exp(-1)) - on;
  let tf = 0; for (let t = 0; t < 1; t += 1e-6) { if ((fr * Math.exp(-t / fr) - fa * Math.exp(-t / fa)) / (fr - fa) <= Math.exp(-1)) { tf = t; break; } }
  check('follower rise and fall match the detector equations', Math.abs(rise - fa * fs) <= 2 && Math.abs(fall - tf * fs) <= 3 && Math.abs(tr[on - 1] - 0.5) < 1e-6,
    `63% rise ${(1000 * rise / fs).toFixed(2)} ms (τA ${1000 * fa}) · fall to 37% ${(1000 * fall / fs).toFixed(2)} ms (equation ${(1000 * tf).toFixed(2)}) · settles at ${tr[on - 1].toFixed(4)}`); }

// 7. follower on Mic 1 follows the note; an extra mic that is off gives nothing; Damping follower shortens notes
{ const { p, m } = proc(H); m(fol(0, 'tone', 0.4, { src: 0 }));
  const tr = []; const bl = new Float32Array(B), br = new Float32Array(B);
  for (let b = 0; b < 400; b++) { if (b === 2) m(note(0)); p.process([], [[bl, br]]); tr.push(p.mods[0].e); }
  const top = Math.max(...tr), late = tr[399];
  const x = proc(H); x.m(fol(0, 'tone', 0.4, { src: 2 })); const tx = []; for (let b = 0; b < 100; b++) { if (b === 2) x.m(note(0)); x.p.process([], [[bl, br]]); tx.push(x.p.mods[0].e); }
  const plain = proc(H), damp = proc(H); damp.m(fol(0, 'loss', 1, { src: 0 }));
  const a = render(plain.p, 400, { 2: [note(0)] }), b = render(damp.p, 400, { 2: [note(0)] });
  const w0 = Math.round(0.4 * RATE), w1 = Math.round(1.2 * RATE), ra = rms(a.L, w0, w1), rb = rms(b.L, w0, w1);
  check('follower tracks Mic 1; an off mic gives nothing; follower on Damping shortens the ring', top > 0.6 && late < 0.5 * top && Math.max(...tx) === 0 && rb < 0.7 * ra,
    `Mic 1: peak ${top.toFixed(2)}, 1.6 s later ${late.toFixed(2)} · Mic 3 (off): ${Math.max(...tx)} · level 0.4–1.2 s: ${ra.toFixed(4)} plain, ${rb.toFixed(4)} with the Damping follower (${(20 * Math.log10(rb / ra)).toFixed(1)} dB)`); }

// 7b. calibrated: at the default sensitivity a firm hit moves a Mic 1 follower most of the way on every
//     shape (it hears the shape-trimmed level, as you do), and a softer hit moves it less
{ const fsrc = await import('node:fs'); const html = fsrc.readFileSync(path.join(root, 'apps/resonator-next.html'), 'utf8');
  const SL = JSON.parse(html.match(/const SHAPE_LVL=(\{[^}]*\})/)[1].replace(/(\w+):/g, '"$1":'));
  const rows = Object.keys(H.SHAPES).map(shape => { const hit = vel => { const { p, m } = proc(H, shape); m({ t: 'lvl', v: SL[shape] }); m(fol(0, '', 0));
      let top = 0; const bl = new Float32Array(B), br = new Float32Array(B); for (let b = 0; b < 200; b++) { if (b === 2) m({ t: 'note', f: E3, v: vel }); p.process([], [[bl, br]]); top = Math.max(top, p.mods[0].e); } return top; };
    return [shape, hit(0.9), hit(0.55)]; });
  check('follower calibrated: firm hits reach most of the range on every shape; softer hits less', rows.every(r => r[1] >= 0.6 && (r[2] < r[1] || r[1] === 1)),
    rows.map(r => `${r[0]} ${r[1].toFixed(2)}/${r[2].toFixed(2)}`).join(' · ') + ' (firm/soft)'); }

// 8. deterministic, and the worst case stays under the ceiling with no NaN
{ const run = () => { const { p, m } = proc(H, 'Drum', { voices: 4 }); m(env(0, 'tune', 0.3, { A: 0.003, D: 0.2 })); m(fol(1, 'drive', 0.6, { src: 0 })); m({ t: 'mod', i: 2, d: 'tone', r: 5, a: 0.4, sh: 4 });
    return render(p, 200, { 2: [note(0), note(4)], 60: [off(0)], 100: [note(7)], 150: [off(4), off(7)] }); };
  const a = run(), b = run();
  const { p, m } = proc(H, 'String', { voices: 8, drive: 3, nl: 4 });
  m(env(0, 'fbAmt', 1, { A: 0.001, D: 1, S: 1 })); m(fol(1, 'gain', 1, { src: 0, sens: 16 })); m(env(2, 'ratio', 1, { A: 0.001, D: 0.05, S: 1, inv: 1 }));
  const w = render(p, 500, { 2: [0, 3, 7, 10, 12, 15, 19, 24].map(note) });
  let bad = 0; for (const v of w.L) if (!isFinite(v)) bad++; for (const v of w.R) if (!isFinite(v)) bad++;
  check('deterministic; worst case under the ceiling, no NaN', same(a.L, b.L) && same(a.R, b.R) && peak(w.L) <= 0.78 && peak(w.R) <= 0.78 && bad === 0,
    `two renders identical: ${same(a.L, b.L) && same(a.R, b.R)} · worst case peak ${peak(w.L).toFixed(3)} / ${peak(w.R).toFixed(3)} (limit 0.78), non-finite ${bad}`); }

// 9. meters: frames carry modulator values only when an envelope or follower exists; hush resets them
{ const { p, m } = proc(H); const sent = []; p.port.postMessage = d => sent.push(d);
  render(p, 40); const plain = sent.filter(d => d.t === 'frame'); sent.length = 0;
  m(env(1, 'tone', 0.5, { A: 0.002, D: 2, S: 1 })); render(p, 40, { 1: [note(0)] }); const withEnv = sent.filter(d => d.t === 'frame');
  m({ t: 'hush' }); const e = p.mods[1].e, held = p.nHeld;
  check('meters only when used; hush resets envelopes', plain.length > 0 && plain.every(d => !('mv' in d)) && withEnv.length > 0 && withEnv.every(d => d.mv && d.mv.length === 3) && withEnv[withEnv.length - 1].mv[1] > 0.9 && e === 0 && held === 0,
    `plain frames with values: ${plain.filter(d => 'mv' in d).length}/${plain.length} · envelope frames: ${withEnv.length}, last value ${withEnv.length ? withEnv[withEnv.length - 1].mv[1].toFixed(2) : '-'} · after hush ${e}, keys held ${held}`); }

console.log(failed ? `\n${failed} check(s) FAILED` : '\nall Stage 5 engine proofs pass');
process.exit(failed ? 1 : 0);
