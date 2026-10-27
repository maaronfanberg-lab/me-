# Experiment 6: is the tilt set by the task, or by how far training has gone? (written before any run)

Written 2026-10-27, before running `experiments/e6.py`. Not edited after results; results go in the README and
`results/e6_analysis.md`.

**What prompted it.** In experiment 4, every condition that raised the trained tilt T* (clean circle labels,
digits relabelled to 2 classes) was also one the network fit almost perfectly (final training loss ≈ 0.000),
and the condition that lowered it most (noisier circle) is one it cannot fit (loss ≈ 0.24). Across runs, T*
correlated with log training loss at r = −0.55. That correlation was found after the fact, so it is a lead,
not a result. One case did not fit the pattern: digits with 20% wrong labels raised T* although its loss was
higher than clean digits.

**Two hypotheses.**

- **H1, fit:** the tilt is set mainly by how well the network currently fits its training data. Lower training
  loss, steeper tilt, whatever the task.
- **H2, classes:** the number of output classes sets the tilt directly, independent of fit.

**Design.** Residual tanh, 24 hidden layers, width 64, α = 1/√24 removed (T* as in experiments 1 and 4), SGD
lr 0.05, batch 64, 6,000 steps, 3 seeds. T* and the full training loss are logged every 100 steps.
Conditions: circle-clean, circle (noise 0.15), circle-noisier (0.30); digits with 10, 5 (digit // 2),
3 (digit mod 3) and 2 (digit ≥ 5) classes; digits with 20% wrong labels.

**Matched-loss comparison.** For each run, T* is read at the first logged step where the training loss falls
below each level L* in {0.3, 0.1, 0.03, 0.01} (linear interpolation between the two logs that bracket it, in
log-loss). Runs that never reach a level are excluded at that level and reported.

**Predictions and pass rule.** A difference "persists" if |Δ| > 2 × sqrt(sd₁² + sd₂²) over seeds (the same
rule as experiment 4).

- *Within runs (H1):* in every condition, T* rises as training loss falls. Pass if the Spearman correlation
  between T* and log loss over each run's logs is negative in at least 20 of the 24 runs.
- *Across tasks at matched loss (H1):* circle-clean vs circle vs circle-noisier, and digits vs digits-noisy, do
  **not** persist at any matched level where both are present. H1 fails if two or more of these persist.
- *Class count at matched loss (H2):* at matched loss, T* falls monotonically from 2 to 3 to 5 to 10 classes,
  and the 2-vs-10 difference persists. H2 fails if the 2-vs-10 difference does not persist at matched loss.

Both can hold (fit and classes each contribute), or neither.
