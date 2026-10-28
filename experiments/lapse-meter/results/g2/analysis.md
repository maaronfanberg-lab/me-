# Gauge G2: neuronwise rescaling, 72 comparisons

**Status:** passes all registered invariance assertions. Separate the exploratory *development* samples (seeds 0,1) from **frozen-code confirmation** (held-out seeds 2,3). See [GAUGE_G2_PREREGISTRATION.md](../../GAUGE_G2_PREREGISTRATION.md), including its timing correction. The G2 implementation was committed (05c36c0) and synthetic tests committed (b88d9ac) **before** the seeds 2,3 confirmation.

## Quantities, scoped claims

- A_l = RMS_examples ||h_l ⊙ (dL/dh_l)||_2 (post-activation hidden state). Relative work profile compares this A_l to the last hidden layer; it measures sensitivity to proportional activation changes, **not time dilation or speed of weight updates**.
- P_l = sqrt(||W_l ⊙ grad_W_l||_F² + ||b_l ⊙ grad_b_l||²). This is a *layer aggregation of known weight-times-gradient sensitivity*, closely related to SNIP, not a novel estimator. It measures response to fractional changes in parameters, **not SGD motion**.
- On any *positive diagonal gauge* D_l, activations h_l -> D_l h_l and their dual gradients g_l -> D_l^-1 g_l; entrywise products are unchanged. Parameter weight/bias gradients transform inversely to the parameters. Residual networks require the same diagonal D at every block because of the identity skip; plain ReLU networks may use different D per hidden layer.

## Design

Two 64-wide architectures: residual ReLU 24 hidden layers, plain ReLU 8 hidden layers. Bundled sklearn digits; batch size 64, SGD learning rate 0.05, probe batch first 256 training examples. Seeds 0,1 exploratory and seeds 2,3 confirmatory; 0,250,500 update checkpoints. Gauges: identity; uniform D=4; nonuniform neuronwise D with entries exp(linspace(-ln32,ln32,64)), deterministically permuted (per hidden layer for plain). **4 seeds x 2 architectures x 3 checkpoints x 3 gauges = 72 comparisons**, no dropped runs.

| Metric | Exploratory seeds 0,1: 36 comparisons | Held-out seeds 2,3: 36 comparisons |
|---|---:|---:|
| maximum absolute logit error | 3.20e-14 | 2.13e-14 |
| maximum absolute loss error | 8.88e-16 | 5.55e-17 |
| maximum relative activation-work component error | 8.83e-16 | 7.17e-16 |
| maximum relative parameter-pressure component error | 1.47e-15 | 1.85e-15 |
| maximum relative work-profile error | 4.76e-16 | 7.54e-16 |
| raw tilt change under neuronwise gauge (range) | +1.81 to +2.49 | +1.71 to +2.31 |
| raw fitted slope change under neuronwise gauge (range) | -0.062 to +0.014 | -0.072 to +0.056 |
| changes to raw 0.01-threshold horizon count | 0 | 0 |

**All 72 comparisons passed** the predeclared primary invariance tests (with stronger relative-error normalization than required). Raw lapse tilt changes despite virtually identical logits, so it does not provide the same invariance. Unlike the much larger uniform gauge in G1, this range of nonuniform scaling did **not** move any network across the 0.01 raw horizon threshold. That is a null observation, reported rather than forced.

At step 500, held-out test accuracies: residual seed2 96.47%, seed3 96.98%; plain seed2 95.21%, seed3 93.20%. Exploratory seeds: residual seed0 97.48%, seed1 96.22%; plain seed0 97.23%, seed1 95.47%.

The tests include 21 synthetic/negative-control/finite-difference checks: explicitly broken output compensation changes logits; tanh scaling is rejected; residual blocks refuse inconsistent per-block rescalings; numeric finite-difference activation and weight gradients agree with analytical gradients.

## What this does not establish

The A/P invariances are largely **algebraic consequences** of the scaling group, not surprising statistical discoveries. This work verifies that the implementation respects them and that they survive two architectures, four seeds, and multiple training stages. It has not established whether the metrics predict training success, robust generalization, actual SGD weight motion, or anything under arbitrary function-equivalent transformations. The 0.01 cutoff remains arbitrary even if applied to an invariant sensitivity measure. The activation-work profile is not necessarily comparable across tasks and outputs without calibration.

## Reproduction

From the repository's `experiments/lapse-meter` folder, with `numpy` and `scikit-learn`:

```bash
OPENBLAS_NUM_THREADS=1 python tests/test_g2_gauge_invariants.py
OPENBLAS_NUM_THREADS=1 python experiments/g2_gauge_invariants.py results/g2/dev.json 0 1
OPENBLAS_NUM_THREADS=1 python experiments/g2_gauge_invariants.py results/g2/confirmation.json 2 3
```

The local full raw JSON outputs are separately available as artifacts in the original research session. This repository records reproducible code and full result summary, but the local output JSON files have not been committed to GitHub.

## Literature and attribution
- Neyshabur et al. (NeurIPS 2015), [Path-SGD](https://papers.neurips.cc/paper_files/paper/2015/hash/eaa32c96f620053cf442ad32258076b9-Abstract.html).
- Meng et al. (ICLR 2019), [G-SGD](https://arxiv.org/abs/1802.03713).
- Lee, Ajanthan & Torr (ICLR 2019), [SNIP](https://arxiv.org/abs/1810.02340): connection sensitivity based on a weight-gradient product.
- Liang et al. (AISTATS 2019), [Fisher-Rao metric](https://proceedings.mlr.press/v89/liang19a.html): invariant information-geometric perspective, not identified with A or P here.
