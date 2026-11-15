# Fast Oracle: fixed roots, no adaptive ceiling

Date: 2026-08-29

## Observed problem
The current R transform repeatedly takes square roots until the value falls below 1,000,000, then takes one extra square root. That makes the number of roots depend on magnitude and creates an artificial threshold boundary.

## Research question
Can the Oracle remove the adaptive threshold and apply a fixed transformation to every raw R sample while preserving comparability, logging, and the R-only correlation view?

## Evidence and limitations
This is a deterministic user-defined mathematical experiment, not an empirical claim of predictive validity. A fixed monotonic transform is preferable for comparing changes because every observation receives the same transformation. The underlying recurrence remains modular, so a mathematical upper bound still exists, but there is no additional runtime cutoff or threshold-triggered root.

## 10-level gate result
1. Observed problem: adaptive threshold verified in current code.
2. Foundational evidence: elementary monotonic transformations and deterministic comparability.
3. Current evidence: JavaScript Number safely represents the post-root values.
4. Natural behavior: not applicable.
5. Mechanism: remove threshold loop and apply exactly four square roots.
6. Competing explanation: fixed roots can compress large differences strongly; accepted as part of the experiment.
7. Replication/limitations: deterministic transform can be independently reproduced.
8. Context transfer: same seed and recurrence retained.
9. Implementation mapping: browser R transform, recorder R transform, model tags, and localStorage prediction key.
10. Validation: browser and recorder must return the same fixed-four-root R for the same seed; no threshold conditional may remain.

## Implementation
Raw R remains `(sum(x_n^2))^2` over 1,000 modular recurrence stages. Final displayed/logged R is the result of exactly four successive square roots. There is no `R > threshold` condition.

## Validation criteria
- Exactly four square roots for every sample.
- No adaptive root threshold in browser or recorder.
- R-only correlations remain unchanged in structure.
- New model-specific prediction-history key prevents mixing with adaptive-root results.
- Recorder model tag identifies the fixed-four-root version.
