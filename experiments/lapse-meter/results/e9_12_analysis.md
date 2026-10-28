# Experiments 9–12 results

Primary measure: ln_transport at training loss 0.03. Reference groups from experiment 8.

**Verdicts:** P9 holds, P9b holds, P10 holds, P11a fails, P11b holds, P12 fails. Pile-up hypothesis: **supported**.


## digits

Reference: plain ReLU 96 = +0.12 ± 0.13 (3/3); tanh 96 = +0.82 ± 0.03 (3/3)

| condition | transport at loss 0.03 | rescued? (gap / threshold vs plain ReLU 96) |
|---|---|---|
| signed ReLU, 96 | +0.70 ± 0.00 (3/3) | yes (+0.58 / 0.25) |
| signed ReLU, 24 | +0.64 ± 0.02 (3/3) | yes (+0.52 / 0.25) |
| shrink, 96 | +0.63 ± 0.03 (3/3) | yes (+0.51 / 0.26) |
| tanh+1, 96 | +0.33 ± 0.03 (3/3) | no (+0.21 / 0.26) |
| warm-up, 96 | +0.82 ± 0.05 (3/3) | yes (+0.70 / 0.27) |
| zero-out, 96 | +0.06 ± 0.05 (3/3) | no (-0.06 / 0.27) |

P9b (signed ReLU, 96 not below 24 by more than threshold): yes (24 minus 96 = -0.06, threshold 0.04)

| plain ReLU depth | transport at loss 0.03 | stream growth at init (last/first block) |
|---|---|---|
| 12 | +0.65 ± 0.05 (3/3) | 3× |
| 24 | +0.72 ± 0.05 (3/3) | 5× |
| 48 | +0.56 ± 0.20 (3/3) | 11× |
| 64 | +0.28 ± 0.25 (3/3) | 17× |
| 80 | +0.06 ± 0.06 (3/3) | 26× |
| 96 | +0.12 ± 0.13 (3/3) | 37× |
| 128 | +0.01 ± 0.00 (3/3) | 69× |

P12 (128 below 48 by more than threshold): yes (48 minus 128 = +0.55, threshold 0.40)

## circle-clean

Reference: plain ReLU 96 = +0.07 ± 0.05 (3/3); tanh 96 = +1.61 ± 0.17 (3/3)

| condition | transport at loss 0.03 | rescued? (gap / threshold vs plain ReLU 96) |
|---|---|---|
| signed ReLU, 96 | +1.16 ± 0.03 (3/3) | yes (+1.09 / 0.11) |
| signed ReLU, 24 | +1.09 ± 0.08 (3/3) | yes (+1.02 / 0.19) |
| shrink, 96 | +1.33 ± 0.04 (3/3) | yes (+1.26 / 0.12) |
| tanh+1, 96 | +0.80 ± 0.03 (3/3) | yes (+0.74 / 0.11) |
| warm-up, 96 | +1.19 ± 0.06 (3/3) | yes (+1.12 / 0.14) |
| zero-out, 96 | +1.30 ± 0.66 (3/3) | no (+1.23 / 1.33) |

P9b (signed ReLU, 96 not below 24 by more than threshold): yes (24 minus 96 = -0.07, threshold 0.18)

| plain ReLU depth | transport at loss 0.03 | stream growth at init (last/first block) |
|---|---|---|
| 12 | +1.01 ± 0.05 (3/3) | 3× |
| 24 | +1.08 ± 0.07 (3/3) | 5× |
| 48 | +1.07 ± 0.04 (3/3) | 11× |
| 64 | +1.08 ± 0.07 (3/3) | 17× |
| 80 | +0.64 ± 0.50 (3/3) | 26× |
| 96 | +0.07 ± 0.05 (3/3) | 37× |
| 128 | +1.51 ± 0.14 (2/3) | 69× |

P12 (128 below 48 by more than threshold): no (48 minus 128 = -0.44, threshold 0.29)
