# Gauge G5: clipped activation-frame learning

**Protocol:** [GAUGE_G5_PREREGISTRATION.md](../../GAUGE_G5_PREREGISTRATION.md). This document discloses the seed-8 **exploratory** tuning and instability before the held-out seeds were run. G5's executable was committed as 39ed09e **before** running seeds 10/11. **Source:** [g5_frame.py](../../experiments/g5_frame.py), [144 local correctness checks](../../tests/test_g5_frame.py).

## All three precommitted hypotheses held on fresh seeds 10 and 11

G5 uses per-neuron preactivation RMS as a coordinate frame to precondition an additive gradient update, and clips the global frame-gradient norm at 1.0. Learning rate 0.05, 150 identical 64-example batches, width64, 8-layer plain and 24-layer residual ReLU networks, sklearn bundled digits.

**H1, gauge equivariance:** all four model pairs stayed equivalent at seven checkpoints across 150 updates. Maximum absolute logit difference across all runs was **2.33e-12**; maximum normalized parameter gauge-coordinate discrepancy **9.52e-14**. First-batch frame-gradient norm difference at most **3.55e-15**. All tests of loss equality and accuracy equality passed.

**H2, zero-bias escape:** initial zero-valued biases became nonzero at step 1. Counts: 499 (plain seed10), 1321 (residual seed10), 490 (plain seed11), 1316 (residual seed11). No biases were seeded artificially.

**H3, plain-network improvement over G4:** both plain models exceeded the precommitted **+20 percentage-point** test-accuracy improvement threshold, with the exact same models, batches, and steps. The improvement was **+57.4 and +61.7 percentage points**. No model or seed omitted.

## Complete held-out summary

| Architecture | Seed | Train loss: start → end | G4 log-step test accuracy | G5 frame-step test accuracy | G5 minus G4 |
|---|---:|---|---:|---:|---:|
| plain ReLU depth8 | 10 | 2.303 → 0.663 | 30.7% | **88.2%** | **+57.4 pp** |
| plain ReLU depth8 | 11 | 2.304 → 0.468 | 21.4% | **83.1%** | **+61.7 pp** |
| residual ReLU depth24 | 10 | 4.525 → 0.363 | 81.4% | **92.2%** | +10.8 pp |
| residual ReLU depth24 | 11 | 7.123 → 0.354 | 85.4% | **88.9%** | +3.5 pp |

The G5 versus G4 residual differences are **descriptive only**, not preregistered hypotheses. The frame method still has a strict positive-anchor requirement and is not validated on all datasets, architectures or scale choices. It should not be represented as state-of-the-art optimization.

## Important failure results retained

The exploratory seed-8 sweep tried cap 0.25 or 1.0 and eta 0.01, 0.05, 0.1 or 0.25, along with an unclipped frame variant. **At eta 0.1 with cap 1.0 both architectures diverged** (plain loss about 12.8, residual loss about 317.8, gross loss of gauge closeness); eta 0.25 was much worse. Several unprotected updates overflowed. The selected cap=1 and eta=0.05 came from that exploratory sweep; the new seeds 10/11 were therefore crucial for a legitimately separate confirmation. Future tests must investigate the stability region.

## Tests and reproducibility

- 144 local synthetic covariance/negative-control tests passed, including signed residual branches, zero-weight and bias movement, invalid clip/eta and exact 0-rate preservation.
- Held-out result rerun from scratch generated **byte-identical JSON**; SHA-256 `f5a861fb11b0bdc5ad5b34990f2bdb7e3e6e32d6bb77cf48740d9ea72a5cd4f3` using `OPENBLAS_NUM_THREADS=1`.
- Code and analysis are committed. The local raw JSON is in the accompanying research archive; `.github/workflows/lapse-gauge-ci.yml` is configured to regenerate and upload raw held-out JSON from a GitHub runner.
- Current evidence establishes equivariance and encouraging small-network learning under these chosen experimental settings, **not** superiority over SGD, Adam, Path-SGD or modern training optimizers. Direct baselines, many more seeds and larger datasets are necessary.

## Literature
Neyshabur et al. (2015), [Path-SGD](https://papers.neurips.cc/paper_files/paper/2015/file/eaa32c96f620053cf442ad32258076b9-Paper.pdf); Gonon et al. (ICML 2025), [invariant path-metrics](https://proceedings.mlr.press/v267/gonon25a.html); Lebeurrier et al. (ICML 2026), [path-conditioned training](https://proceedings.mlr.press/v306/lebeurrier26a.html).
