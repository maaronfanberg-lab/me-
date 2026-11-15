# Experiment 4: what sets the total tilt? (written before any run)

Written 2026-10-27, before running `experiments/e4.py`. Not edited after results came in; results are reported
in the README and `results/e4_analysis.md`.

**Observation to explain.** Trained tanh networks settle at a corrected total tilt T* that does not depend on
depth (12–96 layers) but does depend on the task: about +1.3 on digits, +1.2 to +1.4 on the tiny language model,
and +2.2 on the noisy circle.

**Three candidate causes, and how the tasks differ on each.**

| factor | digits | circle | language model |
|---|---|---|---|
| input dimension | 64 | 2 | 1,312 |
| number of classes | 10 | 2 | 82 |
| label noise | none | yes (labels jittered at the boundary) | some (text is not deterministic) |

**Conditions** (each changes one thing from a baseline):

| condition | changes |
|---|---|
| circle | baseline: 2 inputs, 2 classes, noise 0.15 |
| circle-clean | label noise 0 |
| circle-noisier | label noise 0.30 |
| circle-embed64 | the same 2-D point mapped into 64 inputs by a fixed random orthonormal map (same information, 64 inputs) |
| circle-pad62noise | 2 real inputs plus 62 pure-noise inputs |
| circle-std1 | the same circle with each input standardised to spread 1 (digits inputs have spread 1; circle inputs 0.44) |
| digits | baseline: 64 inputs, 10 classes, clean labels |
| digits-2class | label = digit ≥ 5 (2 classes, same inputs) |
| digits-pca2 | inputs reduced to their top 2 principal components (2 inputs, 10 classes) |
| digits-noisy | 20% of training labels replaced at random |

Networks: residual tanh, 24 layers (α = 1/√24, corrected tilt reported), and plain tanh, 12 layers. Width 64,
SGD lr 0.05, batch 64, 4,000 steps, 3 seeds. Every run is reported with its accuracy. T* is averaged only over
runs that reach at least 70% test accuracy, measured against clean test labels (chance is 50% on the circle and
2-class tasks, 10% on the others).

**Added before running, after a data check:** circle inputs have spread 0.44 while digit inputs are standardised
to 1.0, so input scale is a fourth candidate. *If input scale sets it:* circle-std1 moves toward digits
(Δ ≈ −0.9) and circle-embed64 (which keeps spread 0.44) does not move.

**Predictions.** Let Δ be the change in T* from that condition's baseline.

- *If input dimension sets it:* circle-embed64 and circle-pad62noise move toward digits (Δ ≈ −0.9);
  digits-pca2 moves toward circle (Δ ≈ +0.9). Class count and noise changes give |Δ| small.
- *If class count sets it:* digits-2class moves toward circle (Δ ≈ +0.9); the circle variants barely move.
- *If label noise sets it:* circle-clean drops (Δ < 0), circle-noisier rises (Δ > 0), digits-noisy rises (Δ > 0);
  embedding and class changes barely move it.
- *If none of these:* no condition moves T* by more than the seed spread (about ±0.15).

"Moves" means |Δ| larger than twice the seed standard deviation of the two conditions combined.
