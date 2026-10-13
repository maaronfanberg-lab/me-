// Modal analysis of a tower body with the engine's own stiffness assembly and eigen-solver (used by t1_verify.mjs).
// analyse(g, ratio) classifies every mode: share of motion on the bowl, share along the bowl's normal, volume
// change (breathing), circumferential order m (per-ring Fourier transform of the normal motion), spherical-harmonic
// degree, and amplitude at the strike and mic. The body comes from the page (SHAPES.Tower.make).
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const H = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
export function summary(modes){
  const ok = m => m.bowlShare > 0.6 && m.radShare > 0.6;
  const n2 = modes.find(m => ok(m) && m.dom === 2);
  const br = modes.filter(m => ok(m)).sort((a, b) => b.deg[0] - a.deg[0])[0];
  const cl = modes.filter(m => ok(m) && m.dom >= 3 && n2 && m.f > n2.f && m.f < (br ? br.f : 1e9));
  return { n2, br, cl };
}

// real spherical-harmonic-like basis on the bowl, using polar angle from the spheroid centre
function Ybasis(nmax) {
  const out = [];
  for (let n = 0; n <= nmax; n++) for (let m = -n; m <= n; m++) out.push({ n, m });
  return out;
}
function legendre(n, m, x) {   // associated Legendre P_n^m(x), m >= 0 (no Condon-Shortley phase)
  let pmm = 1; const sx = Math.sqrt(Math.max(0, 1 - x * x));
  for (let i = 1; i <= m; i++) pmm *= (2 * i - 1) * sx;
  if (n === m) return pmm;
  let pmm1 = x * (2 * m + 1) * pmm; if (n === m + 1) return pmm1;
  let pnn = 0; for (let l = m + 2; l <= n; l++) { pnn = (x * (2 * l - 1) * pmm1 - (l + m - 1) * pmm) / (l - m); pmm = pmm1; pmm1 = pnn; }
  return pnn;
}
function Y(n, m, th, ph) { const am = Math.abs(m); const p = legendre(n, am, Math.cos(th)); return m > 0 ? p * Math.cos(am * ph) : m < 0 ? p * Math.sin(am * ph) : p; }

export function analyse(g, ratio, opts = {}) {
  const p = H.makeProc(48000);
  const pos = new Float32Array(g.P.length * 3); g.P.forEach((q, i) => { pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2]; });
  const hit = opts.hit ?? g.hit, mic = opts.mic ?? g.mic, axis = opts.axis ?? g.axis;
  p.port.onmessage({ data: { t: 'struct', n: g.P.length, pos, fixed: Uint8Array.from(g.F), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic, hit, axis } });
  p.anchored = true; p.dofMap();
  const kT = 1, kL = ratio * ratio, n = 3 * p.F;
  const K = p.assembleK(kT, kL, 0);
  const { lam, V } = p.tql(K, n, false);
  const idx = [...lam.keys()].sort((x, y) => lam[x] - lam[y]);
  const hi = p.map[hit], mi = p.map[mic];
  const modes = [];
  for (const m of idx) {
    if (!(lam[m] > 1e-12)) continue;
    const f = Math.sqrt(lam[m]) / (2 * Math.PI);
    let eB = 0, eT = 0, rE = 0, vol = 0, nb = 0; const deg = new Array(7).fill(0), pts = [];
    for (let i = 0; i < g.P.length; i++) { if (g.F[i]) continue; const d = p.map[i];
      const ux = V[(3 * d) * n + m], uy = V[(3 * d + 1) * n + m], uz = V[(3 * d + 2) * n + m], e = ux * ux + uy * uy + uz * uz; eT += e;
      if (g.tag[i] === 'bowl') { eB += e;
        const x = g.P[i][0] / g.a, y = (g.P[i][1] - g.yc) / g.b, z = g.P[i][2] / g.a, r = Math.hypot(x, y, z);
        const nx = x / g.a, ny = y / g.b, nz = z / g.a, nl = Math.hypot(nx, ny, nz);
        const ur = (ux * nx + uy * ny + uz * nz) / nl; rE += ur * ur; vol += ur; nb++;
        pts.push([ur, Math.acos(Math.max(-1, Math.min(1, y / r))), Math.atan2(z, x)]); } }
    const az = new Array(13).fill(0);
    if (g.bowlRings) { for (const R of g.bowlRings) { if (R.length < 3 || g.F[R[0]]) continue; const mx = Math.min(12, (R.length - 1) >> 1);
        for (let mm = 0; mm <= mx; mm++) { let cr = 0, ci = 0; for (const q of R) { const d = p.map[q], ph = Math.atan2(g.P[q][2], g.P[q][0]);
            const x = g.P[q][0] / g.a, y = (g.P[q][1] - g.yc) / g.b, z = g.P[q][2] / g.a, nx = x / g.a, ny = y / g.b, nz = z / g.a, nl = Math.hypot(nx, ny, nz);
            const ur = (V[(3 * d) * n + m] * nx + V[(3 * d + 1) * n + m] * ny + V[(3 * d + 2) * n + m] * nz) / nl;
            cr += ur * Math.cos(mm * ph); ci += ur * Math.sin(mm * ph); } az[mm] += (cr * cr + ci * ci) * (mm ? 2 : 1) / R.length; } } }
    else for (let mm = 0; mm <= 12; mm++) { let cr = 0, ci = 0; for (const [ur, , ph] of pts) { cr += ur * Math.cos(mm * ph); ci += ur * Math.sin(mm * ph); } az[mm] = (cr * cr + ci * ci) * (mm ? 2 : 1); }
    const azT = az.reduce((x, y) => x + y, 0) || 1, mAz = az.indexOf(Math.max(...az));
    for (let dd = 0; dd <= 6; dd++) for (let mm = -dd; mm <= dd; mm++) { let s = 0, q = 0;
      for (const [ur, th, ph] of pts) { const yy = Y(dd, mm, th, ph); s += ur * yy; q += yy * yy; } deg[dd] += q > 0 ? s * s / q : 0; }
    const tot = deg.reduce((a, b) => a + b, 0) || 1;
    let h = 0, c = 0; for (let a = 0; a < 3; a++) { h += V[(3 * hi + a) * n + m] * p.hitVec[a]; c += V[(3 * mi + a) * n + m] * p.micVec[a]; }
    modes.push({ f, mAz, azShare: az[mAz] / azT, vol: vol * vol / (nb * (eB || 1)), bowlShare: eB / eT, radShare: rE / (eB || 1), deg: deg.map(v => v / tot), dom: deg.indexOf(Math.max(...deg)), amp: Math.abs(h * c) / Math.sqrt(lam[m]) });
  }
  return { modes, N: g.P.length, S: g.S.length };
}
