# Experiment 48: bound every step's kick, the μP-like way (written before any run)

Written 2026-10-29, after experiment 47. Committed with `ci/e48.txt` and `experiments/e48_analyze.py` before any run.

**Fix.** `out_lr_norm = 64`. At every step the readout's learning rate is multiplied by 64 / mean_i |h_i|² on that
minibatch (64 is the width). A healthy, unpiled stream (|h|² about the width) keeps its learning rate. A piled-up
stream's readout steps shrink in proportion, so the kick, about η·|h|²·|d|, stays bounded at every step. Unlike the
kick cap, this needs no threshold.

**Design.** Plain residual ReLU, seeds 0–4, 25 runs:

- digits, 96 layers;
- circle, 96 layers;
- language model, inputs ×10, 96 layers;
- digits, 192 layers;
- language model, inputs ×1.

The outcome rule is experiment 47's.

**Predictions.**

- **P48a:** healthy on digits, circle and the language model ×10, all at 96 layers.
- **P48b:** healthy at 192 layers.
- **P48c:** healthy on the language model ×1.
