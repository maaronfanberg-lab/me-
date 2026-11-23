import sys, math
from math import gcd
import numpy as np
sys.path.insert(0, '.')
import engine as E
seed = E.Organism().buds[0]
disc = E.grow(seed, 1, 2); disc['id'] = 1
def limit(par, frac_of, base):
    pts = []
    for m in base:
        a, b = frac_of(m)
        g = gcd(a, b); a, b = a//g, b//g
        try:
            s = E.grow(par, a, b)['surprise']; pts.append((m, s))
        except E.NoConvergence: return None
    qs = np.array([x[0] for x in pts], float); ss = np.array([x[1] for x in pts])
    A = np.vstack([np.ones_like(qs), 1/qs, 1/qs**2]).T
    L1 = np.linalg.solve(A[-3:], ss[-3:])[0]; L0 = np.linalg.solve(A[:3], ss[:3])[0]
    return L1, abs(L1-L0), b
P = [int(x) for x in sys.argv[1].split(',')]
for p in P:
    for r in range(2*p):
        if gcd(r, p) != 1 and p > 1: continue
        # base Q ~ 250..2000 with Q = r mod 2p
        base = [ (n//(2*p))*2*p + r for n in (240, 480, 960, 1920) ]
        d = limit(disc, lambda q: (p, q), base) if gcd(p, base[0]) == 1 else None
        c = limit(seed, lambda Q: (Q - p, 2*Q), base)
        f = lambda v: 'n/a' if v is None else '%.6f (+-%.0e, per %d)' % v
        print('p=%d Q=%2d mod %2d   disc p/q: %-32s  card (Q-p)/2Q: %s' % (p, r, 2*p, f(d), f(c)), flush=True)
