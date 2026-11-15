# Experiment 47: a free fix: start the readout at zero, with its bias at the class priors (written before any run)

Written 2026-10-29. Committed with `ci/e47.txt` and `experiments/e47_analyze.py` before any run.

**Fix.** `zero_out` sets readout weights to 0. `out_bias_prior` sets the readout bias to the log class frequencies.
Every example's prediction then starts at the class priors, so the shared error is exactly zero at step 0. Measured
on seed 0 before writing this:

| setting | plain kick | zero | zero + prior |
|---|---|---|---|
| digits, 96 layers | 2,396 | 123 | 121 |
| circle, 96 layers | 108 | 123 | 137 |
| language model ×10 inputs, 96 layers | 3,196 | 767 | 120 |
| digits, 192 layers | 63,137 | – | 3,295 |

**Design.**

- Four settings: digits 96, circle 96, language model inputs ×10 at 96 layers, and digits 192.
- Three conditions each: plain, zero, and zero + prior.
- Seeds 0–4: 60 runs.

**Outcome.**

- Broken if transport at the first loss level reached is below +0.3. Levels: 0.03, 0.1, 0.3 for the
  classifiers; 1.0, 1.5, 2.0, 2.5, 3.0 for the language model.
- Also broken if the run reaches no level, fails to train or diverges.
- A cell is healthy if at least 3 of 5 runs are.
- Test accuracy is reported.

**Predictions.**

- **P47a:** zero + prior is healthy on digits 96, circle 96 and the language model ×10.
- **P47b:** zero + prior is broken on digits 192. Its kick is still 3,295, because the pile-up's example-specific
  part grows with depth.
- **P47c:** zero alone is healthy on digits 96 and broken on the language model ×10 (kick 767).
- **Plain:** broken in all four settings, as in experiments 8, 28 and 43.

**Decision.** The fix is **supported** where P47a holds. P47b marks its limit.
