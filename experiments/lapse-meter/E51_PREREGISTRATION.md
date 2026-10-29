# Experiment 51: normalize the input layer too (written before any run)

Written 2026-10-29, after experiment 50. Committed with `ci/e51.txt` and `experiments/e51_analyze.py` before any run.

**Background.** Readout normalization alone fails on the language model ×10 at every constant from 4 to 16,384
(experiments 49–50). Experiment 39 found that input scale acts through the input layer.

**Fix.** At every step, scale the input layer's learning rate by c_in / mean |x|². One-hot inputs ×1 have |x|² = 16,
and ×10 have 1,600.

- c_in = 16 restores the ×1 input-layer step size.
- c_in = 160 is a 10× larger step.

**Design.** Language model ×10, `out_lr_norm = 64`, c_in ∈ {16, 160}, seeds 0–4, 10 runs, pinned corpus. Outcome
rule as in experiment 48.

**Predictions.**

- **P51a (about 55%):** c_in = 16 is healthy in at least 3 of 5 runs.
- **P51b:** c_in = 160 is healthy in fewer runs than c_in = 16.
