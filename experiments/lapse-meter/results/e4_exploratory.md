# Experiment 4, exploratory (post-hoc) split of the tilt

T* = internal tilt ln(N_first/N_last) + output step ln(N_last). Stored profiles already have α removed.
Same runs as e4_analysis.md (test acc ≥ 0.70). The last column checks the two parts add back to T*.


**res24**

| condition | classes | final train loss | T* | internal tilt (hidden layers only) | output step ln N_last | sum check |
|---|---|---|---|---|---|---|
| circle | 2 | 0.071 | +2.16 | +1.64 ± 0.08 | +0.53 ± 0.03 | 4e-16 |
| circle-clean | 2 | 0.000 | +3.05 | +2.30 ± 0.27 | +0.75 ± 0.06 | 0e+00 |
| circle-noisier | 2 | 0.242 | +1.42 | +1.12 ± 0.10 | +0.30 ± 0.05 | 2e-16 |
| circle-embed64 | 2 | 0.070 | +1.88 | +1.45 ± 0.09 | +0.43 ± 0.01 | 2e-16 |
| circle-std1 | 2 | 0.070 | +2.02 | +1.53 ± 0.09 | +0.48 ± 0.02 | 4e-16 |
| digits | 10 | 0.002 | +1.32 | +1.18 ± 0.04 | +0.14 ± 0.02 | 0e+00 |
| digits-2class | 2 | 0.000 | +2.37 | +1.79 ± 0.12 | +0.59 ± 0.06 | 0e+00 |
| digits-noisy | 10 | 0.016 | +2.07 | +1.57 ± 0.04 | +0.49 ± 0.05 | 4e-16 |

**plain12**

| condition | classes | final train loss | T* | internal tilt (hidden layers only) | output step ln N_last | sum check |
|---|---|---|---|---|---|---|
| circle | 2 | 0.065 | +2.06 | +1.90 ± 0.26 | +0.17 ± 0.07 | 0e+00 |
| circle-clean | 2 | 0.000 | +2.84 | +2.75 ± 0.12 | +0.10 ± 0.12 | 0e+00 |
| circle-noisier | 2 | 0.208 | +1.44 | +1.40 ± 0.36 | +0.04 ± 0.07 | 2e-16 |
| circle-embed64 | 2 | 0.064 | +1.64 | +1.51 ± 0.25 | +0.13 ± 0.07 | 2e-16 |
| circle-std1 | 2 | 0.065 | +1.71 | +1.56 ± 0.20 | +0.15 ± 0.12 | 2e-16 |
| digits | 10 | 0.001 | +1.36 | +1.48 ± 0.06 | -0.12 ± 0.09 | 0e+00 |
| digits-2class | 2 | 0.000 | +1.61 | +1.79 ± 0.06 | -0.19 ± 0.09 | 2e-16 |
| digits-noisy | 10 | 0.004 | +1.19 | +1.00 ± 0.47 | +0.19 ± 0.04 | 0e+00 |

largest |internal + output − T*| over all runs: 4.4e-16
