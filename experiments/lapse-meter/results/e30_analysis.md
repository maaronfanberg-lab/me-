# Experiment 30 results

**Verdicts:** P30a (signed + offset broken, digits): holds; P30b (center + multiplier broken, digits): holds; P30c (signed + offset + cap 10 healthy, both tasks): holds.

**Account supported on digits:** K (total kick size).

Per-run kick rule right in 14 of 18 runs (reported, not tested).

| task | condition | seed | effective step-one kick | common-mode share | rule says | transport | final loss | test acc | steps capped | reading step | log lines | observed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| digits | signed_offset | 0 | 2081.0 | 1.000 | broken | – failed to train | 57.9143 | 0.108 | 0 | – | 1 | **broken** |
| digits | center_mult | 0 | 2395.6 | 0.001 | broken | +0.91 | 0.0000 | 0.960 | 0 | 1500 | 121 | **healthy** |
| digits | signed_offset_cap10 | 0 | 10.0 | 1.000 | healthy | +1.38 | 0.0001 | 0.987 | 1066 | 750 | 121 | **healthy** |
| digits | signed_offset | 1 | 1531.6 | 1.000 | broken | – failed to train | 52.8955 | 0.103 | 0 | – | 1 | **broken** |
| digits | center_mult | 1 | 1640.0 | 0.001 | broken | – failed to train | 13.0036 | 0.103 | 0 | – | 1 | **broken** |
| digits | signed_offset_cap10 | 1 | 10.0 | 1.000 | healthy | +1.30 | 0.0001 | 0.975 | 1073 | 800 | 121 | **healthy** |
| digits | signed_offset | 2 | 1940.9 | 1.000 | broken | – failed to train | 40.3316 | 0.081 | 0 | – | 1 | **broken** |
| digits | center_mult | 2 | 2093.3 | 0.000 | broken | – failed to train | 12.8017 | 0.081 | 0 | – | 1 | **broken** |
| digits | signed_offset_cap10 | 2 | 10.0 | 1.000 | healthy | +1.40 | 0.0001 | 0.985 | 1096 | 1000 | 121 | **healthy** |
| circle-clean | signed_offset | 0 | 223.7 | 1.000 | broken | +2.21 | 0.0000 | 1.000 | 0 | 100 | 121 | **healthy** |
| circle-clean | center_mult | 0 | 108.1 | 0.000 | healthy | +1.01 | 0.0000 | 1.000 | 0 | 50 | 121 | **healthy** |
| circle-clean | signed_offset_cap10 | 0 | 10.0 | 1.000 | healthy | +2.29 | 0.0000 | 1.000 | 211 | 250 | 121 | **healthy** |
| circle-clean | signed_offset | 1 | 93.2 | 1.000 | healthy | +2.20 | 0.0000 | 1.000 | 0 | 100 | 121 | **healthy** |
| circle-clean | center_mult | 1 | 216.1 | 0.005 | broken | +2.96 | 0.0002 | 1.000 | 0 | 600 | 121 | **healthy** |
| circle-clean | signed_offset_cap10 | 1 | 10.0 | 1.000 | healthy | +2.18 | 0.0000 | 1.000 | 182 | 200 | 121 | **healthy** |
| circle-clean | signed_offset | 2 | 220.7 | 1.000 | broken | +1.66 | 0.0000 | 1.000 | 0 | 100 | 121 | **healthy** |
| circle-clean | center_mult | 2 | 369.1 | 0.002 | broken | – failed to train | 14.2677 | 0.514 | 0 | – | 1 | **broken** |
| circle-clean | signed_offset_cap10 | 2 | 10.0 | 1.000 | healthy | +2.39 | 0.0000 | 1.000 | 227 | 250 | 121 | **healthy** |
