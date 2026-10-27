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
