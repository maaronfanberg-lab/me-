# Escape account checks (THEORY_KICK.md amendment 3)

| task | lr | stream at 0 → 500 | η·λ_out at step 0 | η·λ_out steps 100–500, median [range] | transport at 500 | loss at 500 |
|---|---|---|---|---|---|---|
| digits | 0.02 | 234 → 33.1 | 5.87e-10 | 0.71 [0.50–1.39] | +0.13 | 0.314 |
| digits | 0.05 | 234 → 20.1 | 1.47e-09 | 0.31 [0.23–0.50] | +0.02 | 0.132 |
| digits | 0.1 | 234 → 21.2 | 2.93e-09 | 0.34 [0.21–1.30] | +0.00 | 0.067 |
| circle-clean | 0.02 | 92 → 20.1 | 6.23 | 0.48 [0.21–1.77] | +1.06 | 0.070 |
| circle-clean | 0.05 | 92 → 2.8 | 15.6 | 0.00 [0.00–0.01] | +0.04 | 0.021 |
| circle-clean | 0.1 | 92 → 0.9 | 31.1 | 0.01 [0.00–0.02] | +0.66 | 0.026 |

- digits: E-i stream ratio lr 0.02 / 0.1 = 1.56 → **fails**; E-ii median η·λ_out at lr 0.05 = 0.31 → **fails**
- circle-clean: E-i stream ratio lr 0.02 / 0.1 = 21.47 → **fails**; E-ii median η·λ_out at lr 0.05 = 0.00 → **fails**
