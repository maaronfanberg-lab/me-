# Gauge G3: calibrated parameter log-scale pressure

**Status:** the preregistered 16 small-perturbation cells all passed; 16 larger-perturbation stress cells are exploratory and reported. Code and protocol were committed before seeds 4–5 were trained and checked. Source: [g3_pressure_calibration.py](../../experiments/g3_pressure_calibration.py); [GAUGE_G3_PREREGISTRATION.md](../../GAUGE_G3_PREREGISTRATION.md).

## Purpose and prior art

The score `P_l = sqrt(sum((W_l*dL/dW_l)^2) + sum((b_l*dL/db_l)^2))` aggregates existing `weight × gradient` connection sensitivities, related to the established SNIP pruning criterion (Lee et al., ICLR 2019). It is not a new algorithm. The G2 test showed this score is invariant under positive diagonal ReLU neuron rescalings. G3 asks whether it actually predicts *finite* loss response to controlled random proportional parameter changes.

Perturbation: `W_l' = W_l*exp(eps*xi_W)`, `b_l' = b_l*exp(eps*xi_b)`, each `xi` independently +1 or -1. First-order prediction: `Delta L_hat = eps * (sum(W_l*G_W_l*xi_W) + sum(b_l*G_b_l*xi_b))`. Under independent Rademacher signs, its theoretical standard deviation is `eps*P_l`. The approximation to finite `Delta L` is only first-order; it can degrade for larger eps.

## Protocol and outcomes

Bundled handwritten digits, 500 SGD steps, width 64, learning rate 0.05, plain ReLU depth 8 and residual ReLU depth 24, independent seeds 4 and 5. Four layers per network (first, middle, last hidden, output). 64 independent perturbation directions per cell. Same probe batch of 256 examples. Two epsilons, 0.001 (confirmatory) and 0.01 (exploratory). Each loss response computed on both the original model and its nonuniform neuronwise G2-gauge equivalent. No excluded layers or runs.

| Metric across 16 cells each | eps 0.001 (confirmatory) | eps 0.01 (exploratory) |
|---|---:|---:|
| random perturbation directions | 1,024 | 1,024 |
| actual-vs-linearized loss response correlation | 0.9976–0.999999 | 0.9876–0.9997 |
| RMS approximation error / RMS predicted change | 0.0021–0.0791 | 0.0349–0.3190 |
| observed SD(loss change) / (eps × P) | 0.901–1.169 | 0.892–1.154 |
| max absolute difference in paired gauge loss changes | 4.86e-17 | 4.86e-17 |

**Preregistered decision: 16/16 small-epsilon cells passed** all four criteria: gauge loss-change difference <1e-9, correlation >0.98, relative RMS error <0.1 and SD ratio in (0.65,1.35). Larger epsilon was not part of the primary pass rule; its greater approximation error illustrates the limit of first-order sensitivity.

## Interpretation and limitations

The gauge-invariance of the finite loss changes follows from positive diagonal scaling commuting with an entrywise proportional parameter perturbation. The Rademacher variance identity follows algebraically from independent signs. The empirical contribution is a **calibration and implementation test**, not the discovery of a novel law. The score does predict the local distributional scale of loss changes from multiplicative parameter perturbations in the tested small networks. It does **not** predict loss changes under ordinary additive SGD, Adam, model generalization, or whether a layer is actually learning. The directionwise first-order approximation worsens as eps grows.

## Reproduce

```bash
cd experiments/lapse-meter
OPENBLAS_NUM_THREADS=1 python tests/test_g2_gauge_invariants.py
OPENBLAS_NUM_THREADS=1 python experiments/g3_pressure_calibration.py results/g3/results.json
```

Requires NumPy and scikit-learn. The full raw G3 JSON was generated locally; the summary and executable are committed here. No claim of CI verification on this branch is made.

## Attribution
- Lee, Ajanthan & Torr, [SNIP](https://arxiv.org/abs/1810.02340), ICLR 2019.
- Neyshabur et al., [Path-SGD](https://arxiv.org/abs/1506.02617), NeurIPS 2015.
