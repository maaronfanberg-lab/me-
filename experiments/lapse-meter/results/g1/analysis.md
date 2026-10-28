# Gauge G1 results: a counterexample to function-intrinsic total tilt

**Protocol:** [GAUGE_G1_PREREGISTRATION.md](../../GAUGE_G1_PREREGISTRATION.md). **Data:** [gauge.csv](gauge.csv), 16 comparisons. **Implementation:** [g1_gauge.py](../../experiments/g1_gauge.py). Synthetic regression checks: [test_g1_gauge.py](../../tests/test_g1_gauge.py).

## Result
All 16 comparisons passed the preregistered functional-equivalence and tilt identities. Across every cell, maximum absolute logit difference = 0.0, loss difference = 0.0, and classification accuracy difference = 0.0 in the local float64 run. Maximum absolute error in the predicted change `T*' - T* = -ln(c)` = 2.22e-16. For the residual models, maximum absolute residual-block weight-gradient change = 0.0; maximum fitted log-lapse slope difference = 4.86e-17.

Each network was trained from scratch for 500 SGD updates before a *single checkpoint* was copied and rescaled. The transformations require no retraining.

| architecture | seed | test accuracy after training | horizons before | horizons at c=1024 | tilt before | tilt at c=1024 |
|---|---:|---:|---:|---:|---:|---:|
| residual ReLU, depth 24 | 0 | 97.48% | 0 / 23 | 23 / 23 | +0.7685 | -6.1630 |
| residual ReLU, depth 24 | 1 | 96.22% | 0 / 23 | 23 / 23 | +0.7046 | -6.2269 |
| plain ReLU, depth 8 | 0 | 97.23% | 0 / 8 | 1 / 8 | +1.3813 | -5.5502 |
| plain ReLU, depth 8 | 1 | 95.47% | 0 / 8 | 1 / 8 | +1.2688 | -5.6627 |

All four show a tilt change of **-6.9314718056** at scale 1024. Other scales c=0.25 and c=4 shift tilt by +1.3862943611 and -1.3862943611, respectively, also without changing predictions. c=1 is the no-op baseline. All 16 rows are in gauge.csv.

## What this proves and does not prove
Within these implemented one-matrix ReLU architectures, **a total lapse tilt or horizon count is not invariant under function-preserving positive rescalings**. Hence it is not determined by the input-to-output function alone. The residual 'horizon' criterion N<0.01 is a coordinate-dependent threshold rather than a causal or geometric horizon. This is an application of familiar ReLU scaling symmetries rather than a novel theorem.

Under *uniform residual-stream* rescaling, the internal log-lapse slope and thus a curvature derived solely from its slope remain invariant, even as the total tilt shifts. This experiment does not establish an invariant curvature under arbitrary layerwise or neuronwise ReLU rescaling, nor does it claim a rescaled network follows the same future SGD training trajectory. The gradients with respect to block *weights* remain fixed in the residual case, while gradients with respect to block *biases* and other layers may change. Gradient coordinates can still be operationally meaningful for optimization.

The results do not retroactively falsify earlier controlled depth-versus-depth comparisons at the original fixed initialization and architecture. They require the Atlas to label the measure as a **parameterization-dependent gradient diagnostic**, and to show both the raw and alpha-corrected values.

## Validation status and reproducibility
- Local synthetic development tests: 17 checks passed; cover plain, residual, signed residual branches, negative tanh controls, and no-op c=1.
- Trained-digit experiment: 16/16 comparisons passed all assertions.
- The local run used the relevant NumPy MLP operations mirrored from the current repository. A clean CI run directly from the PR branch is still recommended; no GitHub-hosted test run is claimed here.
- Reproduce in an environment with `numpy` and `scikit-learn`: `python tests/test_g1_gauge.py` followed by `python experiments/g1_gauge.py results/g1/gauge.json`.

## Prior art
- Neyshabur, Salakhutdinov & Srebro (2015), [Path-SGD](https://arxiv.org/abs/1506.02617), treats positive-rescaling-invariant optimization in ReLU nets.
- Dinh, Pascanu, Bengio & Bengio (2017), [Sharp Minima Can Generalize For Deep Nets](https://proceedings.mlr.press/v70/dinh17b.html), shows how function-preserving parameter redefinitions can alter ostensibly geometric measurements.
