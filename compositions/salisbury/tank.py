"""The Tank from RESONATOR No. 2, rebuilt exactly: same mesh, same linearised spring law, same damping.

Mesh (RESONATOR No. 2, SHAPES.Tank.make(C)): a pole, K=2 cap rings, A=4 barrel rings, K=2 cap rings, a pole.
R=0.24, H=0.26. Springs: round each ring; between neighbouring rings straight and diagonal; poles to end rings.
Spring law linearised about rest (resonator.html assembleK): block kT(I - u u^T) + kL u u^T, kL = ratio*kT,
substrate sub*kT on the diagonal. Damping: a dashpot c = lossK*sqrt(kT) on each spring's relative velocity
(isotropic), lossK = loss*0.02*(220/f0)^0.8, plus the global decay (velocity scaled by exp(-6.91/decay * dt)).
Tuning: kT is set so the lowest non-rigid mode sits at f0 (omega^2 = lambda, m = 1).
Because the law is linear about rest, the response is an exact sum of damped modes (state-space eigensolution).
Pins remove nodes' degrees of freedom; cut springs are removed from K and D.
"""
import numpy as np

R_, H_, A_, K_ = 0.24, 0.26, 4, 2


def mesh(C=7):
    P, rings = [], []

    def ring(x, r):
        ids = []
        for j in range(C):
            th = 2 * np.pi * j / C
            ids.append(len(P)); P.append([x, r * np.cos(th), r * np.sin(th)])
        rings.append(ids)
    P.append([-(H_ + R_), 0, 0]); poleL = 0
    for k in range(1, K_ + 1):
        phi = k / (K_ + 1) * np.pi / 2; ring(-H_ - R_ * np.cos(phi), R_ * np.sin(phi))
    for a in range(A_):
        ring(-H_ + 2 * H_ * a / (A_ - 1), R_)
    for k in range(K_, 0, -1):
        phi = k / (K_ + 1) * np.pi / 2; ring(H_ + R_ * np.cos(phi), R_ * np.sin(phi))
    poleR = len(P); P.append([H_ + R_, 0, 0])
    S = []
    link = lambda a, b: S.append((a, b)) if a != b else None
    for ids in rings:
        for j in range(C): link(ids[j], ids[(j + 1) % C])
    for r in range(len(rings) - 1):
        a, b = rings[r], rings[r + 1]
        for j in range(C): link(a[j], b[j]); link(a[j], b[(j + 1) % C])
    for j in range(C): link(poleL, rings[0][j]); link(poleR, rings[-1][j])
    mid = rings[len(rings) // 2]
    return dict(P=np.array(P), S=S, rings=rings, mic=mid[0], hit=rings[K_][C // 2], axis=1, C=C)


class Tank:
    def __init__(self, C=7, ratio=6.0, sub=0.0006, loss=0.5, decay=4.0, angle=0.15):
        self.m = mesh(C); self.ratio, self.sub, self.loss, self.decay, self.angle = ratio, sub, loss, decay, angle
        self.N = len(self.m["P"]); self.pins = set(); self.cut = set()

    # ----- matrices -----
    def _free(self):
        return [q for q in range(self.N) if q not in self.pins]

    def K1D1(self):
        """Stiffness with kT = 1 (kL = ratio) and the dashpot Laplacian, over free DOFs."""
        P, free = self.m["P"], self._free(); mp = {q: i for i, q in enumerate(free)}; n = 3 * len(free)
        K, D = np.zeros((n, n)), np.zeros((n, n))
        for s, (a, b) in enumerate(self.m["S"]):
            if s in self.cut: continue
            u = P[b] - P[a]; u /= np.linalg.norm(u)
            Cb = np.eye(3) + (self.ratio - 1) * np.outer(u, u)
            for M, B in ((K, Cb), (D, np.eye(3))):
                i, j = mp.get(a), mp.get(b)
                if i is not None: M[3*i:3*i+3, 3*i:3*i+3] += B
                if j is not None: M[3*j:3*j+3, 3*j:3*j+3] += B
                if i is not None and j is not None:
                    M[3*i:3*i+3, 3*j:3*j+3] -= B; M[3*j:3*j+3, 3*i:3*i+3] -= B
        return K, D, mp

    def lowest_nonrigid(self, K1):
        w = np.linalg.eigvalsh(K1)
        rigid = 3 if not self.pins else 0   # the engine's law leaves only the three translations at zero energy
        return w[rigid:][w[rigid:] > 1e-9][0]

    def vec(self, node, amt):
        """RESONATOR's mk(): the axis direction tilted toward the node's radial direction by amt."""
        v = np.zeros(3); v[self.m["axis"]] = 1
        a = self.m["P"][node] - self.m["P"].mean(0); a = a / (np.linalg.norm(a) or 1)
        p = a - (a @ v) * v; pl = np.linalg.norm(p) or 1
        o = v + amt * p / pl; return o / np.linalg.norm(o)

    def tuned_kT(self, f0):
        K1, _, _ = self.K1D1(); return (2 * np.pi * f0) ** 2 / (self.lowest_nonrigid(K1) + self.sub)

    def modes(self, f0, kT=None):
        """Damped modes of the tuned tank: poles s_k and the strike->pickup residues for two pickups.
        kT given: keep that stiffness (pins and cuts then move the pitch, as they would in the object)."""
        K1, D1, mp = self.K1D1()
        if kT is None:
            kT = (2 * np.pi * f0) ** 2 / (self.lowest_nonrigid(K1) + self.sub)   # lowest non-rigid mode at f0
        K = kT * (K1 + self.sub * np.eye(len(K1)))
        lossK = self.loss * 0.02 * (220 / max(20, f0)) ** 0.8
        c = lossK * np.sqrt(kT); gam = 6.91 / self.decay if self.decay > 0 else 0
        Dm = c * D1 + gam * np.eye(len(K1))
        n = len(K); A = np.zeros((2 * n, 2 * n)); A[:n, n:] = np.eye(n); A[n:, :n] = -K; A[n:, n:] = -Dm
        s, V = np.linalg.eig(A); Vi = np.linalg.inv(V)
        hit = self.m["hit"]; mic = self.m["mic"]
        far = max(self._free(), key=lambda q: np.sum((self.m["P"][q] - self.m["P"][mic]) ** 2))
        b = np.zeros(2 * n); hv = self.vec(hit, 1.9 * self.angle); b[n + 3 * mp[hit]: n + 3 * mp[hit] + 3] = hv  # force -> acceleration (m = 1)
        res = []
        for node in (mic, far):
            cvec = np.zeros(2 * n); cvec[n + 3 * mp[node]: n + 3 * mp[node] + 3] = self.vec(node, 1.5 * self.angle)  # pickup senses velocity
            res.append((cvec @ V) * (Vi @ b))
        keep = s.imag > 0                                       # one of each conjugate pair (doubled below)
        return dict(s=s[keep], r=np.array([r[keep] for r in res]), kT=kT, K=K, D=Dm, mp=mp, hv=hv, b=b,
                    far=far)

    def strike(self, f0, dur, sr=44100, pulse=0.003, amp=1.0, kT=None):
        """Two pickups' velocity after a sin^2 force pulse of length `pulse` at the hit node."""
        M = self.modes(f0, kT); t = np.arange(int(dur * sr)) / sr
        y = np.zeros((2, len(t)))
        ok = np.abs(M["s"].imag) / (2 * np.pi) < 0.45 * sr       # drop modes above Nyquist
        for k in np.nonzero(ok)[0]:
            e = np.exp(M["s"][k] * t)
            y += 2 * np.real(M["r"][:, k:k+1] * e)
        # the force pulse: convolve the impulse response with the sin^2 window
        L = int(pulse * sr); w = np.sin(np.pi * (np.arange(L) + 0.5) / L) ** 2 if L >= 2 else np.ones(1); w /= w.sum()
        y = np.array([np.convolve(ch, w)[:len(t)] for ch in y])
        return amp * y.T, M


def direct_check(f0=110.0, dur=0.25, sr=44100, sub_steps=16):
    """Second derivation: integrate the same linear system directly (semi-implicit Euler) and compare."""
    tk = Tank(); y_modal, M = tk.strike(f0, dur, sr, pulse=1.0 / sr)
    n = len(M["K"]); dt = 1.0 / (sr * sub_steps); x = np.zeros(n); v = np.zeros(n)
    hit = tk.m["hit"]; mp = M["mp"]; f = np.zeros(n); f[3 * mp[hit]:3 * mp[hit] + 3] = M["hv"]
    mic = tk.m["mic"]; cv = tk.vec(mic, 1.5 * tk.angle); out = []
    v[:] = f                                   # unit impulse of force: delta-v = f (m = 1)
    for i in range(int(dur * sr)):
        out.append(cv @ v[3 * mp[mic]:3 * mp[mic] + 3])
        for _ in range(sub_steps):
            a = -M["K"] @ x - M["D"] @ v; v += a * dt; x += v * dt
    out = np.array(out); ym = y_modal[:, 0]
    return float(np.corrcoef(out[1:], ym[1:])[0, 1]), float(np.max(np.abs(out - ym)) / np.max(np.abs(out)))


if __name__ == "__main__":
    tk = Tank(); print("masses", tk.N, "springs", len(tk.m["S"]))
    K1, D1, mp = tk.K1D1(); w = np.linalg.eigvalsh(K1)
    print("rigid eigenvalues (should be ~0):", np.round(w[:6], 9))
    M = tk.modes(55.0); fr = np.sort(M["s"].imag / (2 * np.pi))
    print("lowest modes at f0 = 55 Hz:", np.round(fr[:12], 2))
    print("ratios to f0:", np.round(fr[:12] / 55.0, 3))
    corr, err = direct_check()
    print(f"modal vs direct integration: correlation {corr:.5f}, max relative error {err:.4f}")
