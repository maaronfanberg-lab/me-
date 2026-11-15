# Perennial: research note

## Question
Where does a simple size law for Mandelbrot satellite buds fail, once the failures that repeat have been learned?

## The law and its two derivations
For a parent component with multiplier lambda, the p/q child attaches where lambda = exp(2 pi i p/q).
Predicted conformal radius: r = |dc/dlambda at the root| / q^2.

1. Local: near the root the child's multiplier changes q^2 times as fast as the parent's, so dc/dmu = (dc/dlambda) / q^2. `verify.py` measures this at the child's root and compares it with the prediction.
2. Exact cases: the period 2 disc gives 1/4 from the main cardioid formula. The empirical form sin(pi p/q)/q^2 on the main cardioid is the same expression, since |dc/dlambda| = sin(pi p/q) there.

The derivative relation is checked numerically here. It was not located in a primary paper in the form used, so it is treated as a tested working law, which is the point of the piece.

## Related sources
- Levin, "Multipliers of periodic orbits of quadratic polynomials and the parameter plane", Israel J. Math. (2009).
- arXiv math/0702011 gives a p/q-limb size bound of O(4^n/p) and does not state this law.
- "An optimal Yoccoz inequality for near-parabolic quadratic polynomials", arXiv 2103.03211.

## Growth rule
surprise = ln(measured / predicted). residual = surprise minus the mean surprise already seen in the same class (q, min(p, q-p), depth capped at 8).
A bud's score is the largest residual among itself and its children, divided by 1 + its children. The highest score grows its next simplest fraction.

## Limits, stated plainly
- The rule is deterministic, so the calendar is pacing, not a compute requirement.
- Double precision sets a floor: radius 1e-8 and period 4096. Buds beyond it are logged as failures and their parent retires.
- Rings and spokes are true curves of the stored multiplier map, within the `resid` value stored per bud.

## Validation
`verify.py` limits are in the file and run before each daily commit.
