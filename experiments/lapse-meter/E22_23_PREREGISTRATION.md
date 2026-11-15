# Experiments 22–23: which early quantity predicts the collapse? (written before experiment 23's runs)

Written 2026-10-28. Committed to GitHub with `experiments/e23_jobs.txt`, the per-run predictions
`experiments/e23_predictions.json` and `experiments/e23_analyze.py`, before any experiment-23 run.

## Experiment 22 (exploratory: the outcomes were already known)

Four candidates from the literature (see `PRIOR_ART.md`) were measured at initialization, before any step, for
all 180 SGD runs of experiments 8–19 (`experiments/e22_predictors.py`, `results/e22_predictors.json`):

- **readout kick:** RMS change in logits from one SGD step on the readout alone (the μP argument, Yang 2022)
- **preconditioned sharpness:** largest eigenvalue of P^½HP^½ (Gilmer 2022; Kalra & Barkeshli 2024)
- **readout-gradient coherence** (Kosson 2024)
- **blocks' relative first step** (Kosson 2024)
- the pile-up ratio is also reported

The sharpness method was validated against explicit Hessians (`tests/test_e22_predictors.py`). Two method errors
were found and fixed before any analysis: power iteration returned negative eigenvalues, and finite differences
across ReLU kinks gave fake curvatures (CORRECTIONS 35).

"Broken" = transport at loss 0.03 below +0.3, or never trained. AUC for broken, where 1 is perfect and 0.5 is
chance:

| candidate | digits (22 of 90 broken) | circle (9 of 90 broken) |
|---|---|---|
| readout kick | **0.99** | **0.94** |
| preconditioned sharpness | 0.91 | 0.85 |
| pile-up ratio (stream growth) | 0.83 | 0.80 |
| readout-gradient coherence | 0.68 | 0.80 |
| blocks' relative first step | 0.71 | 0.74 |

Kick has a transition band, roughly 100–500, where outcomes depend on the seed. The best single cutoffs, taken
from these data and used below, are:

| task | kick | sharpness |
|---|---|---|
| digits | 328 | 4.07 |
| circle | 124 | 210 |

On the circle the sharpness cutoff hardly beats always guessing "healthy".

The independent replication (`independent/`) agrees with this ordering: its digits networks have the same 37×
pile-up but a kick of 90–150, and they did not collapse.

## Experiment 23 (confirmatory)

New conditions where the candidates disagree. Residual ReLU, width 64, SGD lr 0.05, 6,000 steps, seeds 0–2,
both tasks.

- **C1:** 96 layers (pile-up about 37×), readout learning rate permanently ×0.01 (digits) or ×0.1 (circle).
- **C2:** 96 layers, inputs scaled ×0.1 (digits) or ×0.3 (circle).
- **C3:** 24 layers (pile-up about 5×), inputs scaled ×8 (digits) or ×32 (circle).

The multipliers were chosen from initialization measurements only, to put kick far from its transition band.
`experiments/e23_predictions.json` lists every run's kick, sharpness and pile-up, and what each candidate
predicts for it:

- **kick:** broken if above the task's cutoff
- **sharpness:** broken if above the task's cutoff
- **pile-up ratio:** broken if growth exceeds 20× (between 48 layers, 11×, which survived, and 80 layers, 26×,
  which broke, in experiment 12)

**Outcome per run.** A run is **broken** if any of these holds:

- transport is below +0.3 at the first crossing of training loss 0.03
- it failed to train (final loss above half of ln(classes))

If a run trains but never reaches loss 0.03, the first reached of 0.1 and 0.3 is used instead, and the table
flags it.

**Predictions.**

- **P23a:** C1 is healthy (at least 2 of 3 runs) on both tasks.
- **P23b:** C2 is healthy on both tasks.
- **P23c:** C3 is broken (at least 2 of 3 runs) on both tasks.
- **P23d:** kick's per-run predictions are right in at least 15 of 18 runs, and more often than both sharpness's
  and the pile-up ratio's.

**Decision.** "The readout kick, not the pile-up as such, decides the collapse" is **supported** if P23a–P23d all
hold. It is **refuted** if the pile-up ratio predicts more runs correctly than kick. Anything else is mixed.

One limitation is stated in advance: in C3, very large inputs may break training in ways other than transport
collapse. Both count as broken, and the table reports which.
