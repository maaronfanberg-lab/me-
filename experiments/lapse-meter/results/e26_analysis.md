# Experiment 26 results

**Verdicts:** P26a holds, P26b holds, P26c holds, P26d holds. Kick account of normalization: **supported** (refuted only if P26a fails on both tasks; see table).

| task | placement | level | ReLU transport | signed twin transport | ReLU below twin? (gap / threshold) | failed to train, ReLU / twin | final loss, ReLU / twin | test acc, ReLU / twin | healthy? |
|---|---|---|---|---|---|---|---|---|---|
| digits | final | 0.03 | +0.75 ± 0.09 (3/3) | +0.54 ± 0.02 (3/3) | no (+0.21 / 0.18) | 0 / 0 | 0.0012 / 0.0011 | 0.982 / 0.981 | **yes** |
| circle-clean | final | 0.03 | +1.11 ± 0.11 (3/3) | +0.60 ± 0.08 (3/3) | no (+0.51 / 0.26) | 0 / 0 | 0.0000 / 0.0001 | 1.000 / 1.000 | **yes** |
| digits | pre | 0.03 | +1.02 ± 0.09 (3/3) | +0.92 ± 0.05 (3/3) | no (+0.10 / 0.21) | 0 / 0 | 0.0006 / 0.0007 | 0.979 / 0.982 | **yes** |
| circle-clean | pre | 0.03 | +2.86 ± 1.45 (3/3) | +2.29 ± 0.35 (3/3) | no (+0.56 / 2.97) | 0 / 0 | 0.0000 / 0.0000 | 1.000 / 1.000 | **yes** |
| digits | pre_final | 0.03 | +0.93 ± 0.06 (3/3) | +0.89 ± 0.05 (3/3) | no (+0.04 / 0.16) | 0 / 0 | 0.0008 / 0.0008 | 0.977 / 0.981 | **yes** |
| circle-clean | pre_final | 0.03 | +2.50 ± 0.58 (3/3) | +2.26 ± 0.45 (3/3) | no (+0.23 / 1.47) | 0 / 0 | 0.0000 / 0.0000 | 1.000 / 1.000 | **yes** |
| digits | post | 0.03 | +0.20 ± 0.03 (3/3) | +0.21 ± 0.05 (3/3) | no (-0.02 / 0.12) | 0 / 0 | 0.0012 / 0.0012 | 0.986 / 0.978 | **yes** |
| circle-clean | post | 0.03 | +0.54 ± 0.06 (3/3) | +0.51 ± 0.06 (3/3) | no (+0.03 / 0.17) | 0 / 0 | 0.0001 / 0.0001 | 1.000 / 1.000 | **yes** |

**Stress case, 192 layers, ReLU (reported, not tested):**

| task | placement | transport at loss 0.03 | failed to train | final loss | test acc |
|---|---|---|---|---|---|
| digits | pre | +1.17 ± 0.08 (3/3) | 0 of 3 | 0.0004 | 0.979 |
| digits | pre_final | +0.86 ± 0.07 (3/3) | 0 of 3 | 0.0008 | 0.976 |
