# G6A Results: SGD, Adam, and G5 on unfamiliar tasks

**Date:** 2026-10-28. **Frozen preregistration:** [GAUGE_G6A_PREREGISTRATION.md](../../GAUGE_G6A_PREREGISTRATION.md). **Executable:** [g6_benchmark.py](../../experiments/g6_benchmark.py). **Tests:** [test_g6_benchmark.py](../../tests/test_g6_benchmark.py). Study is an adversarial screen of G5, not a validation of its superiority.

## Complete frozen local run

- **108 tuning runs** (three learning-rate candidates per method, two tuning seeds per task/architecture), **90 untouched-seed evaluations** (five seeds 30–34 per task/architecture/method), plus **90 paired neuronwise-gauge trajectory stress tests**.
- 200 updates per run, batch size 64, width 64, plain ReLU depth 8 or residual ReLU depth 24; digits / wine / clean synthetic circle. StandardScaler fitted to the training partition only. The learning-rate grid was fixed and validation selection happened entirely on seeds 20 and 21.
- All **90 untransformed holdout training runs** finished without a numerical failure. There were no tuning-run failures.
- **H2 FAILS:** G5 had lower mean held-out cross-entropy than both SGD and Adam in **0 of 6** task/architecture cells, versus preregistered pass bar 4 of 6.
- **H1 FAILS narrowly:** G5 held equivalent-coordinate trajectories within the strict <1e-7 logit and <1e-9 loss-difference thresholds in **28 of 30** heldout pairs, versus required 30/30. Only the residual circle task failed (seeds 33,34); all G5 gauge pairs retained identical test classification accuracy at all checkpoints. Treat 28/30 as a failure of the locked criterion, **not as success**.

### Held-out results, mean over five seeds

| Task | Architecture | SGD test CE | Adam test CE | G5 test CE | SGD test acc | Adam test acc | G5 test acc |
|---|---|---:|---:|---:|---:|---:|---:|
| digits | plain 8 | 0.3633 | **0.2545** | 0.4917 | 89.8% | **93.7%** | 84.8% |
| digits | residual 24 | 0.1854 | **0.1805** | 0.4454 | 95.8% | **96.7%** | 90.8% |
| wine | plain 8 | **0.1384** | 0.1892 | 0.1458 | 96.7% | 97.2% | 96.7% |
| wine | residual 24 | **0.0555** | 0.0766 | 0.0579 | 97.8% | 98.3% | 96.1% |
| circle | plain 8 | 0.2630 | **0.0347** | 0.1163 | 88.6% | **98.6%** | 95.9% |
| circle | residual 24 | 0.1168 | **0.0425** | 0.2342 | 96.8% | **98.1%** | 91.4% |

All CE values are cross-entropy on the previously unseen test partition, evaluated after the precommitted 200 updates. Wine has only ~36 test cases per seed. The rates were not retuned on these held-out results.

### Coordinate-rescaling stress test

Each evaluation seed was rerun with a function-preserving per-neuron scale spanning 1/8 to 8, same initialization in function space and same mini-batches. Report all 30 pairs per optimizer.

| Method | Pairs passing very strict gauge trajectory rule | Gauge training failures | Maximum finite logit mismatch |
|---|---:|---:|---:|
| SGD | 0 / 30 | **29 / 30** | 129,353.88 |
| Adam | 0 / 30 | 0 / 30 | 73.53 |
| G5 | **28 / 30** | 0 / 30 | 8.60e-7 |

All G5 classification predictions were identical in both gauges despite the two tolerance failures. On residual circles seed 33, the max logit mismatch was 3.65e-7 at step 100 and 8.60e-7 at step 200; test-loss mismatch was 1.08e-8 at step 100 and 2.64e-8 at step 200. On seed 34, logit mismatch reached 1.55e-7 at step 200, loss mismatch 1.61e-9. None of these is a training divergence, but each violates a locked numerical threshold. The G5 coordinate guarantee is algebraic in exact arithmetic; the operational float64 implementation loses exact trajectory matching in two conditions after accumulating roundoff. This benchmark does not establish the mechanism of amplification.

### Compute cost

G5 used **1.08×–1.59×** the median wall time of Adam at equal 200-step budgets (across six cells), and approximately **1.45×–2.29×** that of SGD. Per-model CPU times are stored in the JSON. This is an equal-update / equal-search-grid screen, **not compute-equivalent** benchmarking. Extra frame calculations may be worth the cost if robustness is paramount, but speed/accuracy claims would require matched wall-time comparisons.

### Selected learning rates (mean validation CE on tuning seeds 20,21 only)

| Task | Arch | SGD | Adam | G5 |
|---|---|---:|---:|---:|
| digits | plain | 0.1 | 0.001 | 0.03 |
| digits | residual | 0.1 | 0.003 | 0.05 |
| wine | plain | 0.1 | 0.001 | 0.03 |
| wine | residual | 0.1 | 0.003 | 0.05 |
| circle | plain | 0.1 | 0.001 | 0.05 |
| circle | residual | 0.1 | 0.003 | 0.05 |

## Conclusions, including failures

G5's main empirical distinction is **gauge robustness**, not superior accuracy or test loss. It demonstrably loses on the registered log-loss test against appropriately tuned conventional baselines at this 200-step budget. The G5 strict functional-trajectory prediction also failed on two of 30 circle comparisons under finite precision, despite negligible practical accuracy differences. Both results must remain visible in the project ledger. Do not relax thresholds after looking at outcomes, reweight datasets to turn H2 into a success, or call G5 an improved optimizer in general.

What remains open: wider learning-rate ranges (preregister separately), wall-clock-equated comparisons, 32-bit arithmetic, alternative datasets, effects of residual mean shift, and whether a tested *invariant path optimizer* (rather than G5) yields a better accuracy/robustness tradeoff. Existing literature: [Path-SGD (NeurIPS 2015)](https://proceedings.neurips.cc/paper_files/paper/2015/hash/eaa32c96f620053cf442ad32258076b9-Abstract.html) and [Path-conditioned training (ICML 2026)](https://proceedings.mlr.press/v306/lebeurrier26a.html).

## Reproduction and CI

From `experiments/lapse-meter` with NumPy 2.3.5, scikit-learn 1.8.0, `OPENBLAS_NUM_THREADS=1`:

```bash
python tests/test_g6_benchmark.py
python experiments/g6_benchmark.py results/g6a/results.json
```

The generated raw JSON contains all 108 tuning records, 18 selected configurations, 90 untransformed evaluations and 90 gauge stress tests, including all numerical failures. A separate GitHub Actions workflow (`lapse-g6-benchmark.yml`) regenerates it and publishes the full JSON as an artifact. Do not claim that runner passed until its actual conclusion is verified.
