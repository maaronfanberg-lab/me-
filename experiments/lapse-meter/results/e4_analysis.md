# Experiment 4 results

### residual tanh, 24 layers (α removed)

| condition | inputs | classes | runs counted | test acc | final train loss | T* (mean ± sd) | Δ from baseline | moves? |
|---|---|---|---|---|---|---|---|---|
| circle | 2 | 2 | 3/3 | 0.975 | 0.071 | +2.16 ± 0.11 | baseline |  |
| circle-clean | 2 | 2 | 3/3 | 1.000 | 0.000 | +3.05 ± 0.28 | +0.89 (threshold 0.60) | **yes** |
| circle-noisier | 2 | 2 | 3/3 | 0.929 | 0.242 | +1.42 ± 0.15 | -0.74 (threshold 0.37) | **yes** |
| circle-embed64 | 64 | 2 | 3/3 | 0.975 | 0.070 | +1.88 ± 0.09 | -0.28 (threshold 0.29) | no |
| circle-pad62noise | 64 | 2 | 0/3 | 0.506 | nan | +nan ± nan | – | too few runs |
| circle-std1 | 2 | 2 | 3/3 | 0.973 | 0.070 | +2.02 ± 0.10 | -0.15 (threshold 0.30) | no |
| digits | 64 | 10 | 3/3 | 0.976 | 0.002 | +1.32 ± 0.06 | baseline |  |
| digits-2class | 64 | 2 | 3/3 | 0.967 | 0.000 | +2.37 ± 0.06 | +1.06 (threshold 0.17) | **yes** |
| digits-pca2 | 2 | 10 | 0/3 | 0.563 | nan | +nan ± nan | – | too few runs |
| digits-noisy | 64 | 10 | 3/3 | 0.804 | 0.016 | +2.07 ± 0.04 | +0.75 (threshold 0.13) | **yes** |

### plain tanh, 12 layers

| condition | inputs | classes | runs counted | test acc | final train loss | T* (mean ± sd) | Δ from baseline | moves? |
|---|---|---|---|---|---|---|---|---|
| circle | 2 | 2 | 3/3 | 0.977 | 0.065 | +2.06 ± 0.25 | baseline |  |
| circle-clean | 2 | 2 | 3/3 | 1.000 | 0.000 | +2.84 ± 0.22 | +0.78 (threshold 0.67) | **yes** |
| circle-noisier | 2 | 2 | 3/3 | 0.935 | 0.208 | +1.44 ± 0.39 | -0.63 (threshold 0.93) | no |
| circle-embed64 | 64 | 2 | 3/3 | 0.977 | 0.064 | +1.64 ± 0.28 | -0.42 (threshold 0.76) | no |
| circle-pad62noise | 64 | 2 | 0/3 | 0.481 | nan | +nan ± nan | – | too few runs |
| circle-std1 | 2 | 2 | 3/3 | 0.975 | 0.065 | +1.71 ± 0.30 | -0.36 (threshold 0.79) | no |
| digits | 64 | 10 | 3/3 | 0.972 | 0.001 | +1.36 ± 0.13 | baseline |  |
| digits-2class | 64 | 2 | 3/3 | 0.973 | 0.000 | +1.61 ± 0.14 | +0.25 (threshold 0.38) | no |
| digits-pca2 | 2 | 10 | 0/3 | 0.561 | nan | +nan ± nan | – | too few runs |
| digits-noisy | 64 | 10 | 3/3 | 0.784 | 0.004 | +1.19 ± 0.45 | -0.17 (threshold 0.93) | no |

Across all counted res24 runs: correlation of T* with log(final train loss) r = -0.55 (n = 24)

Across all counted plain12 runs: correlation of T* with log(final train loss) r = -0.32 (n = 24)
