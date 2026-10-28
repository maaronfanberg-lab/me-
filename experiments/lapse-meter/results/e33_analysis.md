# Experiment 33 results

**Verdicts:** P33a fails, P33b holds. Account B (the bias channel): **refuted**.

Per-run kick rule right in 10 of 12 runs.

| task | condition | seed | step-one kick | rule says | transport | final loss | test acc | reading step | log lines | observed |
|---|---|---|---|---|---|---|---|---|---|---|
| digits | detach_mean | 0 | 2395.7 | broken | – | 57.7651 | 0.108 | – | 1 | **broken** |
| digits | detach_mean | 1 | 1640.0 | broken | – | 54.5846 | 0.103 | – | 1 | **broken** |
| digits | detach_mean | 2 | 2093.3 | broken | – | 41.3841 | 0.081 | – | 1 | **broken** |
| digits | detach_random | 0 | 2395.7 | broken | +0.03 | 0.0044 | 0.977 | 1450 | 121 | **broken** |
| digits | detach_random | 1 | 1640.0 | broken | +0.27 | 0.0086 | 0.912 | 3500 | 121 | **broken** |
| digits | detach_random | 2 | 2093.3 | broken | +0.05 | 0.0143 | 0.937 | 3850 | 121 | **broken** |
| circle-clean | detach_mean | 0 | 108.1 | healthy | – | 259.1248 | 0.528 | – | 25 | **broken** |
| circle-clean | detach_mean | 1 | 216.1 | broken | – | 25.6605 | 0.496 | – | 11 | **broken** |
| circle-clean | detach_mean | 2 | 369.1 | broken | – | 293.4184 | 0.514 | – | 23 | **broken** |
| circle-clean | detach_random | 0 | 108.1 | healthy | +0.04 | 0.0018 | 1.000 | 400 | 121 | **broken** |
| circle-clean | detach_random | 1 | 216.1 | broken | +0.11 | 0.0017 | 1.000 | 350 | 121 | **broken** |
| circle-clean | detach_random | 2 | 369.1 | broken | +0.04 | 0.0018 | 1.000 | 400 | 121 | **broken** |
