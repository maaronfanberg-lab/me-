# Gauge G1: function-preserving ReLU rescalings versus lapse

**Pre-registration, 2026-10-28.** This study is independent of the numbered experiment series. The protocol and analysis code are committed before the trained-digit study runs. Development unit tests on synthetic arrays are separate from the study.

## Known mathematical symmetry
ReLU(cz)=c ReLU(z) for c>0. This is a known network parameterization symmetry, not a new discovery. See Neyshabur et al., Path-SGD (2015): https://arxiv.org/abs/1506.02617 and Dinh et al., Sharp Minima Can Generalize for Deep Nets (2017): https://proceedings.mlr.press/v70/dinh17b.html.

Residual case: h0=ReLU(W0 x+b0), hi=h(i-1)+alpha Si ReLU(Wi h(i-1)+bi), logits=Wout hlast+bout, with fixed optional signs Si. Transform W0,b0 -> c W0,c b0; each residual block bias bi -> c bi; Wout -> Wout/c, all other weights unchanged. All hidden states become c times their former values; logits, labels and loss are identical. Residual block deltas scale 1/c, while residual block weight gradients stay fixed. Both raw and alpha-corrected lapse profiles scale 1/c. The corrected total tilt changes by -ln(c). The fitted internal log-lapse slope stays constant.

Plain ReLU: W0,b0 -> c W0,c b0 and W1 -> W1/c. Logits remain identical, and first hidden delta and total tilt shift by 1/c and -ln(c), respectively. Depth slope need not remain unchanged.

## Locked study design
- The bundled sklearn digits via lapse.data.digits; train width=64, ReLU residual depth=24 and plain depth=8, each with seeds 0 and 1. SGD lr=0.05, batch=64, 500 updates. Each original network is trained once. All rescalings are copies of its *same checkpoint*.
- The original first 256 training examples are the probe batch. Rescaling factors c = 0.25, 1, 4, 1024. All 16 comparisons are reported.
- Pass criteria in every comparison: max absolute logit difference <1e-9; loss difference <1e-9; classification accuracy exactly equal; |change in T* + ln(c)| <1e-9. Any nonfinite result fails rather than being omitted.
- Residual-only checks: absolute change in fitted depth slope <1e-9; max absolute change in residual-block **weight gradients** <1e-9. Report horizon counts from raw deltas and require at least one changed count despite identical output. Signed residual blocks and plain networks are tested separately on synthetic unit-test inputs.
- Reject tanh inputs to ReLU rescaling methods as a negative control. Report original test accuracy before/after training, but **do not** set an arbitrary minimum accuracy to select cases.

## Precommitted interpretation
If identities hold, lapse tilt and fixed-threshold horizons are parameterization-dependent, not intrinsic observables of the learned predictor function. This does not make lapse useless as an *optimizer-coordinate diagnostic* or invalidate controlled comparisons within a single parameterization. For the uniform residual rescaling, internal log-lapse slope (and thus fitted curvature derived from it) remains invariant while tilt shifts. A finite numerical lapse threshold is not a causal event horizon. Do not claim SGD trajectories remain invariant under coordinate transformations, or that the known ReLU symmetry is a novel result.