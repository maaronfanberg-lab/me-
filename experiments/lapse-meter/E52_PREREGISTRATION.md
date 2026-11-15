# Experiment 52: the combined fix everywhere, on new seeds (written before any run)

Written 2026-10-29, after experiment 51. Committed with `ci/e52.txt` and `experiments/e52_analyze.py` before any run.

**Fix.** Each step, the readout's learning rate is scaled by 64 / mean |h|² and the input layer's by 16 / mean |x|².

**Design.**

- Plain residual ReLU, new seeds 5–9.
- Five settings: digits at 96 layers, circle at 96, digits at 192, language model ×1, language model ×10.
- 25 runs on the pinned corpus. Outcome rule as in experiment 48.

**Prediction. P52:** healthy in at least 3 of 5 runs in every setting.

The input-layer half could hurt settings that did not need it. It slows digits' input layer (|x|² about 61) to 0.26×
its usual rate. That is the risk this tests.
