# Experiment 26: does normalizing the readout's input protect, as the kick account predicts? (written before any run)

Written 2026-10-28, before any experiment-26 run. While writing it I had seen the first 8 of experiment 24's 48
runs (digits, caps 3–30, all healthy). Committed with `lapse/nets_ln.py`, `tests/test_nets_ln.py`,
`experiments/e26_jobs.txt`, `experiments/e26_predictions.json` and `experiments/e26_analyze.py`.

## Why

Real networks avoid this collapse with normalization (Xiong et al. 2020). Kalra & Barkeshli 2024 also single out
"Transformers with the last layer-norm removed". The kick account says normalization helps because it bounds the
readout's input, and with it the readout kick, not because it removes the pile-up.

## Networks

`lapse/nets_ln.py`: the one-matrix ReLU blocks of experiments 8–24 with LayerNorm (no learned gain or bias) in
one of four places:

- **final:** before the readout
- **pre:** on each block's input, with no final LayerNorm
- **pre_final:** both, the usual Pre-LN transformer arrangement
- **post:** after each residual addition, Post-LN

All gradients are checked by finite differences (13 checks), and ln="none" equals the original network bit for
bit, including a full training run.

At initialization (96 layers, seeds 0–2), measured before writing this:

| placement | stream pile-up (plain) | shared-vector share | kick, digits | kick, circle |
|---|---|---|---|---|
| final | 37× | 72–77% | 0.65–0.89 | 0.19–1.6 |
| pre | 6–13× | 96–98% | 42–55 | 9–36 |
| pre_final | 6–13× | 96–98% | 0.16–0.19 | 0.11–0.39 |
| post | none | 2–14% | 0.17–0.19 | 0.24–0.40 |

Every kick is below the cutoffs fixed in experiment 22 (digits 328, circle 124). So the kick account predicts
every normalized network here is **healthy**. The pile-up account predicts "final" and "pre" break, since their
streams are as piled up as plain ReLU's or more. Xiong et al.'s account (for transformers trained with Adam)
predicts Post-LN is the unstable arrangement.

## Comparison

LayerNorm changes the scale of transport, so the plain-ReLU threshold of +0.3 does not transfer. Each ReLU network
is compared with its **signed-ReLU twin** in the same placement: same weights, ReLU's exact gates, a fixed random
± sign per unit, no pile-up.

- **Healthy:** the ReLU mean transport is not below the twin's by more than 2·sqrt(sd₁² + sd₂²), and no more runs
  failed to train than the twin's.
- **Level:** the lowest of training loss 0.03, 0.1 and 0.3 that both groups reach in at least 2 runs.

**Design.** 96 layers, width 64, SGD lr 0.05, 6,000 steps, seeds 0–2, digits and the clean circle: 4 placements
× {ReLU, signed} × 2 tasks × 3 seeds = 48 runs. Plus a stress case: ReLU at 192 layers in "pre" and "pre_final"
(12 runs, kicks 37–106 and 0.1–0.3), reported, not tested.

## Predictions (kick account)

- **P26a:** final is healthy on both tasks. This is the key test: the full 37× pile-up with a tiny kick.
- **P26b:** pre is healthy on both tasks.
- **P26c:** pre_final is healthy on both tasks.
- **P26d:** post is healthy on both tasks.

## Decision

"The readout kick, not the pile-up, is what normalization controls" is **supported** if P26a and P26b hold on both
tasks. It is **refuted** if P26a fails on both tasks.

## Limits stated in advance

- Every normalized network here has a small kick, so this experiment cannot show the kick predicting a break inside
  normalized networks. That would need something like 650 layers in the "pre" arrangement.
- On the circle, inputs near the origin make LayerNorm divide by an almost-zero spread, giving very large
  curvature (sharpness up to about 10⁵). This affects both twins.
- No learned LayerNorm gain or bias; SGD, not Adam.
