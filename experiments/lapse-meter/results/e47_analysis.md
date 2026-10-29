# Experiment 47 results

**Verdicts:** P47a (zero + prior healthy at 96 layers, three tasks): fails; P47b (not at 192 layers): holds; P47c (zero alone: digits yes, language model no): fails.

| setting | condition | runs | mean transport (healthy-rule level) | test accuracy |
|---|---|---|---|---|
| d96 | plain | 0 healthy, 0 diverged of 5 | +0.09 | 0.931 |
| d96 | zero | 0 healthy, 0 diverged of 5 | +0.07 | 0.948 |
| d96 | zeroprior | 0 healthy, 0 diverged of 5 | +0.07 | 0.946 |
| c96 | plain | 0 healthy, 0 diverged of 5 | +0.04 | 1.000 |
| c96 | zero | 5 healthy, 0 diverged of 5 | +1.41 | 1.000 |
| c96 | zeroprior | 5 healthy, 0 diverged of 5 | +1.45 | 1.000 |
| lm10 | plain | 0 healthy, 0 diverged of 5 | – | 0.189 |
| lm10 | zero | 0 healthy, 0 diverged of 5 | – | 0.187 |
| lm10 | zeroprior | 0 healthy, 0 diverged of 5 | – | 0.187 |
| d192 | plain | 0 healthy, 0 diverged of 5 | -0.00 | 0.941 |
| d192 | zero | 0 healthy, 0 diverged of 5 | +0.01 | 0.936 |
| d192 | zeroprior | 0 healthy, 0 diverged of 5 | +0.01 | 0.940 |
