# Experiment 37: with the teardown blocked, does the kick's size alone decide divergence? (written before any run)

Written 2026-10-28, after experiment 36. Committed with `ci/e37.txt` and `experiments/e37_analyze.py` before any run.

**Reading under test (from experiment 36).** The teardown averts divergence only when the step-one kick is too
large for the readout to absorb. With the teardown blocked (`block_nomean = "all"`), a network diverges if and only
if its kick is large.

**Design.**

- 96 layers, `block_nomean = "all"`, both tasks, seeds 0–4.
- The readout learning rate is multiplied by m ∈ {0.1, 0.3, 1, 3, 10} (`out_lr_mult`, permanent), which scales the
  step-one kick by m: digits from about 160 to 24,000, circle from about 11 to 3,700.

**Predictions.**

- **P37a:** digits at m = 0.1 (kick 164–240) does not diverge, in at least 3 of 5 runs.
- **P37b:** circle at m = 10 (kick 1,080–3,690) diverges, in at least 3 of 5 runs.
- **P37c:** across all 50 runs, divergence is predicted by the kick alone, with one cutoff shared by both tasks.
  The best single cutoff classifies at least 45 of 50 runs.

**Decision.** The reading is **supported** if P37a–P37c all hold, and **refuted** if both P37a and P37b fail.
