#!/usr/bin/env python3
"""Perennial: grows real satellite components of the Mandelbrot set.

Every bud is a hyperbolic component found by Newton's method on f_c(z)=z^2+c.
The size law predicts each bud before it is measured. The largest failure of the
prediction chooses where growth goes next. No randomness is used: the output is a
pure function of the code and the number of buds grown.
"""
import cmath, ctypes, hashlib, heapq, json, math, os, subprocess, sys, tempfile
from math import gcd, pi

TOL = 1e-11          # Newton step tolerance, relative to bud size
FLOOR = 2e-14        # absolute step floor, set by double-precision roundoff near |c|~2
MAX_PERIOD = 4096    # beyond this a bud is recorded as unresolved, never faked
MIN_RADIUS = 1e-8    # below this double precision cannot certify a bud
N_BOUNDARY = 32      # boundary samples per bud
N_COEFF = 6          # stored Taylor coefficients of c(lambda)

class NoConvergence(Exception):
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_SO = os.path.join(tempfile.gettempdir(), "perennial_jet_%d.so" % os.getpid())
subprocess.run(["gcc", "-O2", "-ffp-contract=off", "-fPIC", "-shared", "-o", _SO,
                os.path.join(_HERE, "jet.c"), "-lm"], check=True)
_lib = ctypes.CDLL(_SO)
_lib.jet.argtypes = [ctypes.c_double] * 4 + [ctypes.c_long, ctypes.POINTER(ctypes.c_double)]
_lib.orbit0.argtypes = [ctypes.c_double] * 2 + [ctypes.c_long, ctypes.POINTER(ctypes.c_double)]

def jet(z, c, P):
    """Return f^P(z) and its first and second partial derivatives."""
    z, c = complex(z), complex(c)
    o = (ctypes.c_double * 10)()
    if not _lib.jet(z.real, z.imag, c.real, c.imag, P, o):
        raise NoConvergence("orbit escaped")
    return tuple(complex(o[2 * k], o[2 * k + 1]) for k in range(5))

def orbit0(c, P):
    o = (ctypes.c_double * 4)()
    if not _lib.orbit0(c.real, c.imag, P, o):
        raise NoConvergence("centre escaped")
    return complex(o[0], o[1]), complex(o[2], o[3])

def solve_lambda(lam, z, c, P, scale, iters=30):
    """Newton solve of f^P(z)=z and (f^P)'(z)=lam from a warm start."""
    for _ in range(iters):
        w, a, b, d, e = jet(z, c, P)
        g1, g2 = w - z, a - lam
        m11, m12, m21, m22 = a - 1, b, d, e
        det = m11 * m22 - m12 * m21
        if det == 0:
            raise NoConvergence("singular")
        dz = (m22 * g1 - m12 * g2) / det
        dc = (m11 * g2 - m21 * g1) / det
        z, c = z - dz, c - dc
        if abs(dc) < max(TOL * scale, FLOOR) and abs(dz) < 1e-6:
            return z, c
    raise NoConvergence("lambda solve")

def dc_dlambda(z, c, P):
    """dc/dlambda by implicit differentiation of the two periodic equations."""
    _, a, b, d, e = jet(z, c, P)
    return 1 / (e + d * (-b / (a - 1)))

def centre(guess, P, scale):
    """Newton on f_c^P(0)=0, with its exact period checked."""
    c = guess
    for _ in range(60):
        z, dz = orbit0(c, P)
        if dz == 0:
            raise NoConvergence("flat")
        step = z / dz
        c -= step
        if abs(step) < max(TOL * scale, FLOOR):
            return c
    raise NoConvergence("centre")

def exact_period(c, scale):
    """Smallest n with f_c^n(0) closest to zero, up to a tight tolerance."""
    z, deriv = 0j, 0j
    n = 0
    while n < MAX_PERIOD:
        deriv, z = 2 * z * deriv + 1, z * z + c
        n += 1
        if deriv != 0 and abs(z / deriv) < 1e-3 * scale:
            return n
    return None

def walk(c0, P, target, scale, steps=16):
    """Continue from the centre (lambda=0) along a ray to lambda=target."""
    z, c = 0j, c0
    for k in range(1, steps + 1):
        z, c = solve_lambda(target * k / steps, z, c, P, scale)
    return z, c

def boundary_coefficients(c0, P, radius):
    """Taylor coefficients of c(lambda), from exact points on |lambda|=1."""
    theta = 2 * pi * 0.5 / N_BOUNDARY
    z, c = walk(c0, P, cmath.exp(1j * theta), radius)
    samples = []
    for j in range(N_BOUNDARY):
        t = 2 * pi * (j + 0.5) / N_BOUNDARY
        z, c = solve_lambda(cmath.exp(1j * t), z, c, P, radius)
        samples.append(c)
    coeffs = []
    for k in range(1, N_COEFF + 1):
        s = sum(samples[j] * cmath.exp(-1j * k * 2 * pi * (j + 0.5) / N_BOUNDARY)
                for j in range(N_BOUNDARY)) / N_BOUNDARY
        coeffs.append(s)
    resid = 0.0
    for j, cj in enumerate(samples):
        t = 2 * pi * (j + 0.5) / N_BOUNDARY
        rec = c0 + sum(a * cmath.exp(1j * (k + 1) * t) for k, a in enumerate(coeffs))
        resid = max(resid, abs(rec - cj))
    return coeffs, resid / radius

def grow(parent, p, q):
    """Find the p/q satellite of parent. Returns a verified bud or raises."""
    P = parent["period"] * q
    if P > MAX_PERIOD:
        raise NoConvergence("period limit")
    c0, P0, r0 = complex(*parent["c"]), parent["period"], parent["radius"]
    lam = cmath.exp(2j * pi * p / q)
    z_root, c_root = walk(c0, P0, lam, r0, steps=24)
    d = dc_dlambda(z_root, c_root, P0)
    predicted = abs(d) / q ** 2
    if predicted < MIN_RADIUS:
        raise NoConvergence("below precision floor")
    normal = d * lam / abs(d)
    last = "no attempt"
    for factor in (1.0, 0.7, 1.4, 0.5, 2.0, 0.3, 3.0):
        try:
            cc = centre(c_root + normal * predicted * factor, P, predicted)
            if exact_period(cc, predicted) != P:
                last = "wrong period"
                continue
            _, a, b, d2, e = jet(0j, cc, P)
            radius = abs(1 / (e + d2 * b))
            # The bud must attach at the parent's root: walk almost to lambda=1.
            _, near = walk(cc, P, 0.97 + 0j, radius, steps=12)
            if abs(near - c_root) > 0.2 * radius:
                last = "attached elsewhere"
                continue
            coeffs, resid = boundary_coefficients(cc, P, radius)
            return {
                "id": None, "parent": parent["id"], "p": p, "q": q, "period": P,
                "depth": parent["depth"] + 1, "c": [cc.real, cc.imag],
                "root": [c_root.real, c_root.imag], "radius": radius,
                "predicted": predicted, "surprise": math.log(radius / predicted),
                "coeffs": [[float("%.5g" % a.real), float("%.5g" % a.imag)] for a in coeffs],
                "resid": float("%.3g" % resid),
            }
        except (NoConvergence, ZeroDivisionError, OverflowError) as err:
            last = str(err)
    raise NoConvergence(last)

def fractions():
    """Reduced p/q in simplest-first order: 1/2, 1/3, 2/3, 1/4, 3/4, 1/5, ..."""
    q = 2
    while True:
        for p in range(1, q):
            if gcd(p, q) == 1:
                yield p, q
        q += 1

class Organism:
    """Growth state. The law it tests is fixed; what it has learned is not.

    surprise = ln(measured radius / law's prediction)
    residual = surprise minus the mean surprise already seen in the same class.
    A pattern that repeats stops being surprising, so growth moves on.
    """
    def __init__(self):
        self.buds, self.failures = [], []
        seed = {"id": 0, "parent": None, "p": 0, "q": 1, "period": 1, "depth": 0,
                "c": [0.0, 0.0], "root": [0.25, 0.0], "radius": 0.5,
                "predicted": 0.5, "surprise": 0.0, "expected": 0.0, "residual": 0.0,
                "coeffs": [[0.5, 0.0], [-0.25, 0.0]] + [[0.0, 0.0]] * 4, "resid": 0.0}
        self.buds.append(seed)
        self.classes = {}
        self.cursors, self.children, self.best, self.active = {}, {}, {}, set()
        self._admit(seed)
        self.best[0] = 1.0  # the seed always gets the first turn

    def _admit(self, bud):
        i = bud["id"]
        self.cursors[i], self.children[i] = fractions(), 0
        self.best[i] = abs(bud["residual"])
        self.active.add(i)

    @staticmethod
    def _class(bud):
        return bud["q"], min(bud["p"], bud["q"] - bud["p"]), min(bud["depth"], 8)

    def _learn(self, bud):
        """Fold a finished bud into the class means and its parent's score."""
        n, total = self.classes.get(self._class(bud), (0, 0.0))
        self.classes[self._class(bud)] = (n + 1, total + bud["surprise"])
        parent = bud["parent"]
        self.best[parent] = max(self.best[parent], abs(bud["residual"]))

    def score(self, i):
        return (self.best[i] + 1e-12) / (1 + self.children[i])

    def replay(self, bud):
        """Restore a stored bud without recomputing its geometry."""
        parent = bud["parent"]
        while next(self.cursors[parent]) != (bud["p"], bud["q"]):
            self.children[parent] += 1
        self.children[parent] += 1
        bud = dict(bud)
        self.buds.append(bud)
        self._admit(bud)
        self._learn(bud)

    def replay_failure(self, f):
        i = f["parent"]
        while next(self.cursors[i]) != (f["p"], f["q"]):
            self.children[i] += 1
        self.children[i] += 1
        self.failures.append(f)
        if f["why"] == "period limit" or "floor" in f["why"]:
            self.active.discard(i)

    def step(self):
        """Grow one bud where the math has most surprised the organism."""
        while True:
            if not self.active:
                raise RuntimeError("nothing left to grow")
            i = min(self.active, key=lambda k: (-self.score(k), k))
            parent = self.buds[i]
            p, q = next(self.cursors[i])
            self.children[i] += 1
            try:
                bud = grow(parent, p, q)
            except NoConvergence as err:
                self.failures.append({"after": len(self.buds), "parent": i, "p": p, "q": q,
                                      "why": str(err)})
                if str(err) == "period limit" or "floor" in str(err):
                    self.active.discard(i)  # later fractions are longer and smaller
                continue
            bud["id"] = len(self.buds)
            n, total = self.classes.get(self._class(bud), (0, 0.0))
            bud["expected"] = total / n if n else 0.0
            bud["residual"] = bud["surprise"] - bud["expected"]
            self.buds.append(bud)
            self._admit(bud)
            self._learn(bud)
            return bud

def fingerprint(buds):
    text = json.dumps(buds, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()
