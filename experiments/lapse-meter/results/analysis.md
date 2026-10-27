loaded 144 experiment-1 runs

## Experiment 1: total tilt T = ln N_first, by depth (mean over seeds; trained runs only for T_end)

### digits

| architecture | depth 3 | depth 6 | depth 12 | depth 24 | depth 48 | depth 96 |
|---|---|---|---|---|---|---|
| plain-tanh | -0.8 → **+1.02** (3/3) | -1.0 → **+1.32** (3/3) | -1.4 → **+1.36** (3/3) | -1.8 → **+0.56** (3/3) | failed (3) | failed (3) |
| plain-relu | +0.0 → **+1.28** (3/3) | +0.2 → **+1.70** (3/3) | +0.1 → **+1.46** (3/3) | -0.7 → **+0.16** (2/3) | failed (3) | failed (3) |
| res-tanh | -0.7 → **+0.20** (3/3) | -0.9 → **+0.17** (3/3) | -1.3 → **-0.00** (3/3) | -1.5 → **-0.27** (3/3) | -2.0 → **-0.60** (3/3) | -2.2 → **-0.91** (3/3) |
| res-relu | -0.8 → **+0.27** (3/3) | -1.0 → **+0.10** (3/3) | -1.3 → **-0.12** (3/3) | -1.4 → **-0.39** (3/3) | -1.2 → **-1.12** (3/3) | -0.4 → **-2.09** (3/3) |

### circle

| architecture | depth 3 | depth 6 | depth 12 | depth 24 | depth 48 | depth 96 |
|---|---|---|---|---|---|---|
| plain-tanh | -0.2 → **+2.16** (3/3) | -0.5 → **+2.06** (3/3) | -0.7 → **+2.06** (3/3) | -0.8 → **+2.20** (3/3) | -0.4 → **+2.40** (1/3) | failed (3) |
| plain-relu | +0.0 → **+2.23** (3/3) | -0.1 → **+2.52** (3/3) | -0.4 → **+3.09** (3/3) | -0.5 → **+2.62** (3/3) | -1.6 → **+1.52** (1/3) | failed (3) |
| res-tanh | -0.5 → **+1.06** (3/3) | -0.7 → **+1.12** (3/3) | -1.1 → **+0.90** (3/3) | -1.2 → **+0.57** (3/3) | -1.6 → **+0.31** (3/3) | -2.0 → **-0.09** (3/3) |
| res-relu | -0.9 → **+1.02** (3/3) | -1.2 → **+1.00** (3/3) | -1.4 → **+0.80** (3/3) | -1.6 → **+0.52** (3/3) | -1.6 → **-0.00** (3/3) | -1.6 → **-0.68** (3/3) |

Fit over trained runs: T_end = a + b·depth (a law of conserved total tilt predicts b ≈ 0; a law of conserved per-layer slope predicts T_end ∝ depth)

| task | architecture | depths trained | a | b per layer | T_end spread (max−min of depth means) |
|---|---|---|---|---|---|
| digits | plain-tanh | [3, 6, 12, 24] | +1.38 | -0.0278 | 0.80 |
| digits | plain-relu | [3, 6, 12, 24] | +1.83 | -0.0589 | 1.54 |
| digits | res-tanh | [3, 6, 12, 24, 48, 96] | +0.14 | -0.0121 | 1.11 |
| digits | res-relu | [3, 6, 12, 24, 48, 96] | +0.23 | -0.0250 | 2.36 |
| circle | plain-tanh | [3, 6, 12, 24, 48] | +2.05 | +0.0062 | 0.34 |
| circle | plain-relu | [3, 6, 12, 24, 48] | +2.71 | -0.0124 | 1.57 |
| circle | res-tanh | [3, 6, 12, 24, 48, 96] | +1.05 | -0.0129 | 1.21 |
| circle | res-relu | [3, 6, 12, 24, 48, 96] | +1.03 | -0.0186 | 1.70 |

### Corrected total tilt T* (residual blocks' fixed α factor removed; plain nets unchanged)

**digits**

| architecture | depth 3 | depth 6 | depth 12 | depth 24 | depth 48 | depth 96 | spread over depths ≥ 12 |
|---|---|---|---|---|---|---|---|
| plain-tanh | +1.02 | +1.32 | +1.36 | +0.56 | failed | failed | 0.80 over 2 depths |
| plain-relu | +1.28 | +1.70 | +1.46 | +0.16 | failed | failed | 1.30 over 2 depths |
| res-tanh | +0.75 | +1.06 | +1.24 | +1.32 | +1.33 | +1.37 | 0.13 over 4 depths |
| res-relu | +0.82 | +1.00 | +1.12 | +1.20 | +0.82 | +0.19 | 1.01 over 4 depths |

**circle**

| architecture | depth 3 | depth 6 | depth 12 | depth 24 | depth 48 | depth 96 | spread over depths ≥ 12 |
|---|---|---|---|---|---|---|---|
| plain-tanh | +2.16 | +2.06 | +2.06 | +2.20 | +2.40 | failed | 0.34 over 3 depths |
| plain-relu | +2.23 | +2.52 | +3.09 | +2.62 | +1.52 | failed | 1.57 over 3 depths |
| res-tanh | +1.61 | +2.02 | +2.14 | +2.16 | +2.24 | +2.19 | 0.10 over 4 depths |
| res-relu | +1.57 | +1.89 | +2.04 | +2.11 | +1.93 | +1.60 | 0.51 over 4 depths |


## Experiment 2: does each layer's weight motion follow its lapse?

Per run: slope and correlation of log(relative weight motion per step) against log(lapse) across layers, averaged over the first 200 steps. A literal clock predicts slope ≈ 1 under SGD.

| network | optimiser | slope (mean ± sd over seeds) | correlation r | lapse range across layers |
|---|---|---|---|---|
| plain-tanh-0.8 | adam | 0.06 ± 0.01 | 0.38 | ×6.87 |
| plain-tanh-0.8 | sgd | 0.08 ± 0.04 | 0.49 | ×282 |
| plain-tanh-1.0 | adam | 0.05 ± 0.01 | 0.36 | ×6.38 |
| plain-tanh-1.0 | sgd | 0.68 ± 0.02 | 0.80 | ×3.14 |
| res-tanh | adam | 0.06 ± 0.01 | 0.85 | ×17.5 |
| res-tanh | sgd | 0.94 ± 0.01 | 0.95 | ×7.95 |

Ranges across layers (max/min), SGD runs. Motion under SGD is lr·‖δᵀh‖/‖W‖, so it should follow lapse × input activity; it follows the lapse alone only when activity is uniform.

| network | seed | lapse | input activity (at init) | lapse × activity / ‖W‖ | measured weight motion |
|---|---|---|---|---|---|
| plain-tanh-0.8 | 0 | ×361 | ×509.0 | ×1.4 | ×3.8 |
| plain-tanh-0.8 | 1 | ×269 | ×362.4 | ×1.6 | ×2.5 |
| plain-tanh-0.8 | 2 | ×231 | ×495.3 | ×2.2 | ×2.3 |
| plain-tanh-1.0 | 0 | ×3 | ×8.5 | ×16.3 | ×3.2 |
| plain-tanh-1.0 | 1 | ×3 | ×7.0 | ×14.7 | ×2.9 |
| plain-tanh-1.0 | 2 | ×3 | ×8.6 | ×18.9 | ×3.2 |
| res-tanh | 0 | ×8 | ×1.7 | ×10.6 | ×7.8 |
| res-tanh | 1 | ×8 | ×1.6 | ×10.4 | ×7.6 |
| res-tanh | 2 | ×8 | ×1.7 | ×10.7 | ×8.0 |

## Experiment 3: tiny character-level language model

| model | optimiser | seed | test bits/char start → end | unigram baseline | first layer hears (start → end) | κ end | horizons at end |
|---|---|---|---|---|---|---|---|
| plain | adam | 0 | 6.36 → 4.68 | 4.59 | ×0.809 → ×1.83e-08 (T* -17.82) | +0.7996 | 23/24 |
| residual | adam | 0 | 6.36 → 2.62 | 4.59 | ×0.303 → ×0.648 (T* +1.15) | -0.0727 | 0/23 |
| residual | adam | 1 | 6.35 → 2.69 | 4.59 | ×0.3 → ×0.657 (T* +1.17) | -0.0735 | 0/23 |
| residual | sgd | 0 | 6.36 → 2.79 | 4.59 | ×0.303 → ×0.805 (T* +1.37) | -0.0571 | 0/23 |

Sample, plain adam seed 0:

> ma  rtloitr s o.sice  nnleywnnne oichtteicldetUl rqat d)frY eG ibnHue mteuhelyufohipeoot otw tyu(wtrgYrtaiet ol o oiu s deviaatT biiribesmveils"et rer e naou s eehwpcastidyc:trnvtosa no-etiiEii yi oxkcCnEilv ho.e o etgtrt   tmh,ncofhr iFshy

Sample, residual adam seed 0:

> e Covered SOf imane DTWAROfUVERE PRREVREANT, SERCLTER ICISG, BERANCUNDITITHERmSPROTICINN RTW/ORS ToUR PINGNT LICL the refince the have it, indifin the copyitate not contion any uther the the distribute the version Onterms afile to sombility

Sample, residual adam seed 1:

> e Librily to shall meanys, intent, warranty the X]RAck Cover Aother other maying from the mar. For orantle, you may be inforce a copyright nind to then knat intitle copyright neiubines fyition of it is particulation, but which a copyrightic

Sample, residual sgd seed 0:

> e CoveredPS sage. A. Aequivingat on loweregall of the GLUce de, ir thentations> of the thest trodustrent tor or nermodicaly inge dofyred. You part the copyrofic isconcorgawedowith, a)demaveale ave suin the terman of thith a tomare hou in ov

## Sound pieces

| piece | network | audio | first layer lapse start → end | its pitch start → end | test accuracy start → end |
|---|---|---|---|---|---|
| horizon | 12-layer plain sigmoid, σw 1.0 | 18 s | 2.08e-08 → 2.05e-08 | 1.6 → 1.6 Hz | 0.12 → 0.11 |
| residual | 24-layer residual tanh, σw 1.0 | 18 s | 2.29e-01 → 7.74e-01 | 211.6 → 305.6 Hz | 0.09 → 0.98 |
| settling | 24-layer plain tanh, σw 0.8 | 18 s | 1.80e-03 → 5.75e+00 | 49.3 → 558.7 Hz | 0.06 → 0.97 |
