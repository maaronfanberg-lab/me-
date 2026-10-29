# G10: native float32, time-to-target, and robustness against neuron rescaling

**Protocol:** [GAUGE_G10_PREREGISTRATION.md](../../GAUGE_G10_PREREGISTRATION.md), frozen before all target-seed trials. **Source:** [g10_time_to_target.py](../../experiments/g10_time_to_target.py). **Independent execution:** GitHub Actions [40798278560](https://github.com/maaronfanberg-lab/me-/actions/runs/40798278560), completed **SUCCESS** with clean CPU installation of pinned original PathCond commit 535b202e3476c64d5e7e9ec5e817344fb5cfd787 and PyTorch 2.5.1+cpu. Preflight on seed79 passed. Complete JSON in archived artifact `lapse-g10-full-results`, id **12864572902**. The raw `ci_full.json` SHA256 is **923a1205d6e30ccca4fa0595880c1208d37c16e711209ae11dfa21209dcec31a**.

## Locked decisions, including the failure

- **H1 PASS (80/80):** the published original PathCond preconditioner on **native float32** preserved initial outputs within <1e-4 for **40/40** cases (20 model/seed/task/depth cells ×2 gauges). Maximum error **1.4305115e-6**. The separate precision-only diagnostic on **float64** models preserved initial outputs within <1e-10 in **40/40** cases, worst **3.5527137e-15**. This does not claim float32 is bit-exact or that the double diagnostic is the released method.
- **H2 FAIL (0/4):** official PathCond+Adam did not yield lower median **CPU computation time to first 90% validation accuracy** than Adam in **any** of four native-float32 task/depth cells, versus preregistered pass >=3/4. Every normal-gauge run of both methods crossed the threshold (5/5), so no right-censored cases in those four identity-gauge comparisons. Training-time clock includes PathCond preprocessing and minibatch forward/backprop/update; excludes shared data/model setup and validation-scoring overhead. The target was measured at steps 0,10,...300, not continuously.
- **H3 PASS (4/4):** official float32 PathCond+Adam reduced mean maximum test-logit difference between equivalent starting gauges versus float32 Adam in all four task/depth cells at 300 updates. This is **improved robustness**, NOT exact gauge-equivariant Adam training.
- **H4 PASS (4/4):** official float32 PathCond+Adam mean heldout final test accuracy was within **1 percentage point** of Adam in all four cells (preregistered >=3/4).
- **Software:** all **100 paired runs / 200 trajectories** completed 300 steps with **zero training failures**. Five untouched target seeds90–94, two tasks, plain ReLU hidden depths3/6 width32, fixed Adam LR .003 from prior G7 validation-only tuning. All individual outputs retained, no exclusions.

## Main native-float32 results: time and robustness

Lower computational time and gauge drift are better. Every reported median includes all five target-seed runs. Crossings are first observed at 10-step intervals, at a 90% *validation* accuracy threshold, not test-set selection.

| Task / depth | Adam median time-to-90% (ms) | Official PathCond+Adam (ms) | PathCond / Adam time | Adam mean gauge logit gap (300 steps) | PathCond mean gauge gap |
|---|---:|---:|---:|---:|---:|
| Digits / 3 | **24.14** | 69.70 | 2.89× | 29.273 | **3.484** |
| Digits / 6 | **40.77** | 128.73 | 3.16× | 98.977 | **20.267** |
| Circle / 3 | **23.51** | 65.34 | 2.78× | 7.287 | **1.820** |
| Circle / 6 | **29.57** | 113.53 | 3.84× | 9.239 | **2.577** |

For the **300-step accuracy** comparison:

| Task / depth | Adam test accuracy | Original PathCond+Adam test accuracy | Adam test CE | PathCond+Adam test CE |
|---|---:|---:|---:|---:|
| Digits / 3 | 96.72% | **96.78%** | 0.13103 | **0.12941** |
| Digits / 6 | **95.67%** | 95.56% | **0.24352** | 0.25521 |
| Circle / 3 | 98.39% | **98.61%** | **0.03802** | 0.03932 |
| Circle / 6 | **98.17%** | 97.94% | **0.03784** | 0.04466 |

Differences in test accuracy are small, consistent with H4. The ranking of accuracy versus CE can differ because CE measures confidence as well as correct labels. Do not claim PathCond uniformly improves test loss.

## Why PathCond lost on tiny CPU networks

The native-float32 PathCond one-time rescaling took about **44–46 ms** on three-hidden-layer models and **88–89 ms** on six-hidden-layer models (median over five seeds), even before Adam trained. On these small models, ordinary Adam itself needed only about **24–41 ms** to reach the 90%-validation target. In two of four cells PathCond reduced the **median crossing step** (digits depth3 from 70 to 60; circle depth6 from 60 to 50); in the other two cells median crossing steps tied. Any modest reduction in steps was overwhelmed by the conditioning overhead.

A larger model trained for more steps could amortize this overhead differently; G10 did **not** test that, and CPU times of tens of milliseconds are sensitive to the specific runner and workload. This is a screening result, not a universal speed claim. For fair real-world scaling one should measure matched GPU hardware, larger networks/datasets, longer training and confidence intervals.

## Precision distinction and original-vs-diagnostic controls

The tested **native-float32 official PathCond** follows upstream as released. A separate **float64 PathCond diagnostic** passes upstream's calculated BZ in double to original `reweight_model_inplace`, without the published float32 cast. This is not a newly invented optimization method and is never presented as official released PathCond. It was only run on double-precision model parameters, not mixed into float32 as an incompatible dtype.

G10's float64 arm results and full per-seed precision errors are retained in the raw JSON. The G8 precision finding remains true: removing the final float32 cast restores near-machine-precision initial-function preservation for these float64 MLPs. G9's separate finding also remains true: that precision fix does not make subsequent Adam dynamics function-invariant.

## What the project can and cannot claim after G10

On small plain ReLU MLPs, PathCond substantially decreases the arbitrary-starting-gauge sensitivity of Adam while maintaining comparable 300-step accuracy in float32. **It did not improve time to the same 90% validation accuracy including its preprocessing cost** in any of four cases.

It would be misleading to say that PathCond has no computational value generally: our tiny networks and short 300-step windows are a case where initialization overhead dominates. Conversely, it would be misleading to assert that improved fixed-step cross entropy equals faster training in wall-clock time. G10 directly falsifies that interpretation for these four cells.

The mean gauge-logit gap measures parameterization sensitivity, not statistical calibration or test CE by itself. The artificial gauge range 1/8 to 8 is only one chosen stress regime, not an exhaustive stability test. Only 5 seeds per cell, CPU single thread, two easy datasets; no ResNets, Transformers, CUDA, or modern large-scale tasks.

## Reproduction

```bash
cd experiments/lapse-meter
# Exact upstream and pinned CPU dependencies are installed by
# .github/workflows/lapse-g10-time-to-target.yml
python experiments/g10_time_to_target.py --smoke
python experiments/g10_time_to_target.py results/g10/full.json
```

All G10 target-seed outputs including right-censoring status, early validation checkpoints, separate prep and update computation times, and test accuracy/CE at steps100 and300 are in artifact `lapse-g10-full-results` from [verified GitHub Actions run 40798278560](https://github.com/maaronfanberg-lab/me-/actions/runs/40798278560). Earlier G1–G9 PRs and all negative scientific findings remain unmodified; G10 is a separate unmerged research branch.
