# Experiment 40: the second route to divergence (written before any run)

Written 2026-10-29, after experiment 39. Committed with `ci/e40.txt` and `experiments/e40_analyze.py` before any run.

**Background.** With the teardown blocked (`block_nomean = "all"`) and the input layer frozen, digits still diverged
at readout ×10 (5 of 5 runs). Two candidate routes:

- **Readout alone:** the readout diverges by itself at 10× its learning rate.
- **Blocks:** the blocks' example-specific updates grow the stream.

**Conditions.** 96 layers, `block_nomean = "all"`, seeds 0–4, 20 runs:

- **A:** input layer and blocks frozen (only the readout learns), digits ×10.
- **A3:** the same at ×3.
- **B:** input layer frozen, blocks at 0.1× their learning rate, digits ×10.
- **A-std1:** condition A on circle-std1 ×10, which diverged in experiment 39.

**Predictions.**

- **P40a (my bet, about 60%: readout alone):** A diverges in at least 3 of 5 runs. If it does not, the blocks are
  the route.
- **P40b:** A3 does not diverge (frozen digits at ×3 diverged in only 1 of 5 runs in experiment 39).
- **Reported:** B and A-std1.
