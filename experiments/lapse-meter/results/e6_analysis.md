# Experiment 6 results

## Within runs: does the tilt rise as training loss falls?

Spearman correlation of T* with log training loss, per run. Negative = steeper as loss falls. Pre-registered pass: negative in at least 20 of 24 runs. **Result: 18 of 24.**

| condition | seed 0 | seed 1 | seed 2 |
|---|---|---|---|
| circle-clean | -1.00 | -1.00 | -0.99 |
| circle | +0.36 | +0.10 | +0.41 |
| circle-noisier | +0.55 | +0.55 | +0.56 |
| digits | -1.00 | -1.00 | -0.99 |
| digits-5class | -1.00 | -0.99 | -1.00 |
| digits-3class | -1.00 | -1.00 | -0.99 |
| digits-2class | -1.00 | -1.00 | -1.00 |
| digits-noisy | -0.99 | -1.00 | -1.00 |

## T* at matched training loss (mean ± sd over seeds; runs reaching that loss)

| condition | classes | loss 0.3 | loss 0.1 | loss 0.03 | loss 0.01 | final loss |
|---|---|---|---|---|---|---|
| circle-clean | 2 | +1.10 ± 0.17 (3) | +1.74 ± 0.21 (3) | +2.15 ± 0.16 (3) | +2.45 ± 0.18 (3) | 0.0002 |
| circle | 2 | +1.18 ± 0.18 (3) | +2.02 ± 0.17 (3) | not reached | not reached | 0.0702 |
| circle-noisier | 2 | +1.50 ± 0.20 (3) | not reached | not reached | not reached | 0.2340 |
| digits | 10 | +0.41 ± 0.03 (3) | +0.71 ± 0.03 (3) | +0.96 ± 0.04 (3) | +1.11 ± 0.07 (3) | 0.0013 |
| digits-5class | 5 | +0.55 ± 0.05 (3) | +0.96 ± 0.01 (3) | +1.28 ± 0.02 (3) | +1.45 ± 0.03 (3) | 0.0007 |
| digits-3class | 3 | +0.45 ± 0.13 (3) | +1.07 ± 0.06 (3) | +1.46 ± 0.04 (3) | +1.66 ± 0.04 (3) | 0.0003 |
| digits-2class | 2 | +0.54 ± 0.08 (3) | +1.16 ± 0.07 (3) | +1.63 ± 0.08 (3) | +1.87 ± 0.09 (3) | 0.0001 |
| digits-noisy | 10 | +1.41 ± 0.02 (3) | +1.76 ± 0.02 (3) | +2.00 ± 0.01 (3) | +2.16 ± 0.05 (3) | 0.0053 |

## H1: do task differences persist at matched loss?

Pre-registered: H1 fails if two or more of these comparisons persist at any level where both are present.

| comparison | loss 0.3 | loss 0.1 | loss 0.03 | loss 0.01 | persists anywhere? |
|---|---|---|---|---|---|
| circle-clean − circle | -0.08 / 0.49 | -0.28 / 0.54 | – | – | no |
| circle − circle-noisier | -0.32 / 0.53 | – | – | – | no |
| circle-clean − circle-noisier | -0.40 / 0.53 | – | – | – | no |
| digits-noisy − digits | +1.00 / 0.08 **persists** | +1.05 / 0.07 **persists** | +1.04 / 0.09 **persists** | +1.05 / 0.18 **persists** | **yes** |

**1 of 4 comparisons persist. H1 holds by the pre-registered rule.**

## H2: does class count set the tilt at matched loss?

| loss level | T* by classes (2, 3, 5, 10) | monotone 2 > 3 > 5 > 10? | 2 − 10 difference / threshold | persists? |
|---|---|---|---|---|
| 0.3 | +0.54, +0.45, +0.55, +0.41 | no | +0.12 / 0.18 | no |
| 0.1 | +1.16, +1.07, +0.96, +0.71 | yes | +0.45 / 0.14 | **yes** |
| 0.03 | +1.63, +1.46, +1.28, +0.96 | yes | +0.67 / 0.18 | **yes** |
| 0.01 | +1.87, +1.66, +1.45, +1.11 | yes | +0.76 / 0.23 | **yes** |

**H2 holds at some levels** (2-vs-10 difference persisting at 3 of 4 levels where all four conditions reached the loss).
