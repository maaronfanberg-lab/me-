# Experiments 17–20 results

**Verdicts:** P17a holds, P17b holds, P18 holds, P19 holds.


## digits

| experiment 17 | transport at loss 0.03 | failed to train |
|---|---|---|
| plain one-matrix ReLU, 96 (exp. 8) | +0.12 ± 0.13 (3/3) | – |
| two-matrix ReLU, 96 | +0.84 ± 0.01 (3/3) | 0 of 3 |
| two-matrix ReLU, 24 | +0.79 ± 0.03 (3/3) | 0 of 3 |

P17a (two-matrix 96 rescued): yes (+0.72 / 0.25). P17b (96 not below 24 by more than threshold): yes (24 minus 96 = -0.05, threshold 0.07).

| experiment 18 (Adam, lr 0.001) | transport at loss 0.03 | failed to train | starting → final output-layer weight norm |
|---|---|---|---|
| ReLU, 96 | +1.42 ± 0.01 (3/3) | 0 of 3 | 3.1 → 3.1 |
| ReLU, 24 | +1.22 ± 0.06 (3/3) | 0 of 3 | 3.1 → 3.3 |
| tanh, 96 | +1.47 ± 0.08 (3/3) | 0 of 3 | 3.1 → 3.7 |

P18 (Adam ReLU 96 not below Adam ReLU 24 by more than threshold): yes (24 minus 96 = -0.20, threshold 0.13).

| experiment 19 (width 128, 96 layers) | transport at loss 0.03 | failed to train |
|---|---|---|
| plain ReLU | +0.05 ± 0.07 (3/3) | 0 of 3 |
| signed ReLU | +0.65 ± 0.03 (3/3) | 0 of 3 |

P19 (signed rescued against plain at width 128): yes (+0.60 / 0.15).

## circle-clean

| experiment 17 | transport at loss 0.03 | failed to train |
|---|---|---|
| plain one-matrix ReLU, 96 (exp. 8) | +0.07 ± 0.05 (3/3) | – |
| two-matrix ReLU, 96 | +1.35 ± 0.07 (3/3) | 0 of 3 |
| two-matrix ReLU, 24 | +1.25 ± 0.06 (3/3) | 0 of 3 |

P17a (two-matrix 96 rescued): yes (+1.28 / 0.16). P17b (96 not below 24 by more than threshold): yes (24 minus 96 = -0.09, threshold 0.19).

| experiment 18 (Adam, lr 0.001) | transport at loss 0.03 | failed to train | starting → final output-layer weight norm |
|---|---|---|---|
| ReLU, 96 | +2.21 ± 0.10 (3/3) | 0 of 3 | 1.3 → 1.3 |
| ReLU, 24 | +2.04 ± 0.05 (3/3) | 0 of 3 | 1.5 → 1.6 |
| tanh, 96 | +1.76 ± 0.08 (3/3) | 0 of 3 | 1.3 → 1.5 |

P18 (Adam ReLU 96 not below Adam ReLU 24 by more than threshold): yes (24 minus 96 = -0.17, threshold 0.23).

| experiment 19 (width 128, 96 layers) | transport at loss 0.03 | failed to train |
|---|---|---|
| plain ReLU | +0.22 ± 0.33 (3/3) | 0 of 3 |
| signed ReLU | +1.08 ± 0.03 (3/3) | 0 of 3 |

P19 (signed rescued against plain at width 128): yes (+0.85 / 0.67).

## Experiment 20 (exploratory): does losing transport cost learning?

Every 96-layer, width-64, SGD condition, at step 6,000. Each cell is the mean over three seeds, digits / circle.

| condition | transport at loss 0.03, digits / circle | final training loss, digits / circle | test accuracy, digits / circle |
|---|---|---|---|
| plain ReLU | +0.12 / +0.07 | 0.0084 / 0.0018 | 0.944 / 1.000 |
| tanh | +0.82 / +1.61 | 0.0012 / 0.0002 | 0.982 / 1.000 |
| signed ReLU | +0.70 / +1.16 | 0.0006 / 0.0002 | 0.981 / 1.000 |
| soft threshold | +0.63 / +1.33 | 0.0005 / 0.0002 | 0.978 / 1.000 |
| tanh + 1 | +0.33 / +0.80 | 0.0021 / 0.0003 | 0.979 / 1.000 |
| warm-up 500 | +0.82 / +1.19 | 0.0006 / 0.0003 | 0.982 / 1.000 |
| zero output start | +0.06 / +1.30 | 0.0047 / 0.0018 | 0.947 / 1.000 |
| warm-up 50 | +0.75 / +1.23 | 0.0006 / 0.0007 | 0.985 / 1.000 |
| warm-up 150 | +0.77 / +1.22 | 0.0006 / 0.0005 | 0.982 / 1.000 |
| warm-up 1500 | +0.84 / +1.19 | 0.0006 / 0.0002 | 0.985 / 1.000 |
| warm-up, blocks only | – / +0.31 | 0.8726 / 0.0017 | 0.539 / 1.000 |
| warm-up, output only | +0.83 / +1.39 | 0.0006 / 0.0001 | 0.982 / 1.000 |
| signs q = 0.625 | +0.76 / +1.18 | 0.0005 / 0.0002 | 0.982 / 1.000 |
| signs q = 0.75 | +0.78 / +1.21 | 0.0005 / 0.0001 | 0.982 / 1.000 |
| signs q = 0.875 | +0.33 / +1.11 | 0.0020 / 0.0004 | 0.973 / 1.000 |
| two-matrix ReLU | +0.84 / +1.35 | 0.0004 / 0.0001 | 0.976 / 1.000 |

digits: across 45 runs, Spearman correlation of transport with log final training loss -0.64, with test accuracy +0.55.

circle-clean: across 48 runs, Spearman correlation of transport with log final training loss -0.53, with test accuracy undefined (every run scores 1.000).
