| network | seed | measured motion spread | predicted by ‖δ‖·‖h‖/‖W‖ | predicted by actual gradient ‖δᵀh‖/‖W‖ | alignment A spread | A first → last layer |
|---|---|---|---|---|---|---|
| plain-tanh-0.8 | 0 | ×3.8 | ×1.3 | ×1.5 | ×1.3 | 0.191 → 0.244 |
| plain-tanh-0.8 | 1 | ×2.5 | ×1.4 | ×1.4 | ×1.2 | 0.199 → 0.230 |
| plain-tanh-0.8 | 2 | ×2.3 | ×1.7 | ×1.6 | ×1.2 | 0.199 → 0.212 |
| plain-tanh-1.0 | 0 | ×3.2 | ×1.3 | ×1.4 | ×1.4 | 0.173 → 0.244 |
| plain-tanh-1.0 | 1 | ×2.9 | ×1.4 | ×1.3 | ×1.2 | 0.185 → 0.223 |
| plain-tanh-1.0 | 2 | ×3.2 | ×1.9 | ×1.5 | ×1.3 | 0.181 → 0.216 |
| res-tanh | 0 | ×7.8 | ×8.0 | ×7.4 | ×1.1 | 0.212 → 0.227 |
| res-tanh | 1 | ×7.6 | ×7.9 | ×7.4 | ×1.1 | 0.203 → 0.214 |
| res-tanh | 2 | ×8.0 | ×8.3 | ×7.4 | ×1.1 | 0.207 → 0.231 |

correlation of log(actual-gradient prediction) with log(measured motion) across layers: plain-tanh-0.8 s0: 0.52, plain-tanh-0.8 s1: 0.81, plain-tanh-0.8 s2: -0.21, plain-tanh-1.0 s0: -0.80, plain-tanh-1.0 s1: 0.05, plain-tanh-1.0 s2: 0.84, res-tanh s0: 1.00, res-tanh s1: 1.00, res-tanh s2: 1.00

Part 2: every quantity measured on the same steps (the 200 steps of the clock run, same batches).

| network | seed | measured motion spread | ‖δ‖·‖h‖/‖W‖ spread | lr·‖δᵀh‖/‖W‖ spread | alignment spread | max error, lr·‖δᵀh‖/‖W‖ vs motion |
|---|---|---|---|---|---|---|
| plain-tanh-0.8 | 0 | ×3.84 | ×6.64 | ×3.84 | ×1.73 | 3.2e-15 |
| plain-tanh-0.8 | 1 | ×2.54 | ×4.74 | ×2.54 | ×1.96 | 3.3e-15 |
| plain-tanh-0.8 | 2 | ×2.28 | ×4.27 | ×2.28 | ×2.08 | 4.2e-15 |
| plain-tanh-1.0 | 0 | ×3.20 | ×4.11 | ×3.20 | ×1.24 | 4.4e-16 |
| plain-tanh-1.0 | 1 | ×2.94 | ×4.10 | ×2.94 | ×1.34 | 4.4e-16 |
| plain-tanh-1.0 | 2 | ×3.24 | ×4.42 | ×3.24 | ×1.34 | 4.4e-16 |
| res-tanh | 0 | ×7.78 | ×8.14 | ×7.78 | ×1.07 | 7.8e-16 |
| res-tanh | 1 | ×7.59 | ×8.14 | ×7.59 | ×1.08 | 8.9e-16 |
| res-tanh | 2 | ×7.99 | ×8.38 | ×7.99 | ×1.07 | 7.8e-16 |

Part 3: lapse and input activity, each averaged over the same 200 steps (direction: first layer vs last).

| network | seed | lapse spread | lapse first/last | activity spread | activity first/last | product spread |
|---|---|---|---|---|---|---|
| plain-tanh-0.8 | 0 | ×363.1 | 0.00275 | ×114.2 | 63.8 | ×6.73 |
| plain-tanh-0.8 | 1 | ×268.0 | 0.00373 | ×105.0 | 83.8 | ×4.75 |
| plain-tanh-0.8 | 2 | ×234.2 | 0.00427 | ×139.4 | 93.9 | ×4.36 |
| plain-tanh-1.0 | 0 | ×3.0 | 1.93 | ×3.2 | 2.05 | ×4.46 |
| plain-tanh-1.0 | 1 | ×3.0 | 1.95 | ×3.3 | 2.07 | ×4.51 |
| plain-tanh-1.0 | 2 | ×3.0 | 2.15 | ×3.3 | 2.12 | ×4.80 |
| res-tanh | 0 | ×8.2 | 8.2 | ×1.6 | 1.01 | ×8.33 |
| res-tanh | 1 | ×7.9 | 7.92 | ×1.6 | 1.06 | ×8.39 |
| res-tanh | 2 | ×8.3 | 8.25 | ×1.6 | 1.03 | ×8.50 |
