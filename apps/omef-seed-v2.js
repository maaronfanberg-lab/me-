(function () {
'use strict';
var PHI = (1 + Math.sqrt(5)) / 2;
var EPS = 1e-9;
function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }
function sigmoid(x) { x = clamp(x, -40, 40); return 1 / (1 + Math.exp(-x)); }
function tanh(x) { var e2 = Math.exp(2 * clamp(x, -20, 20)); return (e2 - 1) / (e2 + 1); }
function mean(a) { var s = 0, i; for (i = 0; i < a.length; i++) s += a[i]; return s / a.length; }
function norm2(a) { var s = 0, i; for (i = 0; i < a.length; i++) s += a[i] * a[i]; return Math.sqrt(s); }
function softmax(a) {
var m = -Infinity, i, s = 0, out = [];
for (i = 0; i < a.length; i++) if (a[i] > m) m = a[i];
for (i = 0; i < a.length; i++) { out[i] = Math.exp(clamp(a[i] - m, -40, 40)); s += out[i]; }
for (i = 0; i < out.length; i++) out[i] /= s || 1;
return out;
}
function fib(n) { var a = 0, b = 1, t, i; for (i = 0; i < n; i++) { t = a + b; a = b; b = t; } return a || 1; }
function detNoise(seed, k) { return 0.05 * Math.sin(seed * (k + 1) * 1.731 + k * 0.913); }
function finite(x) { return isFinite(x) ? x : 0; }
function runOMEF(seed) {
var x = finite(seed), i, j, k;
var audit = [];
var U = [], M = [], F = [], cycles = [], weights = [], history = [];
var market = 0, deltaM = 0, divergence = 0, spectral = 0, lambda2 = 0;
var rankEff = 10, humility = 0, confidence = 1, damping = 0, rho = 0;
var correction = 0, strain = 0, particleDeg = 0, calErr = 0, tailRisk = 0;
var blockScore = 0, releaseRisk = 0, score = 0;
function logPage(n, name, value) {
value = finite(value);
audit.push('P' + n + '  ' + name + '  ' + value.toPrecision(10));
return value;
}
for (i = 0; i < 10; i++) U[i] = x + 0.07 * Math.sin((i + 1) * x) + detNoise(x, i);
for (i = 0; i < 5; i++) M[i] = mean(U.slice(i, i + 6));
score += logPage(1, 'unified state / moments', mean(M));
for (i = 0; i < 4; i++) F[i] = 0.72 * M[i % M.length] + 0.18 * tanh(x + i / PHI);
var regimeP = softmax([F[0] + 0.1 * x, F[1] - 0.08 * x, F[2] + F[3] * 0.2]);
var regime = regimeP[0] > regimeP[1] ? (regimeP[0] > regimeP[2] ? 0 : 2) : (regimeP[1] > regimeP[2] ? 1 : 2);
score += logPage(2, 'factor memory / regime', mean(F) + regimeP[regime]);
market = tanh(0.35 * mean(U) + 0.25 * norm2(F) - 0.12 * regime);
var pressure = 0;
for (i = 0; i < 10; i++) {
weights[i] = [];
var logits = [];
for (j = 0; j < 10; j++) logits[j] = (i === j ? -6 : 0.4 * market - 0.15 * Math.abs(U[i] - U[j]) + 0.05 * Math.cos(i + j + x));
weights[i] = softmax(logits);
var mix = 0;
for (j = 0; j < 10; j++) mix += weights[i][j] * U[j];
pressure += mix - U[i];
}
deltaM = pressure / 10;
score += logPage(3, 'market connectivity', market + deltaM);
for (i = 0; i < 9; i++) {
var ts = 5 + i + 0.2 * sigmoid(x);
var tl = ts * PHI * (1 + 0.015 * Math.sin(x + i));
var ps = 2 * Math.PI / ts, pl = 2 * Math.PI / tl;
cycles[i] = Math.cos(ps * (x + i)) + Math.cos(pl * (x + i));
}
var golden = mean(cycles);
score += logPage(4, 'golden-cycle field', golden);
var Ustar = [];
for (i = 0; i < 10; i++) Ustar[i] = U[i] + 0.11 * golden + 0.06 * deltaM + detNoise(x, 30 + i);
var d2 = 0;
for (i = 0; i < 10; i++) d2 += (Ustar[i] - U[i]) * (Ustar[i] - U[i]);
divergence = Math.log1p(Math.sqrt(d2));
score += logPage(5, 'smoothed divergence', divergence);
var jacRadius = 0.68 + 0.22 * Math.abs(tanh(mean(U))) + 0.18 * Math.abs(deltaM) + 0.07 * Math.abs(golden);
spectral = 1 - jacRadius;
score += logPage(6, 'spectral margin', spectral);
var simSum = 0, edges = 0;
for (i = 0; i < 10; i++) for (j = i + 1; j < 10; j++) { simSum += Math.exp(-Math.abs(U[i] - U[j])); edges++; }
lambda2 = clamp((simSum / edges) * (1 - 0.25 * Math.abs(market)), 0, 1);
score += logPage(7, 'graph connectivity lambda2', lambda2);
for (k = 0; k < 21; k++) history[k] = Math.sin(x * (k + 1) / PHI) + 0.4 * Math.cos((k + 1) * market);
var spread = 0, hm = mean(history);
for (k = 0; k < history.length; k++) spread += Math.abs(history[k] - hm);
spread /= history.length;
rankEff = clamp(Math.round(1 + 9 * sigmoid(2.5 * spread - 0.8)), 1, 10);
score += logPage(8, 'effective trajectory rank', rankEff / 10);
var benchmarkGap = tanh(mean(F) - 0.25 * Math.abs(deltaM) - 0.1 * divergence);
particleDeg = clamp(sigmoid(1.8 * divergence + 1.2 * Math.max(0, -spectral) - 1.1), 0, 1);
humility = clamp(0.18 * Math.abs(deltaM) + 0.16 * Math.max(0, -spectral) + 0.14 * (1 - lambda2) + 0.14 * (1 - rankEff / 10) + 0.18 * particleDeg + 0.20 * Math.max(0, -benchmarkGap), 0, 2);
confidence = Math.exp(-humility);
score += logPage(9, 'humility / confidence', humility + confidence);
var reg = 0.08 * (1 + humility + particleDeg + Math.max(0, -benchmarkGap));
damping = 0.10 + 0.25 * divergence + 0.18 * Math.abs(deltaM) + 0.22 * Math.max(0, -spectral) + 0.12 * (1 - rankEff / 10) + reg;
score += logPage(10, 'regularization / damping', reg + damping);
rho = sigmoid(1.2 * divergence + 0.8 * confidence + 0.5 * spectral - 0.7 * humility);
score += logPage(11, 'correction retention rho', rho);
var A = [];
for (i = 0; i < 10; i++) {
var v = U[i];
for (j = 0; j < 10; j++) if (j !== i) v += 0.018 * tanh(U[j]) * Math.sin((i + 1) * (j + 1) + market);
for (j = 0; j < 3; j++) v += 0.009 * tanh(U[(i + j + 1) % 10]) * tanh(U[(i + j + 4) % 10]);
A[i] = v;
}
score += logPage(12, 'nonlinear interaction field', mean(A));
var R = [];
for (i = 0; i < 5; i++) {
var a = x / (i + 2) + 0.25 * golden;
var c = Math.cos(a), s = Math.sin(a), u0 = A[2 * i], u1 = A[2 * i + 1];
R[2 * i] = c * u0 - s * u1;
R[2 * i + 1] = s * u0 + c * u1;
}
var denom = 1 + damping * norm2(U) * norm2(U) / 10;
for (i = 0; i < 10; i++) R[i] /= denom;
score += logPage(13, 'rotation propagation', mean(R));
var residual = mean(Ustar) - mean(R);
correction = rho * residual * confidence + 0.08 * (1 - lambda2) - 0.05 * particleDeg;
var accountSum = 0;
for (i = 0; i < 10; i++) accountSum += R[i] + correction / 10;
var accountPenalty = Math.abs(accountSum) / 10;
score += logPage(14, 'observer / accounting', correction - accountPenalty);
var fw = 0, fsum = 0;
for (k = 1; k <= 13; k++) { var w = 1 / fib(k); fw += w * history[history.length - k]; fsum += w; }
strain = 0.76 * tanh(x / PHI) + 0.24 * fw / (fsum || 1);
score += logPage(15, 'Fibonacci structural strain', strain);
var obsResidual = residual + 0.12 * strain + detNoise(x, 80);
var nu = 5 + 12 * confidence;
var studentScore = -0.5 * (nu + 1) * Math.log1p((obsResidual * obsResidual) / nu);
score += logPage(16, 'Student-t observation score', studentScore);
var objective = studentScore - reg * (norm2(F) + Math.abs(strain)) - 0.25 * accountPenalty - 0.2 * Math.max(0, -spectral);
var adaptRate = 0.06 * confidence / (1 + particleDeg + humility);
score += logPage(17, 'posterior objective / adaptation', objective + adaptRate);
var pw = [], pstate = [];
for (i = 0; i < 16; i++) {
pstate[i] = mean(R) + correction + 0.08 * Math.sin(x * (i + 1));
pw[i] = Math.exp(-Math.abs(pstate[i] - mean(Ustar)) * (1 + humility));
}
var psum = 0; for (i = 0; i < pw.length; i++) psum += pw[i];
var sq = 0; for (i = 0; i < pw.length; i++) { pw[i] /= psum || 1; sq += pw[i] * pw[i]; }
var neff = 1 / (sq || 1);
particleDeg = 1 - neff / pw.length;
score += logPage(18, 'particle posterior diversity', 1 - particleDeg);
var b1 = mean(U.slice(0, 5)), b2 = mean(U.slice(5, 10));
blockScore = 0.5 * (b1 + b2) + 0.2 * (b1 - b2) * market + 0.1 * (1 - particleDeg);
score += logPage(19, 'block-hybrid inference', blockScore);
var revisionVar = 0.04 + 0.18 * sigmoid(Math.abs(x) + divergence - 1);
var releaseSurprise = detNoise(x, 120) + 0.15 * residual;
releaseRisk = releaseSurprise * releaseSurprise / (revisionVar + EPS);
score += logPage(20, 'release / revision risk', releaseRisk);
var spectralRT = spectral - 0.08 * releaseRisk + 0.04 * blockScore;
var benchmarkRT = benchmarkGap - 0.06 * releaseRisk;
var humilityRT = humility + 0.12 * releaseRisk + 0.08 * Math.max(0, -benchmarkRT);
score += logPage(21, 'real-time stability / humility', spectralRT - humilityRT);
var reconcile = mean([mean(U), mean(M), mean(F), golden, strain, market, deltaM, correction]);
score += logPage(22, 'state reconciliation', reconcile);
var diag23 = lambda2 + rankEff / 10 + confidence + benchmarkGap - particleDeg + spectral;
score += logPage(23, 'diagnostic reconciliation', diag23 / 6);
var penalty24 = reg * (1 + humilityRT + particleDeg);
var eta24 = adaptRate / (1 + Math.abs(calErr));
score += logPage(24, 'adaptive penalty / learning rate', eta24 - penalty24);
var qY = obsResidual * obsResidual / (0.2 + revisionVar + EPS);
var coverage = Math.exp(-0.5 * qY);
calErr = 0.90 - coverage;
tailRisk = Math.max(0, qY - 2.71) / (1 + qY);
score += logPage(25, 'calibration / tail risk', coverage - calErr - tailRisk);
var finalInfo = mean([
mean(R), correction, strain, spectralRT, lambda2, rankEff / 10,
confidence, 1 - particleDeg, blockScore, -releaseRisk, -calErr, -tailRisk
]);
score += logPage(26, 'final real-time information state', finalInfo);
var raw = score / 26 + 0.18 * finalInfo + 0.07 * mean(Ustar);
var output = raw + 0.11 * tanh(raw) + 0.03 * Math.sin(PHI * raw);
return { output: finite(output), audit: audit };
}
function formatNumber(x) {
if (!isFinite(x)) return 'UNDEFINED';
return String(Number(x.toPrecision(15)));
}
function boot() {
var seedEl = document.getElementById('seed');
var ansEl = document.getElementById('answer');
var statusEl = document.getElementById('status');
var auditEl = document.getElementById('audit');
var btn = document.getElementById('compute');
function compute() {
var text = String(seedEl.value).replace(',', '.');
var x = Number(text);
if (!isFinite(x)) {
ansEl.innerHTML = 'UNDEFINED';
statusEl.innerHTML = 'Enter a valid number.';
auditEl.innerHTML = '';
return;
}
try {
var r = runOMEF(x);
ansEl.innerHTML = formatNumber(r.output);
statusEl.innerHTML = 'Computed · 26/26 page modules participated';
auditEl.textContent = r.audit.join('\n');
} catch (e) {
ansEl.innerHTML = 'UNDEFINED';
statusEl.innerHTML = 'Engine error: ' + (e && e.message ? e.message : e);
}
}
btn.onclick = compute;
seedEl.onkeypress = function (e) { e = e || window.event; if ((e.keyCode || e.which) === 13) compute(); };
compute();
}
if (document.readyState === 'loading') {
if (document.addEventListener) document.addEventListener('DOMContentLoaded', boot, false);
else window.attachEvent('onload', boot);
} else boot();
}());