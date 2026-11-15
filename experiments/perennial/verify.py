#!/usr/bin/env python3
"""Independent checks of Perennial. Any FAIL exits non-zero and blocks the daily commit."""
import cmath, glob, hashlib, json, math, os, sys, tempfile
from decimal import Decimal as D, getcontext
import engine as E, grow as G
getcontext().prec = 60
fails = 0
def check(name, value, limit, ok=None):
    global fails
    ok = value <= limit if ok is None else ok
    fails += 0 if ok else 1
    print("%-4s %-52s %.3e (limit %.1e)" % ("PASS" if ok else "FAIL", name, value, limit))

class C:
    """Complex numbers on 60-digit decimals: shares no arithmetic with the engine."""
    __slots__ = ("x", "y")
    def __init__(self, x, y=0):
        self.x, self.y = D(x), D(y)
    def __add__(self, o): return C(self.x + o.x, self.y + o.y)
    def __sub__(self, o): return C(self.x - o.x, self.y - o.y)
    def __mul__(self, o): return C(self.x * o.x - self.y * o.y, self.x * o.y + self.y * o.x)
    def __truediv__(self, o):
        n = o.x * o.x + o.y * o.y
        return C((self.x * o.x + self.y * o.y) / n, (self.y * o.x - self.x * o.y) / n)
    def abs(self): return (self.x * self.x + self.y * self.y).sqrt()
ONE, TWO = C(1), C(2)

def dec_centre(c0, P):
    """A second, unrelated Newton solve for the centre, at 60 digits."""
    c = C(c0.real, c0.imag)
    for _ in range(40):
        z, dz = C(0), C(0)
        for _ in range(P):
            dz, z = TWO * z * dz + ONE, z * z + c
        step = z / dz
        c = c - step
        if step.abs() < D(10) ** -40:
            return c
    raise RuntimeError("decimal newton")

def dec_radius_and_period(c, P):
    """Conformal radius from a 60-digit difference of the multiplier, and the exact period."""
    z, first = C(0), None
    for n in range(1, P + 1):
        z = z * z + c
        if z.abs() < D(10) ** -25:
            first = n
            break
    def multiplier(c1):
        w = C(0)
        for _ in range(12):
            z, a = w, ONE
            for _ in range(P):
                a, z = TWO * z * a, z * z + c1
            w = w - (z - w) / (a - ONE)
        z, a = w, ONE
        for _ in range(P):
            a, z = TWO * z * a, z * z + c1
        return a
    h = C(D(10) ** -18)
    return D(2) * h.abs() / (multiplier(c + h) - multiplier(c - h)).abs(), first

org = E.Organism()
days = G.load(org)
buds = org.buds[1:]
print("buds", len(buds), "failures", len(org.failures))

# 1. Published anchors: the centres of well-known components.
known = {(0, 1, 2): -1 + 0j, (0, 1, 3): complex(-0.12256116687665, 0.74486176661974)}
for (par, p, q), c in known.items():
    check("known centre %d/%d" % (p, q), abs(complex(*E.grow(org.buds[par], p, q)["c"]) - c), 1e-12)
check("period-4 known centre", abs(complex(*E.grow(E.grow({**org.buds[0]}, 1, 2) | {"id": -1, "depth": 1}, 1, 2)["c"]) + 1.3107026413368), 1e-11)

# 2. Every stored bud, against 60-digit arithmetic for a deterministic spread of samples.
step = max(1, len(buds) // 40)
worst_c, worst_r, worst_p = 0.0, 0.0, 0
for b in buds[::step]:
    c = complex(*b["c"])
    cm = dec_centre(c, b["period"])
    r, first = dec_radius_and_period(cm, b["period"])
    worst_c = max(worst_c, float((cm - C(c.real, c.imag)).abs()) / b["radius"])
    worst_r = max(worst_r, abs(float(r) / b["radius"] - 1))
    worst_p += 0 if first == b["period"] else 1
check("centre error / radius, vs 60 digits", worst_c, 1e-5)
check("conformal radius relative error, vs 60 digits", worst_r, 1e-4)
check("buds whose exact period differs", worst_p, 0)

# 3. The law's derivation: dc/dmu at the child's root should equal dc/dlambda(parent)/q^2.
worst = 0.0
for b in buds[::step][:12]:
    cc, P = complex(*b["c"]), b["period"]
    d = []
    for mu in (0.995, 0.999):
        zz, ca = E.walk(cc, P, mu + 0j, b["radius"], steps=24)
        d.append(abs(E.dc_dlambda(zz, ca, P)))
    extrap = d[1] + (d[1] - d[0]) * (1 - 0.999) / (0.999 - 0.995)
    worst = max(worst, abs(extrap / b["predicted"] - 1))
check("dc/dmu at root vs law's prediction", worst, 3e-2)

# 4. dc/dlambda by implicit formula vs centred finite difference.
worst = 0.0
for b in buds[::step][:12]:
    c0, P, r = complex(*b["c"]), b["period"], b["radius"]
    lam = 0.5 * cmath.exp(0.7j)
    z, c = E.walk(c0, P, lam, r)
    _, c1 = E.solve_lambda(lam + 2e-3, z, c, P, r)
    _, c2 = E.solve_lambda(lam - 2e-3, z, c, P, r)
    err = abs((c1 - c2) / 4e-3 / E.dc_dlambda(z, c, P) - 1)
    # Allow for the roundoff a small bud puts into the difference itself.
    worst = max(worst, err / (1e-4 + 4 * E.FLOOR / (4e-3 * r)))
check("dc/dlambda implicit vs difference, over noise limit", worst, 1)

# 5. Boundary coefficients reconstruct the true boundary.
check("worst boundary reconstruction / radius", max(b["resid"] for b in buds), 1e-2)

# 6. Replay and chain integrity.
prev = "seed"
broken = 0
for d in days:
    body = {k: v for k, v in d.items() if k != "chain"}
    broken += 0 if d["prev"] == prev and hashlib.sha256(G.dumps(body).encode()).hexdigest() == d["chain"] else 1
    prev = d["chain"]
check("broken links in the day chain", broken, 0)

# 7. Determinism and restart: the last stored day regrown from replay must match byte for byte.
if days:
    fresh = E.Organism()
    for ev in sorted([e for d in days[:-1] for e in d["buds"] + d["failures"]],
                     key=G.event_key):
        fresh.replay_failure(ev) if "after" in ev else fresh.replay(ev)
    again = G.grow_day(fresh, days[-1]["day"], days[-1]["prev"])
    check("last day regrown after restart, bytes differing", 0 if G.dumps(again) == G.dumps(days[-1]) else 1, 0)

# 8. Mirror truth: conjugate buds of real parents must be exact mirrors.
by_key = {(b["parent"], b["p"], b["q"]): b for b in buds}
worst = 0.0
for b in buds:
    if org.buds[b["parent"]]["c"][1] == 0 and (b["parent"], b["q"] - b["p"], b["q"]) in by_key and b["q"] > 2:
        m = by_key[(b["parent"], b["q"] - b["p"], b["q"])]
        worst = max(worst, abs(complex(*b["c"]).conjugate() - complex(*m["c"])) / b["radius"])
check("conjugate buds mirror error / radius", worst, 1e-6)

print("FAILED CHECKS:", fails)
sys.exit(1 if fails else 0)
