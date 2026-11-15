// Symmetric eigen-decomposition: Householder tridiagonalisation (tred2) + implicit QL (tql2).
// Port of the public-domain JAMA / EISPACK routines. Same contract as the engine's jacobi():
// input A (n*n row-major, symmetric), returns {lam, V} with V[k*n+m] = component k of mode m.
// Written without backticks or template expressions so it can live inside String.raw.
function eigTQL(A, n, valuesOnly) {
  const V = Float64Array.from(A), d = new Float64Array(n), e = new Float64Array(n);
  for (let j = 0; j < n; j++) d[j] = V[(n - 1) * n + j];
  // tred2
  for (let i = n - 1; i > 0; i--) {
    let scale = 0, h = 0;
    for (let k = 0; k < i; k++) scale += Math.abs(d[k]);
    if (scale === 0) {
      e[i] = d[i - 1];
      for (let j = 0; j < i; j++) { d[j] = V[(i - 1) * n + j]; V[i * n + j] = 0; V[j * n + i] = 0; }
    } else {
      for (let k = 0; k < i; k++) { d[k] /= scale; h += d[k] * d[k]; }
      let f = d[i - 1], g = Math.sqrt(h);
      if (f > 0) g = -g;
      e[i] = scale * g; h = h - f * g; d[i - 1] = f - g;
      for (let j = 0; j < i; j++) e[j] = 0;
      for (let j = 0; j < i; j++) {
        f = d[j]; V[j * n + i] = f; g = e[j] + V[j * n + j] * f;
        for (let k = j + 1; k <= i - 1; k++) { g += V[k * n + j] * d[k]; e[k] += V[k * n + j] * f; }
        e[j] = g;
      }
      f = 0;
      for (let j = 0; j < i; j++) { e[j] /= h; f += e[j] * d[j]; }
      const hh = f / (h + h);
      for (let j = 0; j < i; j++) e[j] -= hh * d[j];
      for (let j = 0; j < i; j++) {
        f = d[j]; g = e[j];
        for (let k = j; k <= i - 1; k++) V[k * n + j] -= (f * e[k] + g * d[k]);
        d[j] = V[(i - 1) * n + j]; V[i * n + j] = 0;
      }
    }
    d[i] = h;
  }
  for (let i = 0; i < n - 1 && !valuesOnly; i++) {
    V[(n - 1) * n + i] = V[i * n + i]; V[i * n + i] = 1;
    const h = d[i + 1];
    if (h !== 0) {
      for (let k = 0; k <= i; k++) d[k] = V[k * n + i + 1] / h;
      for (let j = 0; j <= i; j++) {
        let g = 0;
        for (let k = 0; k <= i; k++) g += V[k * n + i + 1] * V[k * n + j];
        for (let k = 0; k <= i; k++) V[k * n + j] -= g * d[k];
      }
    }
    for (let k = 0; k <= i; k++) V[k * n + i + 1] = 0;
  }
  if (valuesOnly) { for (let j = 0; j < n; j++) { const t = d[j]; d[j] = V[j * n + j]; V[j * n + j] = t; } }
  else { for (let j = 0; j < n; j++) { d[j] = V[(n - 1) * n + j]; V[(n - 1) * n + j] = 0; }
  V[(n - 1) * n + n - 1] = 1; }
  e[0] = 0;
  // tql2
  for (let i = 1; i < n; i++) e[i - 1] = e[i];
  e[n - 1] = 0;
  let f = 0, tst1 = 0; const eps = Math.pow(2, -52);
  for (let l = 0; l < n; l++) {
    tst1 = Math.max(tst1, Math.abs(d[l]) + Math.abs(e[l]));
    let m = l; while (m < n) { if (Math.abs(e[m]) <= eps * tst1) break; m++; }
    if (m > l) {
      let iter = 0;
      do {
        iter++;
        let g = d[l], p = (d[l + 1] - g) / (2 * e[l]), r = Math.hypot(p, 1);
        if (p < 0) r = -r;
        d[l] = e[l] / (p + r); d[l + 1] = e[l] * (p + r);
        const dl1 = d[l + 1]; let h = g - d[l];
        for (let i = l + 2; i < n; i++) d[i] -= h;
        f += h;
        p = d[m]; let c = 1, c2 = c, c3 = c; const el1 = e[l + 1]; let s = 0, s2 = 0;
        for (let i = m - 1; i >= l; i--) {
          c3 = c2; c2 = c; s2 = s; g = c * e[i]; h = c * p; r = Math.hypot(p, e[i]);
          e[i + 1] = s * r; s = e[i] / r; c = p / r; p = c * d[i] - s * g; d[i + 1] = h + s * (c * g + s * d[i]);
          if (!valuesOnly) for (let k = 0; k < n; k++) { h = V[k * n + i + 1]; V[k * n + i + 1] = s * V[k * n + i] + c * h; V[k * n + i] = c * V[k * n + i] - s * h; }
        }
        p = -s * s2 * c3 * el1 * e[l] / dl1; e[l] = s * p; d[l] = c * p;
      } while (Math.abs(e[l]) > eps * tst1 && iter < 60);
    }
    d[l] = d[l] + f; e[l] = 0;
  }
  return { lam: d, V };
}
if (typeof module !== 'undefined') module.exports = { eigTQL };
