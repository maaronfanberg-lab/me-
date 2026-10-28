# Research record: lapse-meter

Added under the repository's research-first rule. This is a new, self-contained experiment folder; it changes no
existing behaviour of the Room, the apps, or any deployed service.

**Observed problem.** In earlier experiments on this account (a 136-run study of 24-layer tanh networks, and a
browser "Lapse Playground"), the size of the error signal reaching each layer, its lapse, behaved lawfully during
training, but two claims about it were later found wrong or partly wrong (see CORRECTIONS.md). There was no
reusable, verified instrument for measuring it, and no test of whether the pattern depends on depth.

**Research question.** Measured directly from backpropagated signals: (1) does training hold a network's *total*
tilt (output to first hidden layer) roughly fixed as depth changes, or its per-layer slope, or neither?
(2) Is the lapse literally a per-layer learning clock under SGD, and does Adam break that?

**Foundational evidence.** Signal propagation and depth scales in deep networks (Schoenholz et al., *Deep
Information Propagation*, ICLR 2017); dynamical isometry (Pennington, Schoenholz & Ganguli, NeurIPS 2017;
Xiao et al., ICML 2018, 10,000-layer CNNs). The lapse function and 1+1 curvature R = −2N″/N are standard
differential geometry.

**Current evidence.** Criticality lets a local rule approximate backprop through time (Wang, Gao & Chen, *Global
Credit Assignment via Dynamical Criticality*, ICML 2026). Depth-µP scalings for residual networks (used in µPC,
NeurIPS 2025). Residual scaling α = 1/√L is a common choice in that line of work.

**Competing explanations considered.** A changing lapse could be produced by weights merely growing or moving,
not by the gradient's direction (the earlier study ran random-direction controls; the random updates did not
flatten). Lapse could track accuracy only because failed runs saturate. Results could be specific to one task, so
two tasks are used. They could be specific to one architecture, so plain and residual, tanh and ReLU are used.

**Limitations.** Only small numpy networks trained in this environment; no pretrained models could be downloaded
here and PyTorch could not be installed. One optimiser setting per experiment, three seeds per cell. The language
model is a tiny character-level model trained on ~100k characters of licence text.

**Implementation mapping.** New folder only: `lapse/` (library), `tests/`, `experiments/`, `results/`,
`figures/`, `audio/`. No existing file is modified.

**Validation criteria, fixed before the results.**
- Library correct: finite-difference gradient checks < 1e-5 relative error for every architecture and activation;
  an orthogonal linear network must give lapse ratios equal to the weight scale to machine precision.
- Experiment 1: conserved total tilt predicts the fitted depth slope b of T_end ≈ 0 and a small spread of T_end
  across depths; conserved per-layer slope predicts T_end growing in proportion to depth. Report whichever holds,
  or neither.
- Experiment 2: a literal clock predicts a log-log slope near 1 between weight motion and lapse under SGD;
  Adam, which rescales each gradient, predicts a slope near 0.
- Sonification: measured pitch must equal the stated mapping to 0.1%; a flat network must be a unison.

## Addendum, 2026-10-27: experiments 4 and 5

**Experiment 5** (`experiments/e5_alignment.py`) re-measured the clock comparison on a single time base and
showed that an apparent mismatch (CORRECTIONS 10) and two wrong activity spreads in the README (CORRECTIONS 11)
came from my analysis mixing time windows. README section 2 was corrected.

**Experiment 4** was pre-registered in `experiments/E4_PREREGISTRATION.md` before any run; one condition
(input scale) was added to that file after a data check and before running, and the file says so. Outcome
against the fixed validation rule: input dimension and scale not supported; class count supported for residual
networks only; the label-noise prediction failed. An exploratory, post-hoc decomposition is reported separately
and labelled as such. Post-change validation: the library's 24 checks and the sound module's 8 checks pass after
these changes.

## Addendum, 2026-10-27: experiment 6

**Observed problem.** Experiment 4's tilt changes coincided with how completely each task was fit.
**Pre-change baseline and criteria.** Pre-registered in `experiments/E6_PREREGISTRATION.md`; that file and the
analysis script `experiments/e6_analyze.py` were pushed to GitHub before any run. One later change to `e6.py`
(creating its output folder before training) touches file handling only.
**Post-change result.** Within-run test: 18 of 24 (pass bar 20), fails narrowly. Matched-loss task comparisons:
1 of 4 persist (pass), the exception being memorised wrong labels. Class count: holds at 3 of 4 loss levels.
Library checks and sonification checks pass after the change.
**Limits.** One architecture (residual tanh, 24 layers), three seeds, two base tasks; matched-loss comparisons for
the noisy circle tasks exist only at high loss, where seed spread is large.

## Addendum, 2026-10-27: experiment 7

**Observed problem.** Experiment 1 compared depths after equal steps; experiment 6 showed the tilt depends on
training progress. **Baseline and criteria** were pushed before any run (`experiments/E7_PREREGISTRATION.md`,
`e7.py`, `e7_analyze.py`, commit 528036a). **Post-change result.** The tanh prediction held on both tasks; a
pre-registered secondary measure found a small consistent positive depth slope. ReLU at 96 layers behaved
differently (reported as exploratory). A description of the ReLU runs given in conversation was wrong and was
corrected before the write-up (CORRECTIONS 18). All test suites pass after the change.


## Addendum, 2026-10-27: experiments 8–20

**Observed problem.** In experiment 7, residual ReLU behaved differently at 96 layers. This series asks why.

**Baseline and criteria.** Each block's plan was pushed to GitHub before its first run:

| experiments | pre-registration | commit as pushed |
|---|---|---|
| 8 (exploratory) | `PROGRAM_E8.md` | c1c085d |
| 9–12 | `E9_12_PREREGISTRATION.md` | e0d6aba |
| 13–16 | `E13_16_PREREGISTRATION.md` | 0ab8296 |
| 17–20 | `E17_20_PREREGISTRATION.md` | 4595938 |

The main branch is rewritten by an automated process, so these hashes may not survive in its history; the files
themselves carry the dates. One disclosed exception: 100-step smoke tests of two experiment-11 conditions were
seen before their predictions were written.

The new instrumentation is additive:

- `lapse/probe.py` splits the tilt exactly into output, transport and gate parts.
- `experiments/probe_run.py` reproduces experiment 7 bit for bit with default settings, and the warm-up path
  reproduces experiment 11 exactly.
- New network options have gradient and identity checks: `tests/test_probe.py`, `tests/test_probe_run.py`,
  `tests/test_nets2.py`.

**Post-change result.**

- **Experiments 9–10:** the pile-up hypothesis held. Signed ReLU and a zero-mean hard-gate activation are rescued.
- **Experiments 11–16:** several predictions failed:
  - Warm-up rescues (P11a, wrong).
  - 50 steps is enough (P13b, wrong).
  - The shock lands on the output layer, not the blocks (P14a and P14b, wrong).
  - Two comparisons were biased by the rule excluding a run that never trained (P12 and P16 on the circle).
    The rule was supplemented with a failed-to-train count from experiment 13 on.
- **Experiments 17–19:** the standard two-matrix block and Adam show no depth break (P17a, P17b, P18 held).
  Width 128: see README section 10.
- **Experiment 20 (exploratory):** the break goes with higher final loss and lower test accuracy on digits.
- One presentation change was made to `e17_20_analyze.py` after its pre-registration push, before results were
  final. It changes wording only: how an undefined correlation is printed, and a table caption.

All test suites pass after the changes.

**Limits.**

- Small numpy networks.
- Two tasks, three seeds per cell.
- One learning rate per optimizer.
- The one-matrix block is not what production networks use (experiment 17).
