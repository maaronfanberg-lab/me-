# G11 analysis: larger float32 models do not amortize PathCond at the chosen accuracy targets

**Date 2026-10-28.** **Frozen protocol:** [GAUGE_G11_PREREGISTRATION.md](../../GAUGE_G11_PREREGISTRATION.md). **Executable:** [g11_amortization.py](../../experiments/g11_amortization.py). Original upstream PathCond installed unchanged at **535b202e3476c64d5e7e9ec5e817344fb5cfd787**. This is a larger-model follow-up to G10, not a claim about full-scale deep learning.

## Chain of custody and software audit

- G11 protocol committed before evaluating seeds120–124, on its separate branch. The initial smoke-only GitHub Actions [run 40801254704](https://github.com/maaronfanberg-lab/me-/actions/runs/40801254704) **FAILED** before target training, because the original upstream `grad_path_norm` constructs a default-dtype input; the caller's default was float64 while the model was float32. All failures were on reserved software-debugging seed119. The failure and the narrowly scoped fix were appended to the preregistration **before** target trials.
- The corrected caller temporarily sets PyTorch's default dtype to float32 around the **unchanged** original `rescaling_path_cond` call and restores the previous setting. This change does not affect model architecture, data, hyperparameters or target seeds.
- Independent GitHub Actions **[run 40801412356](https://github.com/maaronfanberg-lab/me-/actions/runs/40801412356)**: **SUCCESS**, including all eight reserved seed119 smoke runs and every target run. Complete GitHub Actions artifact **`lapse-g11-full-results`**, artifact id **12865932402**, downloaded and inspected. Its `ci_full.json` SHA256 is **`0b5379b4f1ee70781e68ffa609bf72c1d9992e6a4bcca662aa567e6c060b9cfa`**.
- All **40 paired comparisons / 80 training trajectories** completed 600 updates without numerical failure. No target seeds excluded or retried.

## Frozen hypothesis decisions

| Hypothesis | Locked threshold | Actual outcome | Decision |
|---|---|---|---|
| **H1: lower computation time to target** | PathCond faster in >=3/4 cells, both cross >=4/5 | **0/4** | **FAIL** |
| **H2: gauge robustness** | lower terminal gauge logit mismatch in >=3/4 cells | **3/4** | PASS |
| **H3: final test accuracy noninferiority** | within 1 percentage point of Adam in >=3/4 cells | **4/4** | PASS |
| **H4: initial function preservation** | all 40 native-float32 PathCond gauges <1e-3 | **40/40** | PASS |

Crucially, success in GitHub Actions signifies a completed **software execution**, not confirmation of all **scientific predictions**.

## Primary runtime result: median compute time to validation-accuracy target

Target = 95% validation accuracy on digits and 96% on synthetic circles. Validation was sampled every ten updates. Reported CPU time is **cumulative preprocessing plus minibatch training computation**, excluding shared data creation and validation-scoring overhead. A missing crossing is right-censored, not assigned a fabricated crossing time.

| Task | Width/depth | Adam crossings | PathCond crossings | Adam median sec | PathCond median sec | Ratio PathCond/Adam | Adam median updates | PathCond median updates |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| digits | 64/6 | 4/5 | 5/5 | **0.0578** | 0.2663 | **4.60×** | 65 | 60 |
| digits | 128/12 | 5/5 | 5/5 | **0.2091** | 1.0634 | **5.09×** | 80 | 80 |
| large circle | 64/6 | 5/5 | 5/5 | **0.0515** | 0.2479 | **4.81×** | 60 | 60 |
| large circle | 128/12 | 5/5 | 5/5 | **0.1254** | 0.9562 | **7.63×** | 50 | 40 |

A normal-coordinate Adam digit 64/6 run never reached 95% within 600 updates; it was **counted as censored**, not erased. The paired-run performance measurements are tiny CPU intervals on one hosted runner and have real timing noise. The large model is still small by current standards. The target is typically reached by 40–80 updates, so the 600-update *maximum* budget did not ensure preprocessing amortization for a relatively easy accuracy target. Do not generalize to models trained for hours.

Median original PathCond preprocessing alone was approximately **0.198–0.204 seconds** for width64 and **0.845–0.851 seconds** for width128, already exceeding the corresponding Adam time to target. Thus reducing learning steps by 10–20% on some tasks was not enough to offset setup.

## Fixed-step test outcomes (mean across all five untouched seeds)

| Task | Width/depth | Adam accuracy at step600 | PathCond accuracy | Adam test CE at step600 | PathCond test CE |
|---|---|---:|---:|---:|---:|
| digits | 64/6 | 96.67% | **97.06%** | 0.2582 | **0.2499** |
| digits | 128/12 | 94.39% | **96.56%** | 0.7157 | **0.5054** |
| large circle | 64/6 | **98.51%** | 98.21% | **0.0337** | 0.0422 |
| large circle | 128/12 | **98.21%** | 97.86% | **0.0399** | 0.0490 |

**Important nuance:** PathCond improved *fixed-step* test accuracy/CE in both **digit** cells and reduced digits depth12 test CE noticeably, even though time to target was slower in every cell. It lost on the two circle cells. No general predictive superiority is claimed.

## Gauge sensitivity after 600 updates

The gauge test starts from equivalent positive neuronwise rescalings of the same original function; on the PathCond arm, the *unchanged official upstream* conditioner is invoked independently from each starting coordinate.

| Task | Width/depth | Adam mean max logit gap | PathCond mean max logit gap | PathCond better? |
|---|---|---:|---:|---|
| digits | 64/6 | 99.840 | **19.589** | Yes |
| digits | 128/12 | 595.226 | **331.536** | Yes |
| large circle | 64/6 | 9.677 | **5.039** | Yes |
| large circle | 128/12 | **59.535** | 83.053 | **No** |

H2 passed 3/4. The exception on the widest deep circle model is scientifically important and refutes any claim that official PathCond always improves robustness. These differences are in raw **logit units**, not standardized divergences or accuracy differences, and may be distorted by logit scale across architectures. Neither Adam nor PathCond+Adam is gauge-equivariant here.

## Interpretation

At this modest scale, even with wider 128-unit, 12-layer networks and an 8,192-example synthetic problem, one-time upstream conditioning cost continues to dominate **time to a relatively early accuracy threshold**. Therefore G10's negative cost finding **survived** this increase in model size. This is not proof that PathCond cannot amortize on much larger / longer GPU workloads; the original authors study other settings and architectures.

Positive and negative findings coexist: PathCond improved digit fixed-step accuracy and gauge sensitivity on three of four models while failing to be faster at the specified validation targets, and lost gauge robustness on deep circle. Both outcomes are part of the record.

Scope: CPU single thread, 5 seeds per cell, only two datasets (digits stays 1,797 samples; circles expanded to 8,192), native float32, 600 updates, Adam lr0.003 selected in prior work. No statistical confidence intervals, no GPU/CIFAR-10, no residual PathCond equivalence claim. Measuring a more difficult target, true target-hitting survival curves, normalized output-distance metrics, and a larger, longer workload are candidates for **separate preregistered** studies, not post-hoc changes to G11.

## Reproduction

```bash
cd experiments/lapse-meter
# Install pinned dependencies and exact original PathCond as documented in:
# .github/workflows/lapse-g11-amortization.yml
python experiments/g11_amortization.py --smoke
python experiments/g11_amortization.py results/g11/full.json
```

The clean-run artifact [GitHub Actions run 40801412356](https://github.com/maaronfanberg-lab/me-/actions/runs/40801412356) preserves all 40 individual records, each gauge's validation trace, step100/300/600 test checkpoints, per-network compute times, preprocessing errors, and the censored crossing.
