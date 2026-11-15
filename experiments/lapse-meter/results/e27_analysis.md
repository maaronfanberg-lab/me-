# Experiment 27 results

**Verdicts:** P27a fails, P27b holds. Damage in the first two readout updates: **mixed**.

k=1: digits 2/3 healthy, circle 1/3; k=2: digits 1/3 healthy, circle 1/3; k=3: digits 3/3 healthy, circle 1/3; k=5: digits 3/3 healthy, circle 3/3; k=10: digits 3/3 healthy, circle 2/3;

| task | window k | seed | steps the cap bound | transport | final loss | observed |
|---|---|---|---|---|---|---|
| digits | 1 | 0 | [0] | +0.41 | 0.0036 | **healthy** |
| digits | 1 | 1 | [0] | +0.70 | 0.0039 | **healthy** |
| digits | 1 | 2 | [0] | +0.13 | 0.0118 | **broken** |
| digits | 2 | 0 | [0, 1] | -0.11 | 0.0029 | **broken** |
| digits | 2 | 1 | [0, 1] | +0.57 | 0.0038 | **healthy** |
| digits | 2 | 2 | [0, 1] | +0.17 | 0.0041 | **broken** |
| digits | 3 | 0 | [0, 1, 2] | +0.57 | 0.0029 | **healthy** |
| digits | 3 | 1 | [0, 1, 2] | +0.55 | 0.0031 | **healthy** |
| digits | 3 | 2 | [0, 1, 2] | +0.41 | 0.0041 | **healthy** |
| digits | 5 | 0 | [0, 1, 2, 3, 4] | +0.67 | 0.0007 | **healthy** |
| digits | 5 | 1 | [0, 1, 2, 3, 4] | +0.68 | 0.0007 | **healthy** |
| digits | 5 | 2 | [0, 1, 2, 3, 4] | +0.71 | 0.0007 | **healthy** |
| digits | 10 | 0 | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | +0.78 | 0.0006 | **healthy** |
| digits | 10 | 1 | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | +0.66 | 0.0007 | **healthy** |
| digits | 10 | 2 | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | +0.69 | 0.0006 | **healthy** |
| circle-clean | 1 | 0 | [0] | +0.04 | 0.0018 | **broken** |
| circle-clean | 1 | 1 | [0] | -0.00 | 0.0017 | **broken** |
| circle-clean | 1 | 2 | [0] | +0.85 | 0.0017 | **healthy** |
| circle-clean | 2 | 0 | [0, 1] | +0.20 | 0.0018 | **broken** |
| circle-clean | 2 | 1 | [0, 1] | +0.09 | 0.0017 | **broken** |
| circle-clean | 2 | 2 | [0, 1] | +0.30 | 0.0017 | **healthy** |
| circle-clean | 3 | 0 | [0, 1, 2] | +0.15 | 0.0017 | **broken** |
| circle-clean | 3 | 1 | [0, 1, 2] | +0.03 | 0.0017 | **broken** |
| circle-clean | 3 | 2 | [0, 1, 2] | +1.16 | 0.0009 | **healthy** |
| circle-clean | 5 | 0 | [0, 1, 2, 3, 4] | +1.09 | 0.0010 | **healthy** |
| circle-clean | 5 | 1 | [0, 1, 2, 3, 4] | +0.43 | 0.0013 | **healthy** |
| circle-clean | 5 | 2 | [0, 1, 2, 3, 4] | +1.19 | 0.0006 | **healthy** |
| circle-clean | 10 | 0 | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | +1.10 | 0.0007 | **healthy** |
| circle-clean | 10 | 1 | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] | -0.01 | 0.0013 | **broken** |
| circle-clean | 10 | 2 | [0, 1, 2, 3, 4, 5, 6, 7, 8] | +1.22 | 0.0005 | **healthy** |
