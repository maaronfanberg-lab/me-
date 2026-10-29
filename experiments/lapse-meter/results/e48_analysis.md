# Experiment 48 results

**Verdicts:** P48a (healthy at 96 layers: digits, circle, language model x10): fails; P48b (healthy at 192 layers): holds; P48c (healthy on the language model x1): holds.

| setting | condition | runs | mean transport (healthy-rule level) | test accuracy |
|---|---|---|---|---|
| d96 | norm | 5 healthy, 0 diverged of 5 | +0.89 | 0.981 |
| c96 | norm | 5 healthy, 0 diverged of 5 | +1.66 | 1.000 |
| lm10 | norm | 0 healthy, 0 diverged of 5 | – | 0.189 |
| d192 | norm | 5 healthy, 0 diverged of 5 | +0.77 | 0.969 |
| lm1 | norm | 5 healthy, 0 diverged of 5 | +2.70 | 0.238 |
