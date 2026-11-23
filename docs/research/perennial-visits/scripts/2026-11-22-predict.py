# Preregistered test (rule formed on s<=8): disc bud s/q (period D=2q) and cardioid bud
# theta = 1/2 - s/(2N) (period N) share the same limiting surprise iff (D-N)/s is odd.
import sys
from math import gcd
import numpy as np
sys.path.insert(0, '.')
import engine as E
seed = E.Organism().buds[0]
disc = E.grow(seed, 1, 2); disc['id'] = 1
def lim(par, fr, ms):
    pts = []
    for m in ms:
        a, b = fr(m)
        if gcd(a, b) != 1: return None
        pts.append((b, E.grow(par, a, b)['surprise']))
    qs = np.array([x[0] for x in pts], float); ss = np.array([x[1] for x in pts])
    A = np.vstack([np.ones_like(qs), 1/qs, 1/qs**2]).T
    L1 = np.linalg.solve(A[-3:], ss[-3:])[0]; L0 = np.linalg.solve(A[:3], ss[:3])[0]
    return L1, abs(L1 - L0)
worst_pred, best_wrong, rows = 0, 9, 0
for s in [int(x) for x in sys.argv[1].split(',')]:
    D = {}
    for r in range(1, s):
        if gcd(r, s) != 1: continue
        ms = [(n // s) * s + r for n in (240, 480, 960, 1920)]
        D[r] = lim(disc, lambda q: (s, q), ms)
    for rN in range(2 * s):
        if (rN - s) % 2: continue
        Ns = [(n // (2 * s)) * 2 * s + rN for n in (480, 960, 1920, 3840)]
        if max(Ns) > E.MAX_PERIOD: Ns = [(n // (2 * s)) * 2 * s + rN for n in (300, 600, 1200, 2400)]
        c = lim(seed, lambda N: ((N - s) // 2, N), Ns)
        if c is None: continue
        r_pred = ((rN + s) // 2) % s          # q = (N+s)/2 mod s
        r_alt = (rN // 2) % s if rN % 2 == 0 else ((rN * pow(2, -1, s)) % s if s % 2 else None)  # no half shift
        d = D.get(r_pred)
        diff = abs(c[0] - d[0])
        worst_pred = max(worst_pred, diff)
        others = [abs(c[0] - v[0]) for r, v in D.items() if r != r_pred]
        if others: best_wrong = min(best_wrong, min(others))
        rows += 1
        print('s=%2d N=%2d mod %2d  card %.6f(+-%.0e)  disc r=%2d %.6f(+-%.0e)  |diff| %.1e  nearest other disc %.1e'
              % (s, rN, 2 * s, c[0], c[1], r_pred, d[0], d[1], diff, min(others) if others else float('nan')), flush=True)
print('pairs', rows, 'worst predicted-pair diff %.2e' % worst_pred, 'closest non-predicted %.2e' % best_wrong)
