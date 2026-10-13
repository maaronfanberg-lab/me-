// Does the engine's spring law make a curved shell behave like a membrane shell?
// Free icosphere (no anchors), engine's assembleK + tql, modes classified by spherical-harmonic degree,
// compared with the membrane equation checked in tower_acoustics.py.
//   node qa-resonator/sphere_check.mjs [subdiv] [ratio...]
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const H = await import('./harness.mjs?src=' + path.join(root, 'apps/resonator-next.html'));
const sub = +(process.argv[2] || 2), ratios = process.argv.slice(3).map(Number); if (!ratios.length) ratios.push(2, 4, 6, 10, 14);

function icosphere(k) {
  const t = (1 + Math.sqrt(5)) / 2; let V = [[-1,t,0],[1,t,0],[-1,-t,0],[1,-t,0],[0,-1,t],[0,1,t],[0,-1,-t],[0,1,-t],[t,0,-1],[t,0,1],[-t,0,-1],[-t,0,1]].map(v => { const l = Math.hypot(...v); return v.map(x => x / l); });
  let Fc = [[0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],[1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],[3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],[4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]];
  for (let s = 0; s < k; s++) { const cache = new Map(), nf = [];
    const mid = (a, b) => { const key = a < b ? a + ',' + b : b + ',' + a; if (cache.has(key)) return cache.get(key);
      const m = V[a].map((x, i) => (x + V[b][i]) / 2), l = Math.hypot(...m); V.push(m.map(x => x / l)); cache.set(key, V.length - 1); return V.length - 1; };
    for (const [a, b, c] of Fc) { const ab = mid(a, b), bc = mid(b, c), ca = mid(c, a); nf.push([a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]); }
    Fc = nf; }
  const E = new Set(); for (const [a, b, c] of Fc) for (const [i, j] of [[a, b], [b, c], [c, a]]) E.add(i < j ? i + ',' + j : j + ',' + i);
  return { P: V.map(v => v.map(x => x * 0.3)), S: [...E].map(e => e.split(',').map(Number)) };
}
function legendre(n, m, x) { let pmm = 1; const sx = Math.sqrt(Math.max(0, 1 - x * x)); for (let i = 1; i <= m; i++) pmm *= (2 * i - 1) * sx;
  if (n === m) return pmm; let p1 = x * (2 * m + 1) * pmm; if (n === m + 1) return p1; let pn = 0;
  for (let l = m + 2; l <= n; l++) { pn = (x * (2 * l - 1) * p1 - (l + m - 1) * pmm) / (l - m); pmm = p1; p1 = pn; } return pn; }
const Y = (n, m, th, ph) => { const a = Math.abs(m), p = legendre(n, a, Math.cos(th)); return m > 0 ? p * Math.cos(a * ph) : m < 0 ? p * Math.sin(a * ph) : p; };

const g = icosphere(sub);
const N = g.P.length;
const memb = (n, nu) => { const lam = n * (n + 1), b = 1 + 3 * nu + lam, c = (lam - 2) * (1 - nu * nu), d = Math.sqrt(b * b - 4 * c); return [Math.sqrt(Math.max(0, (b - d) / 2)), Math.sqrt((b + d) / 2)]; };
console.log(`icosphere subdiv ${sub}: ${N} masses, ${g.S.length} springs`);
console.log('membrane (nu 0.3), ratio to lower n=2:', [2, 3, 4, 6, 10].map(n => `n${n} ${(memb(n, 0.3)[0] / memb(2, 0.3)[0]).toFixed(3)}`).join(' '), ` breathing ${(memb(0, 0.3)[1] / memb(2, 0.3)[0]).toFixed(3)} upper n1 ${(memb(1, 0.3)[1] / memb(2, 0.3)[0]).toFixed(3)}`);
for (const ratio of ratios) {
  const p = H.makeProc(48000);
  const pos = new Float32Array(N * 3); g.P.forEach((q, i) => { pos.set(q, i * 3); });
  p.port.onmessage({ data: { t: 'struct', n: N, pos, fixed: new Uint8Array(N), si: Int32Array.from(g.S.map(s => s[0])), sj: Int32Array.from(g.S.map(s => s[1])), mic: 0, hit: 1, axis: 1 } });
  p.anchored = false; p.dofMap();
  const n = 3 * N, K = p.assembleK(1, ratio * ratio, 0), { lam, V } = p.tql(K, n, false);
  const rows = [];
  for (let m = 0; m < n; m++) { if (!(lam[m] > 1e-8)) continue;
    // radial / tangential split and degree of the radial field (exact quadrature not needed: nodes are near-uniform)
    const pw = new Array(9).fill(0); let rE = 0, tE = 0;
    for (let i = 0; i < N; i++) { const [x, y, z] = g.P[i].map(c => c / 0.3), ux = V[3 * i * n + m], uy = V[(3 * i + 1) * n + m], uz = V[(3 * i + 2) * n + m];
      const ur = ux * x + uy * y + uz * z; rE += ur * ur; tE += ux * ux + uy * uy + uz * uz - ur * ur;
      const th = Math.acos(Math.max(-1, Math.min(1, z))), ph = Math.atan2(y, x);
      for (let d = 0; d <= 8; d++) for (let mm = -d; mm <= d; mm++) { /* projection, normalised below */ } }
    // degree by projection with normalised harmonics
    const deg = new Array(9).fill(0);
    for (let d = 0; d <= 8; d++) for (let mm = -d; mm <= d; mm++) { let s = 0, q = 0;
      for (let i = 0; i < N; i++) { const [x, y, z] = g.P[i].map(c => c / 0.3), ur = V[3 * i * n + m] * x + V[(3 * i + 1) * n + m] * y + V[(3 * i + 2) * n + m] * z;
        const yy = Y(d, mm, Math.acos(Math.max(-1, Math.min(1, z))), Math.atan2(y, x)); s += ur * yy; q += yy * yy; }
      deg[d] += q > 0 ? s * s / q : 0; }
    const tot = deg.reduce((a, b) => a + b, 0) || 1;
    const dom = deg.indexOf(Math.max(...deg));
    rows.push({ f: Math.sqrt(lam[m]) / (2 * Math.PI), rad: rE / (rE + tE), dom, share: deg[dom] / tot });
  }
  rows.sort((a, b) => a.f - b.f);
  // group: lower-branch n (radial-dominant? on a membrane sphere lower branch is mixed), report first mode with dom=2 etc
  const first = d => rows.find(r => r.dom === d && r.share > 0.6);
  const n2 = first(2);
  const br = rows.filter(r => r.dom === 0 && r.share > 0.6).sort((a, b) => b.rad - a.rad)[0];
  const out = [`ratio ${ratio}:`];
  for (const d of [2, 3, 4, 5, 6]) { const r = first(d); if (r) out.push(`n${d} ${(r.f / n2.f).toFixed(3)}(${(r.rad * 100).toFixed(0)}%r)`); }
  if (br) out.push(`breathing ${(br.f / n2.f).toFixed(3)}`);
  out.push(`modes ≤1.4×n2: ${rows.filter(r => r.f <= 1.4 * n2.f).length}`);
  console.log(out.join('  '));
}
