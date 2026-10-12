// Stage H: every number the Learn tab teaches, and every factory preset's description, measured on the
// engine with exactly what the page sends. The lessons, presets and presetFrom() are read from the page
// itself, so the text checked is the text shipped.
//   node qa-resonator/h1_claims.mjs [page]         (default apps/resonator-next.html)
//   H1_RATES=32000 node ...                          (only the phone's default engine rate)
// The page's message sequence is mirrored here: restore() -> rebuild() (body built with the shape's own
// strike and mic), the strike and mics moved to the preset's, modulators, spectrum, bow; then the
// lesson's change (lessonApply) and the key (lessonPlay: E4, strength 0.8, held for the lesson's hold).
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const isMain = import.meta.url === pathToFileURL(process.argv[1] || '').href;
const PAGE = path.resolve((isMain && process.argv[2]) || process.env.H1_PAGE || path.join(root, 'apps/resonator-next.html'));
const H = await import('./harness.mjs?src=' + PAGE);
const { lufs, truePeakDb } = await import('./metrics.mjs');
const html = fs.readFileSync(PAGE, 'utf8');

// ---------- read the page ----------
const cut = (a, b) => { const i = html.indexOf(a); if (i < 0) throw new Error('page: missing ' + a); const j = html.indexOf(b, i); if (j < 0) throw new Error('page: missing ' + b); return html.slice(i, j); };
const { FACTORY, presetFrom } = new Function('SHAPES', 'KNOBS', cut('const FACTORY=[', '// H: Learn.') + '\nreturn {FACTORY,presetFrom};')(H.SHAPES, H.KNOBS);
const LESSONS = new Function(cut('const LESSONS=[', 'const LEARN=') + '\nreturn LESSONS;')();
const RB = html.slice(html.indexOf('function rebuild(){'));
const KNOB_LIST = JSON.parse(RB.slice(RB.indexOf('for(const k of [') + 15, RB.indexOf('])send(k)') + 1).replace(/'/g, '"'));
const LVL = new Function(cut('const SHAPE_LVL=', '\n') + '\nreturn SHAPE_LVL;')();
const RATEF = v => 0.01 * Math.pow(200000, v), MTIME = v => 0.001 * Math.pow(10000, v);
const B = 128, E3 = 52;

let failed = 0;
const check = (name, ok, detail = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); if (!ok) failed++; };

// ---------- the page's messages, mirrored ----------
function modMsg(i, val, m) {
  const msg = { t: 'mod', i, d: m.d, r: RATEF(val[['m1r', 'm2r', 'm3r'][i]]), a: val[['m1a', 'm2a', 'm3a'][i]], sh: m.sh };
  if (m.ty) { const p = 'm' + (i + 1); msg.ty = m.ty; msg.inv = m.dn ? 1 : 0; msg.src = m.src || 0;
    msg.A = MTIME(val[p + 'at']); msg.D = MTIME(val[p + 'dc']); msg.S = val[p + 'su']; msg.R = MTIME(val[p + 'rl']);
    msg.fa = MTIME(val[p + 'fa']); msg.fr = MTIME(val[p + 'fr']); msg.sens = Math.pow(64, val[p + 'se']); }
  return msg;
}
function structMsg(o, mic, hit, axis) {
  const pos = new Float32Array(o.P.length * 3); o.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  return { t: 'struct', n: o.P.length, pos, fixed: Uint8Array.from(o.F), si: Int32Array.from(o.S.map(s => s[0])), sj: Int32Array.from(o.S.map(s => s[1])), mic, hit, axis };
}
const freeOf = o => o.P.map((_, i) => i).filter(i => !o.F[i]);
// a fresh engine with the page's restore(o) applied; returns a session to change and play
function session(rate, o) {
  const p = H.makeProc(rate), m = d => p.port.onmessage({ data: d }), val = Object.assign({}, o.val), mods = o.mods.map(x => Object.assign({}, x));
  const st = { p, m, val, mods, o, rate, shape: o.shape, mode: o.mode, free: freeOf(o), axis: o.axis, mic: o.micIdx, hit: o.hitIdx };
  const rebuildMsgs = (mic, hit, axis) => { m(structMsg(st.o, mic, hit, axis)); for (const k of KNOB_LIST) m({ t: 'p', k, v: val[k] });
    m({ t: 'pk', v: st.o.pk || 0 }); m({ t: 'mode', v: st.mode || 0 }); m({ t: 'lvl', v: LVL[st.shape] || 1 });
    for (let q = 0; q < 3; q++) m({ t: 'xmic', k: q, i: -1, g: 0.7, p: [-0.6, 0.6, 0][q] }); };
  st.pickSend = () => { const F = st.free, n = F.length, k = Math.max(0, F.indexOf(st.mic));
    m({ t: 'mic', i: st.mic, a: st.axis }); m({ t: 'mic2', i: F[(k + Math.max(1, Math.floor(n / 2))) % n] }); m({ t: 'hit', i: st.hit, a: st.axis }); };
  const r = o.ref; rebuildMsgs(r ? r.m : o.micIdx, r ? r.h : o.hitIdx, r ? r.a : o.axis);
  st.pickSend();
  for (let i = 0; i < 3; i++) m(modMsg(i, val, mods[i]));
  m({ t: 'spec', v: o.spec || 0 });
  if ('bow' in val) m({ t: 'p', k: 'bow', v: val.bow });
  // lessonApply
  st.apply = (ch, L) => { for (const [k, v] of Object.entries(ch)) {
    if (k === 'shape') { if (v !== st.shape) { const S = H.SHAPES[v], n = S.def, g = S.make(n); st.shape = v; st.o = { ...st.o, shape: v, n, P: g.P, F: Array.from(g.F), S: g.S, axis: g.axis };
      st.free = freeOf(st.o); st.axis = g.axis; st.mic = g.mic; st.hit = g.hit; val.size = (n - S.min) / (S.max - S.min);
      if (g.needSub && val.sub < g.needSub) val.sub = g.needSub; rebuildMsgs(g.mic, g.hit, g.axis); m({ t: 'spec', v: 0 }); } }
    else if (k === 'mode') { st.mode = v; m({ t: 'mode', v }); }
    else if (k === 'env') { const md = mods[0], e = L.env; md.d = v ? 'tone' : ''; md.sh = 0; md.ty = v ? 1 : 0; md.dn = 0; md.src = 0;
      val.m1a = v ? e.a : 0; val.m1at = e.at; val.m1dc = e.dc; val.m1su = e.su; val.m1rl = e.rl; m(modMsg(0, val, md)); }
    else if (k === 'hit' || k === 'mic') { val[k] = v; const F = st.free, n = F.length; st.mic = F[Math.min(n - 1, Math.round(val.mic * (n - 1)))]; st.hit = F[Math.min(n - 1, Math.round(val.hit * (n - 1)))];
      m({ t: 'mic', i: st.mic, a: st.axis }); m({ t: 'mic2', i: F[(Math.round(val.mic * (n - 1)) + Math.max(1, Math.floor(n / 2))) % n] }); m({ t: 'hit', i: st.hit, a: st.axis }); }
    else { val[k] = v; m({ t: 'p', k, v }); } } };
  // render with key events [{at, semi, v, off}] (seconds); returns the take
  st.render = (secs, keys = []) => { const nb = Math.ceil(secs * rate / B), L = new Float32Array(nb * B), R = new Float32Array(nb * B), bl = new Float32Array(B), br = new Float32Array(B);
    const ev = []; for (const k of keys) { const f = 440 * Math.pow(2, (E3 + k.semi - 69) / 12); ev.push([Math.round(k.at * rate / B), { t: 'note', f, v: k.v }]); if (k.off != null) ev.push([Math.round(k.off * rate / B), { t: 'off', f }]); }
    ev.sort((a, b) => a[0] - b[0]); let e = 0;
    for (let b = 0; b < nb; b++) { while (e < ev.length && ev[e][0] <= b) m(ev[e++][1]); bl.fill(0); br.fill(0); p.process([], [[bl, br]]); L.set(bl, b * B); R.set(br, b * B); }
    return { L, R, rate, t0: keys.length ? Math.round(keys[0].at * rate / B) * B / rate : 0, p }; };
  return st;
}
// one lesson tap: setup from the base, apply A or B, play E4 at 0.8 for the lesson's hold
function lessonTake(rate, L, which, secs = 2.6) {
  const st = session(rate, presetFrom(L.base)); st.apply(L[which][1], L);
  const hold = L.hold || 0.15; return st.render(secs, [{ at: 0.05, semi: 12, v: 0.8, off: 0.05 + hold }]);
}

// ---------- measurements ----------
function fftMag(x, start, len, rate) {
  const N = 1 << Math.ceil(Math.log2(len)), re = new Float64Array(N), im = new Float64Array(N);
  for (let i = 0; i < len && start + i < x.length; i++) re[i] = x[start + i] * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / len));
  for (let i = 1, j = 0; i < N; i++) { let b = N >> 1; for (; j & b; b >>= 1) j ^= b; j ^= b; if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let L = 2; L <= N; L <<= 1) { const a = -2 * Math.PI / L; for (let i = 0; i < N; i += L) for (let k = 0; k < L / 2; k++) {
    const c = Math.cos(a * k), s = Math.sin(a * k), p = i + k, q = p + L / 2, tr = re[q] * c - im[q] * s, ti = re[q] * s + im[q] * c;
    re[q] = re[p] - tr; im[q] = im[p] - ti; re[p] += tr; im[p] += ti; } }
  const mag = new Float64Array(N / 2); for (let k = 0; k < N / 2; k++) mag[k] = Math.hypot(re[k], im[k]);
  return { mag, df: rate / N };
}
// brightness centre: the energy-weighted mean frequency over a window (seconds after the key)
const centroid = (r, a, b) => { const { mag, df } = fftMag(r.L, Math.round((r.t0 + a) * r.rate), Math.round((b - a) * r.rate), r.rate);
  let num = 0, den = 0; for (let k = 1; k < mag.length; k++) { const e = mag[k] * mag[k]; num += e * k * df; den += e; } return num / den; };
const peakOf = (x, a = 0, b = x.length) => { let pk = 0; for (let i = a; i < b; i++) pk = Math.max(pk, Math.abs(x[i])); return pk; };
// time from the key until the last 10 ms block above `db` below the peak
const tdrop = (r, db) => { const x = r.L, pk = peakOf(x), thr = pk * Math.pow(10, -db / 20), W = Math.round(0.01 * r.rate); let last = 0;
  for (let i = 0; i + W < x.length; i += W) if (peakOf(x, i, i + W) > thr) last = i + W; return last / r.rate - r.t0; };
const levelAt = (r, a, b) => 20 * Math.log10(peakOf(r.L, Math.round((r.t0 + a) * r.rate), Math.round((r.t0 + b) * r.rate)) / peakOf(r.L));
// the engine's own partials at the pitch it is playing (voice 0)
const modes = (r) => { const p = r.p, kT = p.vkTt[0], q = p.kLfor(kT); return [...new Set(p.modeSpectrum(kT, q.kL, Math.max(p.sub, p.anchored ? 0 : 1e-5) * kT).map(s => +s.f.toFixed(3)))]; };
const partials = (r, fs, a, b) => { const { mag, df } = fftMag(r.L, Math.round((r.t0 + a) * r.rate), Math.round((b - a) * r.rate), r.rate);
  return fs.map(f => { let mx = 0; for (let k = Math.floor(f * 0.985 / df); k <= Math.ceil(f * 1.015 / df); k++) mx = Math.max(mx, mag[k] || 0); return 20 * Math.log10(mx + 1e-30); }); };
// time for one partial to fall `db` below its own peak (Goertzel, 64 ms frames every 16 ms)
function partialDecay(r, f, db = 30) {
  const N = Math.round(0.064 * r.rate), hop = Math.round(0.016 * r.rate), x = r.L, lv = [];
  for (let s = Math.round(r.t0 * r.rate); s + N < x.length; s += hop) { let s1 = 0, s2 = 0; const c = 2 * Math.cos(2 * Math.PI * f / r.rate);
    for (let i = 0; i < N; i++) { const w = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N), s0 = x[s + i] * w + c * s1 - s2; s2 = s1; s1 = s0; }
    lv.push(10 * Math.log10(s1 * s1 + s2 * s2 - c * s1 * s2 + 1e-30)); }
  let pk = -1e9, pi = 0; lv.forEach((v, i) => { if (v > pk) { pk = v; pi = i; } });
  let last = pi; for (let i = pi; i < lv.length; i++) if (lv[i] > pk - db) last = i;
  return { t: (last - pi) * hop / r.rate, censored: last === lv.length - 1 }; }
// the strongest frequency in a window, refined by parabolic interpolation (for pitch glides)
function domFreq(r, a, b, lo = 60, hi = 2000) { const { mag, df } = fftMag(r.L, Math.round((r.t0 + a) * r.rate), Math.round((b - a) * r.rate), r.rate);
  let bk = 0, bv = 0; for (let k = Math.ceil(lo / df); k < Math.min(mag.length - 1, hi / df); k++) if (mag[k] > bv) { bv = mag[k]; bk = k; }
  const y0 = Math.log(mag[bk - 1] + 1e-30), y1 = Math.log(mag[bk] + 1e-30), y2 = Math.log(mag[bk + 1] + 1e-30), d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 || 1);
  return (bk + d) * df; }
const near = (v, want, tol) => Math.abs(v - want) <= tol;
const rel = (v, want, frac) => Math.abs(v - want) <= frac * Math.abs(want);
const has = (L, strs) => strs.filter(x => !L.why.includes(x));
const lesson = t => { const L = LESSONS.find(x => x.t === t); if (!L) throw new Error('no lesson ' + t); return L; };

export { FACTORY, LESSONS, presetFrom, session, lessonTake, centroid, tdrop, levelAt, modes, partials, partialDecay, domFreq, lufs, truePeakDb };
if (isMain) {
// ---------- the lessons ----------
const RATES = (process.env.H1_RATES || '32000,22050,48000').split(',').map(Number);
check('the page has 9 A/B lessons and 1 how-to', LESSONS.filter(L => !L.how).length === 9 && LESSONS.filter(L => L.how).length === 1, LESSONS.map(L => L.t).join(' | '));
for (const rate of RATES) {
  const tag = ` @ ${rate / 1000} kHz`;
  { const L = lesson('Hard or soft'), A = lessonTake(rate, L, 'A'), Bt = lessonTake(rate, L, 'B');
    const ca = centroid(A, 0, 0.6), cb = centroid(Bt, 0, 0.6), dl = lufs(A.L, A.R, rate) - lufs(Bt.L, Bt.R, rate), miss = has(L, ['1030 Hz', '330 Hz', '7 dB']);
    check('1 Hard or soft' + tag, rel(ca, 1030, 0.06) && rel(cb, 330, 0.04) && near(dl, 7, 1.2) && !miss.length,
      `brightness centre ${ca.toFixed(0)} → ${cb.toFixed(0)} Hz; soft ${dl.toFixed(1)} dB quieter${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('Pluck or ring'), A = lessonTake(rate, L, 'A'), Bt = lessonTake(rate, L, 'B', 3.5);
    const ta = tdrop(A, 60), tb = tdrop(Bt, 60), ca = centroid(A, 0, 0.05), cb = centroid(Bt, 0, 0.05), miss = has(L, ['0.5 s', '1.9 s', '520 Hz']);
    check('2 Pluck or ring' + tag, near(ta, 0.5, 0.06) && near(tb, 1.9, 0.1) && rel(ca, 520, 0.04) && rel(cb, 520, 0.04) && !miss.length,
      `60 dB down after ${ta.toFixed(2)} s vs ${tb.toFixed(2)} s; attack centre ${ca.toFixed(0)} vs ${cb.toFixed(0)} Hz${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('Ringing metal, dull wood'), A = lessonTake(rate, L, 'A', 7), Bt = lessonTake(rate, L, 'B', 3), fs = modes(A).slice(0, 4);
    const da = [0, 1].map(i => partialDecay(A, fs[i])), db = [0, 1, 2, 3].map(i => partialDecay(Bt, fs[i]).t), miss = has(L, ['4 s', '0.9 s', '0.3 s', 'a tenth of a second']);
    const ok = da.every(d => !d.censored && near(d.t, 4, 0.5)) && rel(da[1].t, da[0].t, 0.08) && near(db[0], 0.9, 0.1) && near(db[1], 0.3, 0.06) && db[2] <= 0.16 && db[3] <= 0.16 && db[2] >= 0.03;
    check('3 Ringing metal, dull wood' + tag, ok && !miss.length,
      `30 dB down: no damping ${da.map(d => d.t.toFixed(2) + (d.censored ? '+' : '')).join(' / ')} s (note / octave); damped ${db.map(t => t.toFixed(2)).join(' / ')} s (partials 1–4)${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('Where you strike'), A = lessonTake(rate, L, 'A'), Bt = lessonTake(rate, L, 'B'), fs = modes(A).slice(0, 4);
    const pa = partials(A, fs, 0.05, 1.5), pb = partials(Bt, fs, 0.05, 1.5), a2 = pa[1] - pa[0], b2 = pb[1] - pb[0], d3 = Math.abs((pa[2] - pa[0]) - (pb[2] - pb[0])), miss = has(L, ['13 dB', '68 dB']);
    check('4 Where you strike' + tag, near(a2, -13, 2) && near(b2, -68, 6) && d3 < 8 && rel(fs[0], 329.63, 0.01) && !miss.length,
      `partials ${fs.map(f => f.toFixed(0)).join('/')} Hz; 2nd partial ${a2.toFixed(0)} → ${b2.toFixed(0)} dB re the note; 3rd moves ${d3.toFixed(1)} dB${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('Where you listen'), A = lessonTake(rate, L, 'A'), Bt = lessonTake(rate, L, 'B'), fs = modes(A).slice(0, 4);
    const pa = partials(A, fs, 0.05, 1.5), pb = partials(Bt, fs, 0.05, 1.5), a2 = pa[1] - pa[0], b2 = pb[1] - pb[0], miss = has(L, ['11 dB', '99 dB']);
    check('5 Where you listen' + tag, near(a2, -11, 2) && b2 <= -88 && near(b2, -99, 12) && rel(fs[0], 329.63, 0.01) && !miss.length,
      `partials ${fs.map(f => f.toFixed(0)).join('/')} Hz; 2nd partial ${a2.toFixed(0)} → ${b2.toFixed(0)} dB re the note${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('Pitch or no pitch'), A = lessonTake(rate, L, 'A'), Bt = lessonTake(rate, L, 'B');
    const ra = modes(A).slice(0, 4), rb = modes(Bt).slice(0, 4), qa = ra.map(f => (f / ra[0]).toFixed(2)), qb = rb.map(f => (f / rb[0]).toFixed(2));
    const miss = has(L, ['1 : ' + qa.slice(1).join(' : '), '1 : ' + qb.slice(1).join(' : ')]);
    check('6 Pitch or no pitch' + tag, !miss.length && rel(ra[0], 329.63, 0.01), `string ${qa.join(' : ')}, drum ${qb.join(' : ')}${miss.length ? '; text lacks ' + miss : ''}`);
    if (rate === RATES[0]) {   // the real round drum quoted beside it: zeros of the Bessel functions J0, J1, J2 (Fletcher & Rossing, 3.6)
      const J = (n, x) => { let s = 0; const N = 2000; for (let i = 0; i < N; i++) { const t = Math.PI * (i + 0.5) / N; s += Math.cos(n * t - x * Math.sin(t)); } return s / N; };
      const zero = (n, a, b) => { for (let i = 0; i < 60; i++) { const m = (a + b) / 2; if (J(n, a) * J(n, m) <= 0) b = m; else a = m; } return (a + b) / 2; };
      const z = [zero(0, 2, 3), zero(1, 3.5, 4.2), zero(2, 4.8, 5.4), zero(0, 5.2, 5.8)], q = z.map(x => (x / z[0]).toFixed(2)), m2 = has(L, ['1 : ' + q.slice(1).join(' : ')]);
      check('6 ...a real round drum (ideal membrane, from the Bessel zeros)', !m2.length, `modes 01, 11, 21, 02 at ${q.join(' : ')}${m2.length ? '; text lacks ' + m2 : ''}`); } }
  { const L = lesson('Strike or pluck'), A = lessonTake(rate, L, 'A'), Bt = lessonTake(rate, L, 'B'), fs = modes(A).slice(0, 5);
    const ca = centroid(A, 0, 0.6), cb = centroid(Bt, 0, 0.6), pa = partials(A, fs, 0, 0.5), pb = partials(Bt, fs, 0, 0.5);
    const dd = [1, 2, 3, 4].map(i => (pa[i] - pa[0]) - (pb[i] - pb[0])), miss = has(L, ['1030 Hz', '380 Hz', '5 to 16 dB']);
    check('7 Strike or pluck' + tag, rel(ca, 1030, 0.06) && rel(cb, 380, 0.05) && near(Math.min(...dd), 5, 1.5) && near(Math.max(...dd), 16, 2) && !miss.length,
      `brightness centre ${ca.toFixed(0)} vs ${cb.toFixed(0)} Hz; plucked partials 2–5 lower by ${dd.map(d => d.toFixed(0)).join('/')} dB${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('A room'), A = lessonTake(rate, L, 'A', 3), Bt = lessonTake(rate, L, 'B', 3);
    const la = levelAt(A, 1.0, 1.1), lb = levelAt(Bt, 1.0, 1.1), pk = 20 * Math.log10(peakOf(Bt.L) / peakOf(A.L)), miss = has(L, ['47 dB', '26 dB']);
    check('8 A room' + tag, near(la, -47, 3) && near(lb, -26, 3) && Math.abs(pk) < 1 && !miss.length,
      `1 s after the strike: dry ${la.toFixed(1)} dB, plate ${lb.toFixed(1)} dB re the peak; peaks differ ${pk.toFixed(2)} dB${miss.length ? '; text lacks ' + miss : ''}`); }
  { const L = lesson('Make it move'), A = lessonTake(rate, L, 'A', 2.6), Bt = lessonTake(rate, L, 'B', 2.6);
    const W = [[0, 0.08], [0.15, 0.3], [0.35, 0.5], [0.7, 0.9], [1.2, 1.45]], ca = W.map(w => centroid(A, ...w)), cb = W.map(w => centroid(Bt, ...w));
    const falls = ca.every((c, i) => i === 0 || c <= ca[i - 1] + 3), top = cb.indexOf(Math.max(...cb)), miss = has(L, ['440 Hz', '355 Hz', '940 Hz', 'a quarter of a second']);
    check('9 Make it move' + tag, falls && rel(ca[0], 440, 0.05) && rel(ca[4], 355, 0.04) && top === 1 && rel(cb[1], 940, 0.04) && cb[4] < cb[1] * 0.7 && !miss.length,
      `still ${ca.map(c => c.toFixed(0)).join(' → ')} Hz; envelope ${cb.map(c => c.toFixed(0)).join(' → ')} Hz (windows ${W.map(w => w.join('–')).join(', ')} s)${miss.length ? '; text lacks ' + miss : ''}`); }
}

// ---------- the factory presets ----------
const RATE = 32000, VEL = [0.55, 1.0];
const factory = n => { const f = FACTORY.find(x => x.name === n); if (!f) throw new Error('no preset ' + n); return f; };
check('the page has 10 factory presets', FACTORY.length === 10, FACTORY.map(f => f.name).join(' | '));
for (const f of FACTORY) {
  const o = presetFrom(f);
  // a short phrase across the keyboard at the soft and hard ends of the pads' strength
  const keys = [0, 7, 12, 19, 24], take = (v) => session(RATE, presetFrom(f)).render(f.mode === 3 ? 6 : 5, keys.map((s, i) => ({ at: 0.1 + i * 0.8, semi: s, v, off: 0.1 + i * 0.8 + (f.mode === 3 ? 0.6 : 0.15) })));
  const t = VEL.map(take), bad = t.reduce((n, r) => n + [...r.L, ...r.R].filter(x => !Number.isFinite(x)).length, 0);
  const tp = Math.max(...t.map(r => Math.max(truePeakDb(r.L), truePeakDb(r.R)))), lu = t.map(r => lufs(r.L, r.R, RATE));
  // each key alone: none of them should be close to silent
  const each = keys.map(s => { const r = session(RATE, presetFrom(f)).render(1.6, [{ at: 0.05, semi: s, v: 0.55, off: 0.05 + (f.mode === 3 ? 0.8 : 0.15) }]); return lufs(r.L, r.R, RATE); });
  const spread = Math.max(...each) - Math.min(...each);
  check(`preset ${f.name}: plays cleanly, near the default instrument's loudness`, !bad && tp <= -0.9 && lu[0] >= -26 && lu[0] <= -14 && lu[1] <= -12 && Math.min(...each) >= -32 && spread <= 10,
    `true peak ${tp.toFixed(2)} dBTP; phrase ${lu.map(x => x.toFixed(1)).join(' / ')} LUFS (strength 0.55 / 1); single keys E3–E5 ${each.map(x => x.toFixed(0)).join(' ')} LUFS (spread ${spread.toFixed(1)} dB)${bad ? '; ' + bad + ' non-finite samples' : ''}`);
}
// what each description says
{ const r = session(RATE, presetFrom(factory('Glass bar (bowed)'))).render(4);
  check('Glass bar (bowed): the bow keeps it sounding with no key', levelAt({ ...r, t0: 0 }, 3, 4) > -12 && peakOf(r.L) > 0.01, `last second ${levelAt({ ...r, t0: 0 }, 3, 4).toFixed(1)} dB re the peak; peak ${peakOf(r.L).toFixed(3)}`); }
{ const r = session(RATE, presetFrom(factory('Wind harp'))).render(4);
  check('Wind harp: sounds with no key', lufs(r.L, r.R, RATE) > -36 && levelAt({ ...r, t0: 0 }, 3, 4) > -12, `${lufs(r.L, r.R, RATE).toFixed(1)} LUFS; last second ${levelAt({ ...r, t0: 0 }, 3, 4).toFixed(1)} dB re the peak`); }
{ const r = session(RATE, presetFrom(factory('Steel tank'))).render(10, [{ at: 0.05, semi: 0, v: 0.8, off: 0.2 }]);
  check('Steel tank: a long ring', tdrop(r, 40) > 4, `40 dB down after ${tdrop(r, 40).toFixed(1)} s`); }
{ const f = factory('Gong'), res = VEL.map(v => { const r = session(RATE, presetFrom(f)).render(2.5, [{ at: 0.05, semi: 0, v, off: 0.2 }]);
    const a = domFreq(r, 0.02, 0.3), b = domFreq(r, 1.2, 2.2); return { v, a, b, c: 1200 * Math.log2(a / b) }; });
  check('Gong: hit hard, the pitch starts high and sinks', res[1].c > 15 && res[1].c > res[0].c, res.map(x => `strength ${x.v}: ${x.a.toFixed(1)} Hz → ${x.b.toFixed(1)} Hz (${x.c.toFixed(0)} cents)`).join('; ')); }
{ const f = factory('Breathing pad'), r = session(RATE, presetFrom(f)).render(4, [{ at: 0.05, semi: 12, v: 0.8, off: 2.05 }]);
  const c0 = centroid(r, 0.03, 0.15), c1 = centroid(r, 0.3, 0.5), c2 = centroid(r, 1.7, 2.0);
  check('Breathing pad: hold a key and the tone opens, then settles', c1 > 1.3 * c0 && c2 < 0.8 * c1,
    `brightness centre ${c0.toFixed(0)} Hz at the strike, ${c1.toFixed(0)} Hz at 0.3–0.5 s, ${c2.toFixed(0)} Hz held at 1.7–2 s`); }
{ const f = factory('Turning bell'), r = session(RATE, presetFrom(f)).render(4.2, [{ at: 0.05, semi: 12, v: 0.8, off: 0.2 }]);
  const W = Math.round(0.1 * RATE), bal = []; for (let s0 = Math.round(0.1 * RATE); s0 + W < Math.round(4 * RATE); s0 += W) { let l = 0, q = 0; for (let i = s0; i < s0 + W; i++) { l += r.L[i] ** 2; q += r.R[i] ** 2; } bal.push(10 * Math.log10(l / q)); }
  const lo = Math.min(...bal), hi = Math.max(...bal);
  check('Turning bell: it drifts between your ears', hi - lo >= 5, `left/right balance moves over ${(hi - lo).toFixed(1)} dB (${lo.toFixed(1)} … ${hi.toFixed(1)}) in 4 s`); }
{ const o = presetFrom(factory('Sympathetic twins')), n = o.n, m2 = Math.max(4, Math.round(n * 0.68)), first = i => i <= n + 1;
  const r = session(RATE, o).render(2.5, [{ at: 0.05, semi: 0, v: 0.8, off: 0.2 }]);
  check('Sympathetic twins: you pluck one string, the mic hears the other', first(o.hitIdx) && !first(o.micIdx) && lufs(r.L, r.R, RATE) > -30 && m2 > 0,
    `strike on mass ${o.hitIdx} (first string), mic on mass ${o.micIdx} (second string); ${lufs(r.L, r.R, RATE).toFixed(1)} LUFS`); }
{ const f = factory('Kalimba'); check('Kalimba: struck firmly (the Mallet knob reads firm)', H.KNOBS.hard.fmt(f.val.hard) === 'firm', H.KNOBS.hard.fmt(f.val.hard)); }
{ const f = factory('Harp'); check('Harp: a string plucked with a plectrum, in a plate', f.mode === 2 && f.shape === 'String' && f.val.rvMix > 0, `mode ${f.mode}, ${f.shape}, reverb ${f.val.rvMix}`); }
{ const f = factory('Pickup twang'); check('Pickup twang: humbucker, amp, speaker box', f.pk === 1 && f.val.amp > 0 && f.val.cab > 0, `pickup ${f.pk}, amp ${f.val.amp}, cabinet ${f.val.cab}`); }
console.log(failed ? `\n${failed} check(s) FAILED` : '\nall Stage H claims verified');
process.exit(failed ? 1 : 0);
}
