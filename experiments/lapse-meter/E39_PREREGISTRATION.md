# Experiment 39: input dimension or input scale? And does the divergence travel through the input layer? (written before any run)

Written 2026-10-28, after experiment 38. Committed with `ci/e39.txt` and `experiments/e39_analyze.py` before any run.

**Why.** In experiment 38, `circle-embed64` changed both the dimension (2 → 64) and the input scale: its RMS
input norm is 3.51, against 0.62 for the circle (measured before writing this). Digits' is 7.83.

**Design.**

- 96 layers, `block_nomean = "all"`, readout ×1, ×3 and ×10, seeds 0–4: 90 runs.
- Variants, with their input norm:
  - `circle-embed64u`: 64 dimensions at the circle's own scale (0.62). This is new, the embedding without the √32.
  - `circle-std1`: 2 dimensions (1.41).
  - `digits-pca2`: 2 dimensions, 10 classes (1.41).
  - `circle-pad62noise`: 64 dimensions, 62 of them noise (7.84).
- Two mechanism conditions, with the input layer frozen (`freeze: ["in"]`):
  - digits;
  - circle-embed64.
- A condition **diverges** at a multiplier if at least 3 of its 5 runs do.

**Predictions.**

- **P39a (decisive; my bet, about 60%: scale).** circle-embed64u does not diverge at ×10. If it diverges, dimension
  is supported.
- **P39b.** circle-pad62noise diverges at ×10. Both accounts predict this.
- **P39c (mechanism; about 50%).** Freezing the input layer prevents divergence at ×1 for digits and at ×3 for
  circle-embed64, the multipliers where both diverged in experiments 37 and 38.
- **Reported:** circle-std1 and digits-pca2 at every multiplier.
