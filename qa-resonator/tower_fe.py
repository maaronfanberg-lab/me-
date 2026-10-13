# Run: python3 qa-resonator/tower_fe.py [h_mm]
# Independent check of the water-tower bowl: a thin shell of revolution solved by finite elements along the
# meridian, one circumferential harmonic m at a time (the standard approach for shells of revolution,
# Kalnins 1964). Membrane strains (Novozhilov) plus Donnell-type bending; linear elements for the in-surface
# displacements u (meridional) and v (circumferential), Hermite cubics for the normal displacement w.
#   u = U(s) cos m t, v = V(s) sin m t, w = W(s) cos m t
#   e1 = U' + W/R1,  e2 = (m V + r' U)/r + W/R2,  g12 = -m U/r + V' - r' V / r
#   k1 = -W'',  k2 = -(r'/r) W' + (m^2/r^2) W,  k12 = 2 (m/r) (W' - r' W / r)
# Energy per unit area: C/2 [e1^2 + e2^2 + 2 nu e1 e2 + (1-nu)/2 g12^2] + D/2 [k1^2 + k2^2 + 2 nu k1 k2 + (1-nu)/2 k12^2]
# with C = E h/(1-nu^2), D = E h^3/(12 (1-nu^2)); kinetic rho h (U^2+V^2+W^2)/2; area element r ds dt.
# Check 1: a complete sphere against the Abaqus Benchmarks Guide 1.4.1 membrane column (R = 3 m, E = 180 GPa,
# rho = 7670, nu = 1/3), which tower_acoustics.py reproduces in closed form.
# Check 2: the same sphere at h/R tiny vs the closed-form membrane equation (the bending terms must vanish).
# Then: the Superior bowl as an oblate spheroid (23 m x 17.5 m), clamped where it meets the cone neck.
import math, sys
import numpy as np
from scipy.linalg import eigh

GP = np.polynomial.legendre.leggauss(4)

def solve(prof, s_end, m, E, nu, rho, h, ne=120, clamp_end=True, pole_free_hole=True, nmodes=12, pole_end=False):
    """prof(s) -> (r, r', z', 1/R1, 1/R2) along the meridian, s from 0 to s_end."""
    C = E * h / (1 - nu * nu); D = E * h ** 3 / (12 * (1 - nu * nu))
    nn = ne + 1
    # dofs per node: U, V, W, W'
    nd = 4 * nn
    K = np.zeros((nd, nd)); M = np.zeros((nd, nd))
    xs = np.linspace(0, s_end, nn)
    for e in range(ne):
        a, b = xs[e], xs[e + 1]; L = b - a
        dofs = [4 * e, 4 * e + 1, 4 * e + 2, 4 * e + 3, 4 * e + 4, 4 * e + 5, 4 * e + 6, 4 * e + 7]
        ke = np.zeros((8, 8)); me = np.zeros((8, 8))
        for xi, wq in zip(*GP):
            t = (xi + 1) / 2; s = a + t * L; w = wq * L / 2
            r, rp, zp, k1c, k2c = prof(s)
            # shape functions: linear N for U,V; Hermite H for W
            N = np.array([1 - t, t]); dN = np.array([-1, 1]) / L
            H = np.array([1 - 3 * t * t + 2 * t ** 3, L * (t - 2 * t * t + t ** 3), 3 * t * t - 2 * t ** 3, L * (-t * t + t ** 3)])
            dH = np.array([-6 * t + 6 * t * t, L * (1 - 4 * t + 3 * t * t), 6 * t - 6 * t * t, L * (-2 * t + 3 * t * t)]) / L
            ddH = np.array([-6 + 12 * t, L * (-4 + 6 * t), 6 - 12 * t, L * (-2 + 6 * t)]) / L ** 2
            # map to element dof order [U0,V0,W0,W0',U1,V1,W1,W1']
            def vec(cU=None, cV=None, cW=None):
                v = np.zeros(8)
                if cU is not None: v[0] += cU[0]; v[4] += cU[1]
                if cV is not None: v[1] += cV[0]; v[5] += cV[1]
                if cW is not None: v[2] += cW[0]; v[3] += cW[1]; v[6] += cW[2]; v[7] += cW[3]
                return v
            e1 = vec(cU=dN, cW=H * k1c)
            e2 = vec(cU=N * rp / r, cV=N * m / r, cW=H * k2c)
            g = vec(cU=-m * N / r, cV=dN - rp * N / r)
            b1 = vec(cW=-ddH)
            b2 = vec(cW=-(rp / r) * dH + (m * m / (r * r)) * H)
            b12 = vec(cW=2 * (m / r) * (dH - rp * H / r))
            Bm = np.array([e1, e2, g]); Bb = np.array([b1, b2, b12])
            Dm = C * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
            Db = D * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
            ke += (Bm.T @ Dm @ Bm + Bb.T @ Db @ Bb) * r * w
            Nu = vec(cU=N); Nv = vec(cV=N); Nw = vec(cW=H)
            me += rho * h * (np.outer(Nu, Nu) + np.outer(Nv, Nv) + np.outer(Nw, Nw)) * r * w
        K[np.ix_(dofs, dofs)] += ke; M[np.ix_(dofs, dofs)] += me
    # regularity at a pole (r -> 0), applied at the tiny hole the mesh starts from: a free edge there carries
    # spurious edge modes (a first version had them: an m = 2 mode at 52 Hz living on a 0.3 m hole at the top).
    #   m = 0: U = 0, W' = 0 (V is dropped for m = 0 below);  m = 1: W = 0, W' = 0... only W (lateral translation of
    #   the pole is allowed);  m >= 2: U = V = W = W' = 0
    def pole(k):   # k = node index (0 = start, ne = end)
        b = 4 * k
        if m == 0: return [b, b + 3]
        if m == 1: return [b + 2]
        return [b, b + 1, b + 2, b + 3]
    fixed = list(pole(0)) if pole_free_hole else []
    if clamp_end: fixed += [nd - 4, nd - 3, nd - 2, nd - 1]
    elif pole_end: fixed += [i for i in pole(ne)]
    free = [i for i in range(nd) if i not in fixed]
    # angular factor: integral of cos^2 or sin^2 over t is pi (2 pi for m = 0 cos^2); it cancels in K/M except
    # m = 0, where v-motion (sin 0 t) vanishes identically: drop V for m = 0 (torsion handled separately, not needed)
    if m == 0:
        free = [i for i in free if i % 4 != 1]
    free = [i for i in free if i not in fixed]
    Kf = K[np.ix_(free, free)]; Mf = M[np.ix_(free, free)]
    lam, vec_ = eigh(Kf, Mf, subset_by_index=[0, min(nmodes, len(free)) - 1])
    f = np.sqrt(np.maximum(lam, 0)) / (2 * math.pi)
    # volume change for each mode (only m = 0 changes the volume): integral of W r ds
    out = []
    for k in range(len(f)):
        full = np.zeros(nd); full[free] = vec_[:, k]
        W = full[2::4]; U = full[0::4]; V = full[1::4]
        rr = np.array([prof(s)[0] for s in xs])
        vol = abs(np.trapezoid(W * rr, xs)) if m == 0 else 0.0
        wE = np.trapezoid(W * W * rr, xs); tE = np.trapezoid((U * U + V * V + W * W) * rr, xs)
        nodes = int(np.sum(np.abs(np.diff(np.sign(W[np.abs(W) > 1e-6 * np.abs(W).max()])) ) > 0))
        out.append((f[k], m, vol / math.sqrt(max(tE, 1e-300) * np.trapezoid(rr, xs)), wE / tE, nodes))
    return out

def sphere(R, hole_deg=0.5):
    s0 = math.radians(hole_deg) * R
    def prof(s):
        th = (s + s0) / R
        return (R * math.sin(th), math.cos(th), -math.sin(th), 1 / R, 1 / R)
    return prof, math.pi * R - 2 * s0

def spheroid(a, b, th0_deg, th1_deg, n=4000):
    # meridian by arc length: x = a sin th, z = b cos th, th from th0 (near the top) to th1 (neck)
    th = np.linspace(math.radians(th0_deg), math.radians(th1_deg), n)
    dx = a * np.cos(th); dz = -b * np.sin(th)
    ds = np.hypot(dx, dz); s = np.concatenate([[0], np.cumsum(0.5 * (ds[1:] + ds[:-1]) * np.diff(th))])
    def prof(sq):
        t = np.interp(sq, s, th)
        x, xp, zp = a * math.sin(t), a * math.cos(t), -b * math.sin(t)
        l = math.hypot(xp, zp); rp, zps = xp / l, zp / l
        # curvatures: meridional 1/R1 = |x' z'' - z' x''| / l^3; circumferential 1/R2 = sin(normal angle)/r = -z'/(l r)
        xpp, zpp = -a * math.sin(t), -b * math.cos(t)
        k1 = abs(xp * zpp - zp * xpp) / l ** 3
        k2 = -zps / x
        return (x, rp, zps, k1, k2)
    return prof, float(s[-1])

if __name__ == '__main__':
    h_mm = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    # ---- check 1: Abaqus benchmark sphere, membrane column (h/R = 0.01 here so bending is small for low n)
    E, nu, rho, R = 180e9, 1 / 3, 7670.0, 3.0
    prof, L = sphere(R)
    bench = {2: 187.34, 3: 222.57, 4: 236.56, 6: 247.37}
    got = {}
    for m in range(0, 7):
        for (f, mm, vol, wsh, nod) in solve(prof, L, m, E, nu, rho, 0.0003 * R, ne=160, clamp_end=False, nmodes=14, pole_end=True):
            got.setdefault(m, []).append(f)
    # a complete sphere's degree-n mode appears in every harmonic m <= n; its lowest-branch frequency is m-independent,
    # so collect all frequencies and match each benchmark value to the nearest computed one
    allf = sorted(f for v in got.values() for f in v if f > 1)
    print('check 1 (sphere, membrane limit h/R = 0.0003) vs Abaqus membrane column:')
    for n, fb in bench.items():
        near = min(allf, key=lambda f: abs(f - fb)); print(f'   n={n}: benchmark {fb:.2f} Hz, FE nearest {near:.2f} Hz ({100 * (near / fb - 1):+.2f}%)')
    # check 1b: with the pole conditions, the lowest mode of each order m on the sphere is the benchmark's n = m
    low = {m: min(f for (f, *_r) in solve(prof, L, m, E, nu, rho, 0.0003 * R, ne=160, clamp_end=False, nmodes=3, pole_end=True)) for m in (2, 3, 4)}
    print('check 1b (no spurious modes): lowest per order m = 2, 3, 4:', ', '.join(f'{low[m]:.2f}' for m in (2, 3, 4)), 'Hz (benchmark 187.34, 222.57, 236.56)')
    # ---- the bowl
    import json, os
    E, nu, rho = 200e9, 0.30, 7850.0
    prof, L = spheroid(11.5, 8.75, 1.0, 156.0)
    out = {'source': 'qa-resonator/tower_fe.py', 'bowl': 'oblate spheroid 23 x 17.5 m, clamped at the cone neck (156 deg), steel'}
    for hmm in ([h_mm] + [x for x in (10.0, 16.0, 25.0) if x != h_mm]):
        rows = []
        for m in range(0, 46):
            rows += solve(prof, L, m, E, nu, rho, hmm / 1000, ne=140, clamp_end=True, nmodes=110)
        rows.sort()
        cov = min(max(r[0] for r in rows if r[1] == m) for m in range(46))
        br = max((r for r in rows if r[1] == 0), key=lambda r: r[2])
        m2 = next(r for r in rows if r[1] == 2 and r[3] > 0.6)
        print(f'\nbowl, {hmm:.0f} mm (complete below {cov:.0f} Hz): breathing {br[0]:.1f} Hz (volume share {br[2]:.2f}); lowest m=2 mode {m2[0]:.1f} Hz;'
              f' global modes below the cluster: ' + ', '.join(f'{r[0]:.1f} Hz (m{r[1]})' for r in rows if r[0] < 50))
        q = {}
        for M in (4, 5, 6, 7, 8, 45):
            c = []
            for (f, m, vol, nrm, nod) in rows:
                if m <= M and nrm > 0.6 and 50 <= f < br[0]:
                    c += [f] if m == 0 else [f, f]
            c.sort(); Q = lambda p: c[min(len(c) - 1, int(p * len(c)))]
            q[M] = [round(Q(0.1), 1), round(Q(0.5), 1), round(Q(0.9), 1), len(c)]
            print(f'   modes with m <= {M} between 50 Hz and breathing: {len(c)} shapes, 10th/50th/90th percentile {Q(.1):.0f} / {Q(.5):.0f} / {Q(.9):.0f} Hz')
        out[f'{hmm:.0f}mm'] = {'breathing': round(br[0], 2), 'breathing_volume_share': round(br[2], 3), 'm2_lowest': round(m2[0], 2), 'cluster_by_mmax': q}
    json.dump(out, open(os.environ.get('TOWER_FE_OUT') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tower_fe_modes.json'), 'w'), indent=1)
