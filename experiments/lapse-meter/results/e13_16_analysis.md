# Experiments 13–16 results

Primary measure: ln_transport at training loss 0.03.

**Verdicts:** P13a holds, P13b fails, P14a untestable, P14b fails, P15a holds, P15b holds, P16 fails. First-step-shock hypothesis: **mixed**.


## digits

References: plain ReLU 96 = +0.12 ± 0.13 (3/3); plain ReLU 128 = +0.01 ± 0.00 (3/3)

| condition | transport at loss 0.03 | rescued? (gap / threshold vs plain ReLU, same depth) | failed to train |
|---|---|---|---|
| warm-up 50 | +0.75 ± 0.07 (3/3) | yes (+0.63 / 0.29) | 0 of 3 |
| warm-up 150 | +0.77 ± 0.06 (3/3) | yes (+0.65 / 0.28) | 0 of 3 |
| warm-up 500 (exp. 11) | +0.82 ± 0.05 (3/3) | yes (+0.70 / 0.27) | 0 of 3 |
| warm-up 1500 | +0.84 ± 0.06 (3/3) | yes (+0.72 / 0.28) | 0 of 3 |
| warm-up 500, blocks only | 0/3 reached | untestable | 1 of 3 |
| warm-up 500, output only | +0.83 ± 0.08 (3/3) | yes (+0.71 / 0.30) | 0 of 3 |
| signs q = 0.625 | +0.76 ± 0.05 (3/3) | yes (+0.64 / 0.27) | 0 of 3 |
| signs q = 0.75 | +0.78 ± 0.05 (3/3) | yes (+0.66 / 0.27) | 0 of 3 |
| signs q = 0.875 | +0.33 ± 0.30 (3/3) | no (+0.21 / 0.65) | 0 of 3 |
| 128 layers, warm-up 500 | +0.91 ± 0.04 (3/3) | yes (+0.91 / 0.08) | 0 of 3 |

## circle-clean

References: plain ReLU 96 = +0.07 ± 0.05 (3/3); plain ReLU 128 = +1.51 ± 0.14 (2/3)

| condition | transport at loss 0.03 | rescued? (gap / threshold vs plain ReLU, same depth) | failed to train |
|---|---|---|---|
| warm-up 50 | +1.23 ± 0.05 (3/3) | yes (+1.16 / 0.13) | 0 of 3 |
| warm-up 150 | +1.22 ± 0.06 (3/3) | yes (+1.15 / 0.15) | 0 of 3 |
| warm-up 500 (exp. 11) | +1.19 ± 0.06 (3/3) | yes (+1.12 / 0.14) | 0 of 3 |
| warm-up 1500 | +1.19 ± 0.06 (3/3) | yes (+1.12 / 0.15) | 0 of 3 |
| warm-up 500, blocks only | +0.31 ± 0.46 (3/3) | no (+0.25 / 0.92) | 0 of 3 |
| warm-up 500, output only | +1.39 ± 0.10 (3/3) | yes (+1.32 / 0.22) | 0 of 3 |
| signs q = 0.625 | +1.18 ± 0.08 (3/3) | yes (+1.11 / 0.18) | 0 of 3 |
| signs q = 0.75 | +1.21 ± 0.06 (3/3) | yes (+1.14 / 0.15) | 0 of 3 |
| signs q = 0.875 | +1.11 ± 0.01 (3/3) | yes (+1.04 / 0.09) | 0 of 3 |
| 128 layers, warm-up 500 | +1.21 ± 0.09 (3/3) | no (-0.30 / 0.33) | 0 of 3 |
