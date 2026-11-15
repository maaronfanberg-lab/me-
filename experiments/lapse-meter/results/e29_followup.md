# Experiment 29 follow-up (exploratory, after the results)

## A. Plain ReLU against fixed centering, digits seed 0, first 20 steps

| step | plain: loss | plain: last stream | plain: shared logits | center: loss | center: last stream | center: readout input, shared part | center: shared logits |
|---|---|---|---|---|---|---|---|
| 0 | 57.8 | 234 | 90.7 | 10.7 | 234 | 4 | 1.71 |
| 1 | 173 | 105 | 750 | 50.4 | 258 | 64 | 67.5 |
| 2 | 22.5 | 20 | 136 | 146 | 71 | 154 | 240 |
| 3 | 12.1 | 16 | 104 | 88 | 205 | 108 | 547 |
| 4 | 8.68 | 14 | 95.8 | 141 | 221 | 91 | 421 |
| 5 | 6.78 | 13 | 86.2 | 231 | 71 | 150 | 1.08e+03 |
| 6 | 6.16 | 13 | 83 | 600 | 415 | 145 | 656 |
| 7 | 5.22 | 12 | 79.9 | 406 | 22 | 191 | 1.2e+03 |
| 8 | 4.6 | 12 | 76.5 | 527 | 27 | 187 | 1.67e+03 |
| 9 | 4.25 | 12 | 73.8 | 583 | 47 | 174 | 1.84e+03 |
| 10 | 4.06 | 11 | 73 | 400 | 358 | 168 | 281 |
| 11 | 3.77 | 11 | 71.3 | 782 | 24 | 188 | 1.8e+03 |
| 12 | 3.64 | 11 | 70.4 | 678 | 29 | 183 | 1.68e+03 |
| 13 | 3.4 | 11 | 68.9 | 726 | 37 | 177 | 1.68e+03 |
| 14 | 3.25 | 11 | 68.1 | 667 | 78 | 148 | 1.48e+03 |
| 15 | 3.04 | 11 | 67.5 | 2.27e+03 | 1252 | 920 | 6.31e+03 |
| 16 | 2.96 | 11 | 67.2 | 3.77e+03 | 72 | 176 | 4.62e+03 |
| 17 | 2.89 | 11 | 67.3 | 1.18e+04 | 2923 | 1896 | 2.69e+04 |
| 18 | 2.82 | 11 | 66.9 | 5.81e+03 | 57 | 179 | 7.6e+03 |
| 19 | 2.74 | 11 | 66.6 | 9.03e+03 | 524 | 305 | 2.07e+04 |
| 20 | 2.69 | 11 | 66.6 | 2.22e+03 | 170 | 143 | 2.1e+03 |

## B. What the first steps do to the blocks, digits seed 0

| condition | step | gates open per example | units dead for every example | last stream | transport |
|---|---|---|---|---|---|
| plain | 0 | 0.50 | 0.28 | 234 | +2.30 |
| plain | 1 | 0.43 | 0.25 | 105 | +2.93 |
| plain | 2 | 0.26 | 0.05 | 20 | +1.12 |
| plain | 3 | 0.25 | 0.06 | 16 | +0.87 |
| plain | 5 | 0.23 | 0.07 | 13 | +0.56 |
| plain | 10 | 0.22 | 0.04 | 11 | +0.46 |
| plain | 20 | 0.22 | 0.04 | 11 | +0.27 |
| plain | 50 | 0.22 | 0.06 | 11 | +0.10 |
| plain | 100 | 0.23 | 0.09 | 14 | +0.02 |
| plain | 200 | 0.23 | 0.11 | 17 | +0.02 |
| kick cap 10 | 0 | 0.50 | 0.28 | 234 | +2.30 |
| kick cap 10 | 1 | 0.43 | 0.25 | 105 | +1.21 |
| kick cap 10 | 2 | 0.42 | 0.24 | 83 | +0.83 |
| kick cap 10 | 3 | 0.42 | 0.23 | 73 | +0.73 |
| kick cap 10 | 5 | 0.41 | 0.22 | 62 | +0.36 |
| kick cap 10 | 10 | 0.40 | 0.21 | 51 | +0.49 |
| kick cap 10 | 20 | 0.38 | 0.19 | 36 | +0.46 |
| kick cap 10 | 50 | 0.35 | 0.15 | 23 | +0.24 |
| kick cap 10 | 100 | 0.35 | 0.15 | 27 | +0.43 |
| kick cap 10 | 200 | 0.36 | 0.15 | 31 | +0.59 |
| signed twin | 0 | 0.50 | 0.00 | 8 | +0.22 |
| signed twin | 1 | 0.50 | 0.00 | 8 | +0.22 |
| signed twin | 2 | 0.50 | 0.00 | 7 | +0.22 |
| signed twin | 3 | 0.50 | 0.00 | 7 | +0.21 |
| signed twin | 5 | 0.50 | 0.00 | 7 | +0.21 |
| signed twin | 10 | 0.50 | 0.00 | 8 | +0.22 |
| signed twin | 20 | 0.50 | 0.00 | 8 | +0.25 |
| signed twin | 50 | 0.50 | 0.00 | 9 | +0.36 |
| signed twin | 100 | 0.50 | 0.00 | 10 | +0.45 |
| signed twin | 200 | 0.50 | 0.00 | 11 | +0.55 |

## C. Runs whose loss-0.03 reading falls at or before their first logged step after 0

8 of 125 conditions that reach loss 0.03: e26/circle-clean_pre_final_relu, e26/circle-clean_pre_final_relu_d192, e26/circle-clean_pre_final_signed, e26/circle-clean_pre_relu, e26/circle-clean_pre_relu_d192, e26/circle-clean_pre_signed, e29/circle-clean_center, e29/circle-clean_center_random.
