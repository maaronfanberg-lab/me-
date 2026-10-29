# Experiment 36: block every route for the mean shift (written before any run)

Written 2026-10-28, after experiment 35. Committed with `ci/e36.txt` and `experiments/e36_analyze.py` before any run.

Experiment 35 blocked the blocks' own mean shift but left the input layer free. On the circle the teardown still
happened, through the stream feeding each block. `block_nomean = "all"` also projects the input layer's update, so
no layer's own update can shift its minibatch-mean pre-activation.

**Design and measures.** As experiment 35: 96 layers, both tasks, seeds 0–4. Teardown = last stream at step 5
below 25% of step 0. Healthy, broken and diverged as before. A condition takes the state at least 3 of its 5 runs
show.

**Predictions.**

- **P36a:** nomeanall prevents the teardown on both tasks.
- **P36b (my bet, about 60%):** it diverges on digits, as in experiment 35. On the circle I bet diverge too, at about
  55%; that is reported, not tested.
- **P36c:** with kick cap 10 it is healthy on both tasks.

**Decision.**

- If the teardown is prevented on both tasks and digits diverges, the teardown is **the escape**.
- If the teardown is prevented and digits is healthy, it is **the damage**.
- If the teardown is not prevented, the test is **void**.
