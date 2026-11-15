# Experiment 25 (exploratory): what does the kick do? (written before any run)

Written 2026-10-28, before any experiment-25 run, while experiment 24 was running. Exploratory: no pass/fail, but
what would count as evidence for each mechanism is fixed here.

**Runs.** 96-layer residual ReLU, digits and the clean circle, seeds 0–2, 200 steps. Four conditions:

- plain: collapses
- kick cap 10: rescued, but blocks take full steps
- 50-step warm-up: rescued
- signed ReLU: no pile-up

Traced with `experiments/e25_trace.py`, which reproduces the runner's loss trajectory exactly.

**Mechanisms and their signatures.**

- **M1, catapult** (Lewkowycz 2020).
  - Evidence for: in plain runs η·λ_max exceeds 2 in the first steps, the loss rises before falling, and transport
    collapses while η·λ_max returns below 2; in the three rescued conditions η·λ_max stays below 2.
  - Evidence against: plain runs never exceed 2, or the rescued conditions exceed it as much as the plain ones.
- **M2, shared-direction capture.**
  - Evidence for: in plain runs, within the first ~10 steps, the readout weights' energy along the shared mean
    direction (share_W) and the stream gradient's energy along it (share_g) rise far above their starting values
    and above the rescued conditions', before transport collapses.
  - Evidence against: no rise, or the same rise in rescued runs.
- **M3, gate disruption.**
  - Evidence for: in plain runs the fraction of ReLU gates changed since step 0, especially in block 1, jumps within
    the first ~10 steps, more than in the kick-capped runs, whose blocks take the same full steps.
  - Evidence against: the same flip fractions in capped and plain runs.

The kick-capped condition is the key comparison throughout. Its blocks get the same full early updates as plain,
so any mechanism that also appears there is not the kick's doing.
