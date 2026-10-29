# Experiment 53: a prospective test of the divergence boundary (written before any run)

Written 2026-10-29. With the teardown blocked, the account is a feedback loop whose gain is about kick × η|x|². Fitted
on 190 earlier runs (`results/theory_fit.json`), the rule "diverges if kick × η|x|² > 735" was right in 176. The
kick alone, with its best cutoff (1,107), was right in 164.

**New grid**, none of it run before, with `block_nomean = "all"` and 3 seeds per cell (63 runs):

- circle and digits-pca2, input scale ×2, ×4 and ×8;
- digits, input scale ×0.25 and ×0.5;
- readout ×0.3, ×1 and ×3 throughout.

Per-run predictions from both rules are fixed in `experiments/e53_predictions.json`.

**Predictions.**

- **P53a:** the product rule is right in at least 85% of runs.
- **P53b:** it is right in more runs than the kick-alone rule.
