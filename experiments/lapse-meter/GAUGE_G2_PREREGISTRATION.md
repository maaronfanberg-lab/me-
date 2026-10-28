# Gauge G2: can an operational signal survive neuronwise ReLU rescaling?

**Pre-registered 2026-10-28; independent of experiments 1–21 and Gauge G1.**
This document is committed before the trained-digit G2 runs. Positive ReLU scaling symmetries and path invariants are established prior art (Neyshabur et al., NeurIPS 2015; Meng et al., ICLR 2019). Do not characterize the symmetry as a new discovery.

## Scientific question
G1 showed that lapse tilt and fixed raw-gradient 'horizons' depend on parameterization even when the network function is exactly unchanged. Can two alternative layer-local signals remain invariant under *nonuniform per-neuron* scaling, not just the uniform scaling used in G1?

For layer l, let h_l be its **post-activation state**, g_l=partial L / partial h_l on the same examples, and G_W,l=partial L / partial W_l, G_b,l=partial L / partial b_l (batch-averaged). Proposed diagnostics:

1. **Activation sensitivity/work** A_l = RMS_examples ||h_l elementwise* g_l||_2. Dimensionless relative profile A_l / A_last_hidden (when denominator>0). This is sensitivity to infinitesimal multiplicative perturbation of hidden activations, **not a physical clock or layer training rate**.
2. **Parameter log-scale pressure** P_l = sqrt( ||W_l elementwise*G_W,l||_F^2 + ||b_l elementwise*G_b,l||_2^2 ). This is sensitivity to proportional perturbations of each parameter, **not the actual SGD update speed**.

For an invertible *positive diagonal* D, h'_l=D h_l and g'_l=D^-1 g_l, so each component of h*g is invariant. For weights W'_l=D_out W_l D_in^-1, b'_l=D_out b_l, the corresponding gradients transform inversely, making each elementwise W*G_W and b*G_b invariant. ReLU is positively homogeneous; the residual skip permits a *shared D* for all residual-stream states (including fixed diagonal sign branches). Plain ReLU layers permit an independent D_l at each hidden layer.

## Locked design (development tests are not experimental results)
- Base architecture uses the repository's existing `lapse.nets.MLP` and `lapse.data.digits`. Two seeds 0 and 1; plain ReLU depth 8; residual ReLU depth 24; width 64; digit 10-class task; SGD lr=0.05, batch size 64.
- Snapshots at 0, 250, and 500 optimizer steps. Each gauge comparison is a *copy of that exact checkpoint*. Initial and trained snapshots included, no accuracy-based exclusions.
- Two nontrivial gauges per snapshot: (a) uniform hidden scale 4; (b) deterministic neuronwise positive scales log-spaced from 1/32 to 32 in a seed-dependent permutation. In plain networks independent deterministic permutations/scales at each hidden layer. Identity gauge 1 is a control. This yields 2 seeds x 2 architectures x 3 snapshots x 3 gauges = **36 comparisons**.
- Measurements computed on the same 256 training examples for every pair. Record max absolute logit change, loss difference, test accuracy difference, raw lapse tilt shift, raw slope shift, changed raw horizon count, max (across layers) relative activation-work component error, max relative parameter-pressure component error, activation-work tilt shift, and maximum change to the entire profile.
- Positive scales only, finite float64. No clipping or arbitrary renormalization. If a relative profile's reference is zero, report undefined rather than hide it. All non-finite quantities count as failures.
- Gauge invariance pass criteria in *all 36 comparisons*: logits < 1e-9 absolute change, loss < 1e-9 change, accuracy same, max relative error (normalized by max(1, |original|)) in each work and pressure component < 1e-9.
- Check raw lapses are not invariant under some nontrivial gauge, but do not require an arbitrary effect-size threshold. Record effects for both plain and residual; report if unexpectedly invariant in any condition. Gauge-invariance of A/P is the primary confirmatory claim.
- Synthetic tests: signed residual branches; gradient checks using finite differences; deliberate broken-gauge negative control must change logits; tanh gauge must be rejected by the transformation helper.

## Decision and limitations
If every comparison passes, A_l and P_l are empirically gauge-invariant under these **specific positive diagonal transformations**, with algebra supporting exact invariance away from floating-point error. This does not prove invariance under arbitrary function-preserving transformations, other activations, architectures, changes in training algorithm, or that these diagnostics predict successful learning. No 'causal horizon' claim. A_l is anchored to the last hidden layer (not the output-loss gradient), so it is not numerically comparable to G1 tilt. P_l is batch averaged and does not include optimizer preconditioning. Report any failed assertions and keep original values.

## Prior work
- Neyshabur, Salakhutdinov & Srebro, Path-SGD (NeurIPS 2015): https://papers.neurips.cc/paper_files/paper/2015/hash/eaa32c96f620053cf442ad32258076b9-Abstract.html
- Meng et al., G-SGD (ICLR 2019): https://arxiv.org/abs/1802.03713
- Liang et al., Fisher-Rao Metric, Geometry, and Complexity (2017): https://arxiv.org/abs/1711.01530
