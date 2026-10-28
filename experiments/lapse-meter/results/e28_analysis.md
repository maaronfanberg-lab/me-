# Experiment 28 results (language model)

**Verdicts:** P28a holds, P28b holds, P28c holds, P28d holds. Kick account on language modelling: **carries over**.

| prediction | ReLU condition | twin | level (nats) | ReLU transport | twin transport | ReLU below twin? (gap / threshold) | failed, ReLU / twin | final train loss, ReLU / twin | final test loss, ReLU / twin | observed | predicted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P28a | relu_x1 | signed_x1 | 1.0 | +2.66 ± 0.12 (3/3) | +1.78 ± 0.04 (3/3) | no (+0.88 / 0.25) | 0 / 0 | 0.852 / 0.266 | 7.858 / 5.184 | **healthy** | healthy |
| P28b | relu_x10 | signed_x10 | – | – | – | – | 1 / 0 | 3.167 / 0.018 | 3.310 / 6.311 | **broken** | broken |
| P28c | relu_x10_cap10 | signed_x10 | 2.0 | +0.74 ± 0.04 (3/3) | +0.26 ± 0.02 (3/3) | no (+0.48 / 0.09) | 0 / 0 | 1.754 / 0.018 | 4.015 / 6.311 | **healthy** | healthy |
| P28d | relu_x10_finalLN | signed_x10_finalLN | 1.0 | +0.66 ± 0.03 (3/3) | +0.50 ± 0.02 (3/3) | no (+0.17 / 0.08) | 0 / 0 | 0.044 / 0.032 | 4.836 / 4.637 | **healthy** | healthy |

Per-run rule (kick above 124 = broken) right in 18 of 21 runs.
