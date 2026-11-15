# Experiment 35 results

**Verdicts:** P35a (nomean prevents the teardown, both tasks): fails; P35b (nomean diverges on digits): holds; P35c (nomean + cap 10 healthy, both tasks): holds.

**Decision (digits):** the teardown is void (the teardown is carried by the inherited part).

| task | condition | seed | stream step 5 / step 0 | transport | last step | final loss | state |
|---|---|---|---|---|---|---|---|
| digits | plain | 0 | 0.056 | +0.05 | 6000 | 0.004329 | **broken** |
| digits | plain | 1 | 0.058 | +0.26 | 6000 | 0.009121 | **broken** |
| digits | plain | 2 | 0.058 | +0.04 | 6000 | 0.01188 | **broken** |
| digits | plain | 3 | 0.064 | +0.05 | 6000 | 0.007443 | **broken** |
| digits | plain | 4 | 0.084 | +0.04 | 6000 | 0.1357 | **broken** |
| digits | nomean | 0 | 11.095 | – | 0 | 57.77 | **diverged** |
| digits | nomean | 1 | 0.967 | – | 6000 | 1.674 | **broken** |
| digits | nomean | 2 | 1.516 | – | 0 | 41.38 | **diverged** |
| digits | nomean | 3 | 4.027 | – | 0 | 44.19 | **diverged** |
| digits | nomean | 4 | 2.672 | – | 0 | 24.11 | **diverged** |
| digits | nomean_cap10 | 0 | 0.538 | +0.80 | 6000 | 0.01661 | **healthy** |
| digits | nomean_cap10 | 1 | 0.589 | +0.86 | 6000 | 0.07124 | **healthy** |
| digits | nomean_cap10 | 2 | 0.649 | +0.42 | 6000 | 0.01595 | **healthy** |
| digits | nomean_cap10 | 3 | 0.653 | +1.52 | 6000 | 0.01479 | **healthy** |
| digits | nomean_cap10 | 4 | 0.807 | +1.55 | 6000 | 0.0003011 | **healthy** |
| circle-clean | plain | 0 | 0.055 | +0.04 | 6000 | 0.001844 | **broken** |
| circle-clean | plain | 1 | 0.208 | +0.12 | 6000 | 0.00167 | **broken** |
| circle-clean | plain | 2 | 0.047 | +0.04 | 6000 | 0.00176 | **broken** |
| circle-clean | plain | 3 | 0.076 | +0.01 | 6000 | 0.001724 | **broken** |
| circle-clean | plain | 4 | 0.065 | +0.00 | 6000 | 0.001716 | **broken** |
| circle-clean | nomean | 0 | 0.247 | +0.00 | 6000 | 0.001689 | **broken** |
| circle-clean | nomean | 1 | 0.415 | +0.00 | 6000 | 0.001689 | **broken** |
| circle-clean | nomean | 2 | 0.137 | +0.22 | 6000 | 0.001729 | **broken** |
| circle-clean | nomean | 3 | 0.260 | +0.00 | 6000 | 0.001688 | **broken** |
| circle-clean | nomean | 4 | 0.230 | +0.00 | 6000 | 0.001689 | **broken** |
| circle-clean | nomean_cap10 | 0 | 0.920 | +1.76 | 6000 | 0.001706 | **healthy** |
| circle-clean | nomean_cap10 | 1 | 0.944 | +1.70 | 6000 | 0.001716 | **healthy** |
| circle-clean | nomean_cap10 | 2 | 0.857 | +1.79 | 6000 | 0.001706 | **healthy** |
| circle-clean | nomean_cap10 | 3 | 0.943 | +1.54 | 6000 | 0.001695 | **healthy** |
| circle-clean | nomean_cap10 | 4 | 0.894 | +1.56 | 6000 | 0.001711 | **healthy** |
