# Experiment 38: why the circle never diverges, class count or input size? (written before any run)

Written 2026-10-28, after experiment 37. Committed with `ci/e38.txt` and `experiments/e38_analyze.py` before any run.

With the teardown blocked (`block_nomean = "all"`), digits diverges above a kick of about 600, and the circle never
does, up to 5,403 (experiment 37). Two differences between the tasks are tested:

- class count: 10 against 2;
- input size: 64 against 2.

**Design.**

- Two existing variants (`e4.make`):
  - `digits-2class`: digits' 64 inputs, 2 classes;
  - `circle-embed64`: the circle embedded in 64 inputs, 2 classes.
- 96 layers, `block_nomean = "all"`, readout learning rate ×1, ×3 and ×10, seeds 0–4: 30 runs.
- A variant **diverges** if at least 3 of its 5 runs at ×10 diverge.

**Accounts.**

- **Class count:** neither variant diverges, because both have 2 classes.
- **Input size:** both diverge, because both have 64 inputs.
- **Both needed:** neither diverges.

**Prediction (my bet, about 55%): class count.** Neither variant diverges at ×10. If both diverge, input size is
supported. If only one diverges, the result is **mixed**. Kicks are reported per run.
