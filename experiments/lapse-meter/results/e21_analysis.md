# Experiment 21 results

Residual tanh, 24 layers. Transport at training loss 0.03.

**Verdicts:** P21a fails, P21b fails, P21c holds. H21 (normalization, not momentum): **mixed**.


## digits

SGD, lr 0.05 (experiment 8): +0.76 ± 0.03 (3/3)

| optimizer | transport at loss 0.03 | above SGD? (gap / threshold) | failed to train |
|---|---|---|---|
| Adam, lr 0.001 | +1.22 ± 0.05 (3/3) | yes (+0.46 / 0.12) | 0 of 3 |
| RMSprop, lr 0.001 | +1.23 ± 0.06 (3/3) | yes (+0.47 / 0.13) | 0 of 3 |
| momentum SGD, lr 0.005 | +0.76 ± 0.04 (3/3) | no (-0.01 / 0.09) | 0 of 3 |
| SGD, lr 0.02 | +0.76 ± 0.04 (3/3) | no (-0.01 / 0.10) | 0 of 3 |
| SGD, lr 0.1 | +0.76 ± 0.05 (3/3) | no (-0.00 / 0.11) | 0 of 3 |

## circle-clean

SGD, lr 0.05 (experiment 8): +1.45 ± 0.20 (3/3)

| optimizer | transport at loss 0.03 | above SGD? (gap / threshold) | failed to train |
|---|---|---|---|
| Adam, lr 0.001 | +1.36 ± 0.11 (3/3) | no (-0.08 / 0.45) | 0 of 3 |
| RMSprop, lr 0.001 | +1.57 ± 0.19 (3/3) | no (+0.12 / 0.54) | 0 of 3 |
| momentum SGD, lr 0.005 | +1.43 ± 0.20 (3/3) | no (-0.01 / 0.56) | 0 of 3 |
| SGD, lr 0.02 | +1.47 ± 0.21 (3/3) | no (+0.02 / 0.58) | 0 of 3 |
| SGD, lr 0.1 | +1.43 ± 0.21 (3/3) | no (-0.02 / 0.57) | 0 of 3 |
