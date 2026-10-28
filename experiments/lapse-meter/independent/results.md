# Independent replication results

| task | condition | transport at loss 0.03, per seed | mean | prediction | holds? | test accuracy |
|---|---|---|---|---|---|---|
| digits | plain | +1.13, +1.28, +1.26 | +1.22 | R1: below +0.30 | **fails** | 0.977 |
| digits | warm50 | +1.58, +1.48, +1.45 | +1.50 | R2: above +0.50 | **holds** | 0.989 |
| digits | warmout | +1.63, +1.64, +1.48 | +1.58 | R3: above +0.50 | **holds** | 0.986 |
| digits | signed | +1.27, +1.22, +1.27 | +1.25 | R4: above +0.50 | **holds** | 0.990 |
| circle | plain | +0.00, +0.37, -0.00 | +0.12 | R1: below +0.30 | **holds** | 1.000 |
| circle | warm50 | +0.87, +0.84, +0.97 | +0.90 | R2: above +0.50 | **holds** | 1.000 |
| circle | warmout | +1.03, +1.04, +1.26 | +1.11 | R3: above +0.50 | **holds** | 1.000 |
| circle | signed | +1.08, +0.94, +0.97 | +1.00 | R4: above +0.50 | **holds** | 1.000 |
