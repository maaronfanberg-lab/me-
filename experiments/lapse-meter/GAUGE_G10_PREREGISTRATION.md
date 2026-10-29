# G10 preregistration: time-to-validation-target and native float32 robustness

**Date:** 2026-10-28. This protocol was committed before any G10 target-seed evaluations. Parent G9 results are unchanged. The scope is a fixed, reproducible CPU screening benchmark, not a GPU or large-model claim.

## Background
G9 (10 fresh seeds, 300 steps) showed that PathCond+Adam often improved 100-step test cross entropy, whereas ordinary Adam was better by 300 steps in three of four small cells. G8 showed that PathCond's released float32 cast can break exact initial-function preservation on float64 models. G10 asks whether early gains repay preprocessing cost and whether the behavior survives **native float32** models.

## Fixed datasets, models, seeds
- sklearn handwritten digits and deterministic concentric-circle classification exactly as G6/G7/G9. Stratified 60/20/20 splits, train-only StandardScaler. Plain ReLU MLP, width32, hidden depths 3/6; no residual models.
- **Target seeds 90, 91, 92, 93, 94** (untouched by G1–G9). Smoke-check on seed79 only. Same seed's initial NumPy weights, train/test split and index schedule across all arms.
- Native torch.float32 and torch.float64 CPU, torch.set_num_threads(1), pinned PyTorch CPU 2.5.1, NumPy 2.3.5, sklearn 1.8.0, upstream PathCond pinned original commit 535b202e3476c64d5e7e9ec5e817344fb5cfd787.
- Per dtype: **Adam** and **original PathCond + Adam**. In float64 only, also test **float64-factor diagnostic PathCond + Adam**, calling unchanged original BZ construction primitives but not casting the factor tensor to float32. It is NOT the released method. Total 5 dtype/method arms.
- Each seed/task/depth/arm starts in *both* identity and equivalent per-neuron positive rescaled gauges (factors in 1/8..8, independently per plain hidden layer), with separate PathCond preprocessing for each gauge as in G7 and G9. 2 tasks ×2 depths ×5 seeds ×5 arms ×2 gauges = **200 training trajectories**, 100 matched pairs. Random mini-batches with replacement (`default_rng(10000+seed)`, batch64).
- All arms use **Adam LR=0.003**, fixed from prior G7 validation-only tuning, beta=(.9,.999), eps1e-8, zero weight decay. Train for **300 steps**, no early stopping and no test-driven tuning.
- Monitor **validation accuracy** at step0 and every 10 steps (not selected upon, only measured). Targets are **90%** on digits, **90%** on circles. Record first crossing and cumulative *training computation time* (preprocessing + forward/backprop/optimizer steps); exclude shared validation-scoring overhead from this cumulative clock. Include model preprocessing overhead. Runtime cost of data loading/model initialization and diagnostic evaluation is reported separately and excluded from time-to-target. Time measurements are inherently hardware-specific.
- Report test cross entropy and accuracy at fixed step100 and 300, never use test labels to choose target or rate. Record validation crossings for **both gauges** and all trials, all failures, and numerical precision at the beginning/end of training.
- Time-to-target for never-crossing runs is **right-censored** at 300 steps, not assigned a fabricated time. Report crossing count per cell and time distribution among crossers; when comparing wins, no uncrossed run can be silently discarded.

## Locked scientific hypotheses
- **H1 precision/integration:** all 40 float64 diagnostic preconditioning transforms (two gauges ×2 tasks ×2 depths ×5 seeds) preserve model outputs within max abs 1e-10 on first 128 train examples. Official float32 preconditioning also preserves within 1e-4 on all 40 float32 networks. If any nonfinite or failed transformation occurs, H1 fails.
- **H2 time-to-target (normal gauge, float32):** original PathCond+Adam has lower **median time to 90% validation accuracy** than Adam in **at least 3 of 4** task×depth cells, but *only* if both methods reach the target on >=4/5 seeds in each passing cell. Otherwise that cell fails. Include all 5 seeds. This is a prospective directional prediction, not a theorem.
- **H3 float32 gauge robustness:** original PathCond+Adam has smaller **mean maximum absolute test-logit gap after 300 steps** between two equivalent starts than Adam in **at least 3/4** cells. Any failed/nonfinite pair counts as infinity and prevents a win if PathCond fails. No claim of exact function equivariance.
- **H4 final accuracy noninferiority:** in >=3/4 cells, PathCond+Adam mean native float32 test accuracy at 300 steps is at most **1 percentage point below** native float32 Adam. This does not measure statistical significance.
- **Secondary:** float64 official versus diagnostic factor conversion, time-to-target under stressed gauges and rate of censored runs, difference from matched-update ranking, and the impact of CPU preprocessing overhead. Record all counts, individual results and per-run timing. A green CI run only proves software completed, not that scientific hypotheses succeeded.

## Audit and limitations
Do not change thresholds, seeds, targets, rates or model architecture after target evaluation. If a code-level defect is found after any target-seed run, preserve the original outputs, fix explicitly and use new independent seeds for fresh confirmation. H2 time-to-target is sampled every 10 steps and uses noisy wall-clock readings from one runner; it is a screening study, not a formal performance engineering paper. Only small offline tasks and plain ReLU networks. No extrapolation to modern CNNs, ResNets, transformers or GPUs.

Original PathCond: https://github.com/Artim436/pathcond (ICML 2026, https://proceedings.mlr.press/v306/lebeurrier26a.html).
