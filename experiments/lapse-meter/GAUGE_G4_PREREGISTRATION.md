# Gauge G4: do entire learning trajectories survive a change of coordinates?

**Pre-registration, 2026-10-28, before experimental training.** Independent of the numbered experiment series E1–E24. Builds on Gauge G1–G3. This protocol and analysis are committed before confirmatory runs. Any implementation-debugging examples are reported as development, not evidence.

## Context / prior art
Positive ReLU node rescaling is a known symmetry. Conventional SGD is not equivariant under this transformation; Path-SGD (Neyshabur et al., NeurIPS 2015), G-SGD (Meng et al., ICLR), and path-conditioned training (Lebeurrier et al., ICML 2026) all address related limitations. G4 is a compact demonstration of an *elementwise log-parameter update*, **not a proposed state-of-the-art optimizer**.

For each parameter theta (weight or bias), let u=theta * dL/dtheta, a derivative with respect to log|theta| when theta≠0. Under a positive diagonal ReLU gauge, theta'=c theta and grad'=grad/c; so u'=u. The elementwise update

    theta_new = theta * exp(-eta * (theta * grad))

commutes exactly with positive diagonal ReLU gauges at the level of real-number arithmetic. Zeros and parameter signs are invariant, which can impede optimization; document this, do not hide it. This algorithm is not ordinary SGD. Training loss, gradients and the mini-batch schedule are held identical between gauge copies.

## Hypotheses and locked evaluation
- H1 (primary): for each checkpoint and gauge, two gauge-equivalent networks trained with log-parameter updates on the same minibatches have the same output logits and training/test losses to float64 error after every recorded step, including after actual updates. Under exact arithmetic, this is an algebraic identity, so the empirical test checks implementation and numerical stability, **not a newly discovered fact**.
- H2 (negative control): standard SGD on gauge-equivalent copies yields measurably different logits after one identical nonzero update (unless an accidental zero gradient). This outcome is expected prior art.
- Models: bundled sklearn digits, plain ReLU (depth 8) and residual ReLU (depth 24), width 64, batch 64, seeds 6 and 7 not used by G1–G3. Starting networks are fresh, not selected by training success.
- Gauges: uniform hidden scale 4, neuronwise positive scales exp(linspace(-ln 8, ln 8, 64)) permuted deterministically. Plain networks may have different per-layer diagonal scalings; residual identity skips require a shared diagonal.
- Same minibatch indices from generator seed 10000+seed. Learning steps 150, log updates at 0,1,5,25,50,100,150. Log-parameter learning-rate eta=2.0 chosen analytically as a finite candidate **before training**; all results are reported even if the network fails to fit. For SGD control lr=0.05, apply exactly one update from fresh identical gauges. Bias starts at zero and remains zero under log updates: a known shortcoming.
- Primary pass for all 8 (architecture x seed x nontrivial gauge) log-update pairs: logits absolute max difference <1e-8 at all checkpoints; full training-loss difference <1e-9; test accuracy equal. No nonfinite results or hidden exclusions; any failure is a failed prediction. Also check log-gradient product invariant at first update (max relative difference <1e-9), and directly compare transformed parameters against the gauge of original trained network (max relative difference <1e-8).
- Negative control: for each of 8 SGD gauge pairs, max logit difference >1e-7 after one step is success; report difference even if not. No claim that SGD will always be worse at classification.
- Secondary, non-confirmatory: individual training losses/accuracies at steps 0 and 150, and robustness of the log-parameter updater compared with ordinary SGD. No accuracy pass threshold, and do not change eta after seeing outcomes. This test concerns **equivariance**, not improved optimization performance.

## Implementation validation
- Synthetic forward/backprop exactness, signed residual branches, invalid tanh gauge rejection, frozen zeros, and finite differences of a log-scale parameter gradient.
- Independent test of one-step equivariance and zero gradient controls.
- Reproduce using the already verified MLP implementation in lapse.nets and G2's reparameterize/scales helpers.
- Save the complete JSON for all 8 model-gauge pairs, with time-series checks and every failure visible.
