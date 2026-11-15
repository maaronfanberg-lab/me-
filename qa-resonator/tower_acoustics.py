# Run: python3 qa-resonator/tower_acoustics.py   (research numbers behind docs/research/resonator-water-tower-2026-10-12.md)
# Superior, WI water tower (single-pedestal spheroid), empty: first acoustic estimates.
import math, numpy as np
E, rho, nu = 200e9, 7850.0, 0.30            # structural steel
cp = math.sqrt(E / (rho * (1 - nu**2)))      # plate (membrane) wave speed
rho0, c0 = 1.2, 343.0                        # air at ~20 C (Superior winters: c0 ~ 325 m/s at -10 C)
print(f"plate wave speed c_p = {cp:.0f} m/s")

# ---- check of the membrane equation against the Abaqus benchmark (R = 3 m, E=180 GPa, rho=7670, nu=1/3)
def omega_sphere(n, nu):
    lam = n * (n + 1); b = 1 + 3 * nu + lam; c = (lam - 2) * (1 - nu**2)
    disc = math.sqrt(b * b - 4 * c); return math.sqrt(max(0.0, (b - disc) / 2)), math.sqrt((b + disc) / 2)
cpb = math.sqrt(180e9 / (7670 * (1 - 1/9)))
bench = {2: 187.34, 3: 222.57, 4: 236.56, 5: 239.56, 6: 247.37, 7: 249.80, 8: 251.41, 9: 252.54, 10: 253.35}
print("benchmark check (membrane, Hz):", ", ".join(f"n{n} {omega_sphere(n, 1/3)[0]*cpb/(2*math.pi*3.0):.2f}/{f}" for n, f in bench.items()))

# ---- the bowl: estimated 23 m across, ~17.5 m tall -> volume-equivalent sphere radius
D, Hb = 23.0, 17.5
V = 4/3 * math.pi * (D/2)**2 * (Hb/2) * 0.82          # spheroid volume, cone neck takes ~18% off
Req = (3 * V / (4 * math.pi)) ** (1/3)
print(f"bowl volume ~{V:.0f} m^3 ({V*264.17/1e6:.2f} million US gal), equivalent sphere radius {Req:.1f} m")
for R, tag in [(Req, 'volume-equivalent sphere'), (D/2, 'equator radius')]:
    fr = cp / (2 * math.pi * R)
    low = [omega_sphere(n, nu)[0] * fr for n in (2, 3, 4, 6, 10, 20)]
    up = [omega_sphere(n, nu)[1] * fr for n in (0, 1, 2, 3)]
    print(f"  R={R:.1f} m ({tag}): ring {fr:.0f} Hz; breathing {math.sqrt(2*(1+nu))*fr:.0f} Hz; lower branch n=2,3,4,6,10,20: "
          + ", ".join(f"{f:.0f}" for f in low) + f" Hz (limit {math.sqrt(1-nu**2)*fr:.0f}); upper n=0..3: " + ", ".join(f"{f:.0f}" for f in up) + " Hz")
# how far the cluster stays a cluster: bending correction ~ beta^2 (lam-2)^2 (calibrated loosely on the benchmark's h/R=0.05 rows)
for h in (0.010, 0.016, 0.025):
    b2 = (h / Req)**2 / 12
    nmax = next(n for n in range(2, 400) if b2 * (n*(n+1) - 2)**2 > 0.10 * (1 - nu**2))
    print(f"  wall {h*1000:.0f} mm: bending lifts modes by >5% only above n ~ {nmax}; the cluster holds ~{sum(2*n+1 for n in range(4, nmax)):,} mode shapes")
# fluid side: radiation from the bowl
for f in (60, 75, 130):
    ka = 2 * math.pi * f * Req / c0
    print(f"  at {f} Hz: ka = {ka:.1f} (modes with n below ~ka radiate efficiently)")

# ---- the column: cylinder ~5 m across, ~15 m of straight + flared shell
def donnell(m, n, R, L, h):
    lam = m * math.pi * R / L; b2 = h*h / (12 * R*R); s = lam*lam + n*n
    return math.sqrt(((1 - nu**2) * lam**4 + b2 * s**4) / s**2)
Rc, Lc, hc = 2.5, 15.0, 0.016
frc = cp / (2 * math.pi * Rc)
rows = sorted((donnell(m, n, Rc, Lc, hc) * frc, m, n) for m in (1, 2, 3) for n in range(1, 13))
print(f"column: ring frequency {frc:.0f} Hz; lowest shell modes (Donnell, simply supported): " + ", ".join(f"{f:.1f} Hz (m{m},n{n})" for f, m, n in rows[:6]))

# ---- coincidence and damping
for h in (0.010, 0.016, 0.025):
    fc = c0**2 / (1.81 * cp * h)
    print(f"coincidence frequency, {h*1000:.0f} mm wall: {fc:.0f} Hz")
h = 0.012; ms = rho * h
for f, sigma, tag in [(65, 1.0, 'low bowl mode, radiates well'), (75, 0.05, 'high-order cluster mode, radiates poorly'), (130, 1.0, 'breathing mode')]:
    eta_rad = rho0 * c0 * sigma / (ms * 2 * math.pi * f); eta = eta_rad + 1e-3
    print(f"  {tag}: {f} Hz, radiation loss {eta_rad:.4f} + structure 0.0010 -> T60 {2.2/(eta*f):.1f} s")
# interior: Sabine, painted steel alpha ~0.01-0.02, plus air absorption
S = 4 * math.pi * Req**2 * 1.03
for alpha in (0.01, 0.02):
    print(f"inside the empty bowl (alpha {alpha}): T60 ~ {0.161*V/(alpha*S):.0f} s at low/mid frequencies; lowest air modes ~ "
          + ", ".join(f"{k*c0/(2*math.pi*Req):.0f}" for k in (2.082, 3.342, 4.493)) + " Hz")

# ---- a humongous mallet: 200 kg head at 4 m/s (energy 1.6 kJ), 0.6 m face, padding 8 cm (core rigid)
mH, v0, A, t = 200.0, 4.0, math.pi * 0.3**2, 0.08
def strike(law, dt=2e-6):
    x, v, F_hist, xmax, wl = 0.0, v0, [], 0.0, 0.0
    while True:
        F = law(x, v); a = -F / mH; v += a * dt; x += v * dt; F_hist.append(max(F, 0)); xmax = max(xmax, x)
        if x <= 0 and v < 0 and len(F_hist) > 10: break
        if len(F_hist) > 200000: break
    F_hist = np.array(F_hist); tau = (F_hist > 0.02 * F_hist.max()).sum() * dt
    spec = np.abs(np.fft.rfft(F_hist, 1 << 20)); fq = np.fft.rfftfreq(1 << 20, dt); spec /= spec[0]
    f20 = fq[np.argmax(spec < 0.1)]                 # first frequency where the force spectrum is 20 dB down
    return tau, F_hist.max(), f20, -v / v0, xmax
mats = {
  # wool felt: hardening power law (Russell 1997: p ~ 2-3.5), modest hysteresis; K chosen for a soft, thick pad
  # thick wool wrap (10 cm): soft at first touch, hardening (p 2.5, Russell 1997); 30% loading/unloading hysteresis
  'thick wool (p 2.5)': lambda x, v: (4.0e8 * max(x, 0)**2.5) * (1 + 0.3 * math.copysign(1, v)) if x > 0 else 0.0,
  # rubber: elastic, Hertz-like (p 1.5); E ~ 4 MPa
  'rubber (p 1.5)': lambda x, v: (4.0e6 * A / t * max(x, 0)**1.5 / 0.02**0.5) * (1 + 0.1 * math.copysign(1, v)) if x > 0 else 0.0,
  # thick leather over a hard core: stiffer, nearly linear, some loss; E ~ 30 MPa over 2 cm
  'thick leather': lambda x, v: (30e6 * A / 0.02 * max(x, 0)) * (1 + 0.15 * math.copysign(1, v)) if x > 0 else 0.0,
}
for nm, law in mats.items():
    tau, Fm, f20, rest, xm = strike(law)
    print(f"mallet {nm}: contact {tau*1000:.1f} ms, peak force {Fm/1000:.0f} kN, force spectrum 20 dB down at {f20:.0f} Hz, rebound {rest:.2f}, pad squeezed {xm*100:.1f} cm")
# compressed Styrofoam (EPS 32-48 kg/m3: crushes at 173-414 kPa, AFM Foam-Control data): elastic to ~2% strain, then a plateau
for sc in (173e3, 414e3):
    Ee, ey = 6e6, None
    state = {'xp': 0.0}
    def eps_law(x, v, sc=sc):
        strain = max(x, 0) / t; yield_strain = sc / 6e6
        if x <= state['xp']: return 0.0
        if v > 0 and strain - state['xp'] / t >= yield_strain:   # crushing: plateau force, permanent set grows
            state['xp'] = x - yield_strain * t; return sc * A
        return 6e6 * A * (x - state['xp']) / t
    tau, Fm, f20, rest, xm = strike(eps_law)
    print(f"mallet compressed Styrofoam (crush {sc/1000:.0f} kPa): contact {tau*1000:.1f} ms, peak {Fm/1000:.0f} kN, 20 dB down at {f20:.0f} Hz, rebound {rest:.2f}, permanent dent {state['xp']*100:.1f} cm")
