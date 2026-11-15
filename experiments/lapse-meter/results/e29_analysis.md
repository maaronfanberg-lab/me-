# Experiment 29 results

**Verdicts:** P29a holds, P29b fails. Common-mode kick as the damaging part: **mixed**.

Per-run kick rule right in 6 of 12 runs.

| task | condition | seed | step-one kick | rule says | transport | final loss | test acc | observed |
|---|---|---|---|---|---|---|---|---|
| digits | center | 0 | 170.3 | healthy | +0.54 | 0.0000 | 0.965 | **healthy** |
| digits | center | 1 | 108.4 | healthy | – | 13.0036 | 0.103 | **broken** |
| digits | center | 2 | 152.8 | healthy | +0.46 | 0.0000 | 0.975 | **healthy** |
| digits | center_random | 0 | 2416.6 | broken | – | 50.5845 | 0.108 | **broken** |
| digits | center_random | 1 | 2683.8 | broken | – | 61.3334 | 0.103 | **broken** |
| digits | center_random | 2 | 3804.4 | broken | +0.55 | 0.0000 | 0.945 | **healthy** |
| circle-clean | center | 0 | 19.5 | healthy | +1.28 | 0.0000 | 1.000 | **healthy** |
| circle-clean | center | 1 | 66.9 | healthy | +1.04 | 0.0000 | 1.000 | **healthy** |
| circle-clean | center | 2 | 142.2 | broken | +3.15 | 0.0000 | 1.000 | **healthy** |
| circle-clean | center_random | 0 | 264.0 | broken | +1.48 | 0.0000 | 1.000 | **healthy** |
| circle-clean | center_random | 1 | 219.2 | broken | +1.06 | 0.0000 | 0.998 | **healthy** |
| circle-clean | center_random | 2 | 543.6 | broken | +2.70 | 0.0000 | 1.000 | **healthy** |
