# Experiment 24 results

**Verdicts:** P24a holds, P24b fails, P24c fails, P24d holds, P24e holds. Kick as a cause: **mixed**.

Spearman(log effective kick, transport) over the cap runs: digits -0.51, circle-clean -0.74.

Per-run rule right in 42 of 48 runs.

| task | condition | seed | effective step-one kick | rule says | transport | | steps the cap bound | observed |
|---|---|---|---|---|---|---|---|---|
| digits | cap3 | 0 | 3.0 | healthy | +0.96 |  | 457 (last 919) | **healthy** |
| digits | cap3 | 1 | 3.0 | healthy | +0.78 |  | 469 (last 1176) | **healthy** |
| digits | cap3 | 2 | 3.0 | healthy | +0.78 |  | 505 (last 1059) | **healthy** |
| digits | cap10 | 0 | 10.0 | healthy | +0.81 |  | 31 (last 40) | **healthy** |
| digits | cap10 | 1 | 10.0 | healthy | +0.66 |  | 29 (last 63) | **healthy** |
| digits | cap10 | 2 | 10.0 | healthy | +0.67 |  | 27 (last 94) | **healthy** |
| digits | cap30 | 0 | 30.0 | healthy | +0.78 |  | 8 (last 8) | **healthy** |
| digits | cap30 | 1 | 30.0 | healthy | +0.65 |  | 7 (last 7) | **healthy** |
| digits | cap30 | 2 | 30.0 | healthy | +0.66 |  | 7 (last 6) | **healthy** |
| digits | cap100 | 0 | 100.0 | healthy | +0.78 |  | 3 (last 2) | **healthy** |
| digits | cap100 | 1 | 100.0 | healthy | +0.72 |  | 3 (last 2) | **healthy** |
| digits | cap100 | 2 | 100.0 | healthy | +0.64 |  | 3 (last 2) | **healthy** |
| digits | cap300 | 0 | 300.0 | healthy | +0.80 |  | 2 (last 1) | **healthy** |
| digits | cap300 | 1 | 300.0 | healthy | +0.66 |  | 2 (last 1) | **healthy** |
| digits | cap300 | 2 | 300.0 | healthy | +0.76 |  | 2 (last 1) | **healthy** |
| digits | cap1000 | 0 | 1000.0 | broken | +0.22 |  | 1 (last 0) | **broken** |
| digits | cap1000 | 1 | 1000.0 | broken | +0.47 |  | 1 (last 0) | **healthy** |
| digits | cap1000 | 2 | 1000.0 | broken | +0.71 (loss 0.1) |  | 1 (last 0) | **healthy** |
| digits | zloss0.0001 | 0 | 2422.0 | broken | +0.05 |  | 0 | **broken** |
| digits | zloss0.0001 | 1 | 1658.2 | broken | +0.32 |  | 0 | **healthy** |
| digits | zloss0.0001 | 2 | 2111.6 | broken | +0.03 |  | 0 | **broken** |
| digits | zloss0.01 | 0 | 5101.5 | broken | +0.12 |  | 0 | **broken** |
| digits | zloss0.01 | 1 | 3516.7 | broken | +0.18 (loss 0.1) |  | 0 | **broken** |
| digits | zloss0.01 | 2 | 3976.1 | broken | -0.01 (loss 0.3) |  | 0 | **broken** |
| circle-clean | cap3 | 0 | 3.0 | healthy | +1.18 |  | 94 (last 129) | **healthy** |
| circle-clean | cap3 | 1 | 3.0 | healthy | +1.24 |  | 93 (last 130) | **healthy** |
| circle-clean | cap3 | 2 | 3.0 | healthy | +1.26 |  | 104 (last 139) | **healthy** |
| circle-clean | cap10 | 0 | 10.0 | healthy | +1.23 |  | 19 (last 31) | **healthy** |
| circle-clean | cap10 | 1 | 10.0 | healthy | +1.29 |  | 19 (last 31) | **healthy** |
| circle-clean | cap10 | 2 | 10.0 | healthy | +1.28 |  | 15 (last 35) | **healthy** |
| circle-clean | cap30 | 0 | 30.0 | healthy | +1.17 |  | 3 (last 3) | **healthy** |
| circle-clean | cap30 | 1 | 30.0 | healthy | +1.25 |  | 5 (last 5) | **healthy** |
| circle-clean | cap30 | 2 | 30.0 | healthy | +1.27 |  | 4 (last 4) | **healthy** |
| circle-clean | cap100 | 0 | 100.0 | healthy | +1.12 |  | 2 (last 1) | **healthy** |
| circle-clean | cap100 | 1 | 100.0 | healthy | +0.49 |  | 1 (last 0) | **healthy** |
| circle-clean | cap100 | 2 | 100.0 | healthy | +1.38 |  | 1 (last 0) | **healthy** |
| circle-clean | cap300 | 0 | 108.1 | healthy | +0.74 |  | 1 (last 1) | **healthy** |
| circle-clean | cap300 | 1 | 216.1 | broken | +0.12 |  | 0 | **broken** |
| circle-clean | cap300 | 2 | 300.0 | broken | +0.05 |  | 1 (last 0) | **broken** |
| circle-clean | cap1000 | 0 | 108.1 | healthy | +0.04 |  | 0 | **broken** |
| circle-clean | cap1000 | 1 | 216.1 | broken | +0.12 |  | 0 | **broken** |
| circle-clean | cap1000 | 2 | 369.1 | broken | +0.04 |  | 0 | **broken** |
| circle-clean | zloss0.0001 | 0 | 107.9 | healthy | +0.02 |  | 0 | **broken** |
| circle-clean | zloss0.0001 | 1 | 216.0 | broken | +0.24 |  | 0 | **broken** |
| circle-clean | zloss0.0001 | 2 | 369.8 | broken | +0.06 |  | 0 | **broken** |
| circle-clean | zloss0.01 | 0 | 94.3 | healthy | +0.17 |  | 0 | **broken** |
| circle-clean | zloss0.01 | 1 | 205.1 | broken | – | failed to train | 0 | **broken** |
| circle-clean | zloss0.01 | 2 | 443.5 | broken | – | failed to train | 0 | **broken** |
