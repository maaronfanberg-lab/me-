# Gauge G5: moving zero parameters without sacrificing scale-equivariant learning

**New confirmatory protocol frozen 2026-10-28 before the G5 holdout runs.** G5 follows a clearly labeled exploratory pilot on seed 8. It is distinct from and does not retroactively change G4 or experiments E1–E24.

## Motivation and prior work
G4 log-parameter steps are positive-rescaling equivariant but freeze zero-valued biases; its plain 8-layer ReLU networks barely fit handwritten digits after 150 steps. This is an intrinsic defect of the multiplicative update. G5 tests an activation-coordinate (gauge-covariant) preconditioner that allows zero weights and biases to change while keeping equivalent ReLU networks on identical learning trajectories. Related established approaches: Path-SGD (Neyshabur et al., NeurIPS 2015), G-SGD (Meng et al., ICLR 2018/2019), and path-conditioned training (Lebeurrier et al., ICML 2026). Do not claim this is a novel state-of-the-art optimizer.

For each hidden/output unit i let a_i = RMS_batch[z_i], where z_i is its **preactivation** (linear outputs); define a_input = RMS_batch[X] per input feature, replacing constant-zero input features by 1, and a_output=1 (fixed because logits are not reparameterized). Under a positive ReLU diagonal D, preactivations scale by their node coordinate, so these per-unit anchors transform covariantly. For weight W_ij, q_ij=a_out_i/a_in_j; for bias b_i, q_bi=a_out_i. Define `G = sqrt(sum((q_W*grad_W)^2)+sum((q_b*grad_b)^2))`, gauge invariant. Update with `divisor=max(1,G/1.0)`:

    W_ij <- W_ij - 0.05 * q_ij^2 * grad_Wij / divisor
    b_i <- b_i - 0.05 * q_bi^2 * grad_bi / divisor

All anchors must be strictly positive and finite; if not, report a failed/unusable condition instead of clipping them with a fixed epsilon that breaks exact symmetry. This is *not* ordinary SGD, and its success may depend strongly on learning-rate and clipping choices.

## Exploratory pilot, disclosed before holdout
On digits seed 8, width64, depth8 plain and depth24 residual, 150 steps, same seed-specific minibatch schedule: with cap=1.0 and eta=0.05, plain reached ~79.1% test accuracy, residual ~84.1%, and maximal paired-gauge logit difference was below 1e-12. With eta=0.1, cap1.0, **both architectures diverged** (huge loss and functional-equivalence drift). Unclipped frame updates also overflowed at several higher learning rates. These pilot failures must remain in the report; cap1 and eta0.05 were selected *after* this exploratory tuning, so a positive holdout result is necessary.

## Locked holdout design and pass rules
- Two fresh seeds **10 and 11**, not used for selecting the settings. Bundled sklearn digits; width64; plain ReLU depth8 and residual ReLU depth24; batch64; 150 updates, step logs 0,1,5,25,50,100,150.
- For each of the four baseline models, compare a nonuniform positive neuronwise gauge from G4 (permutation of scales log-spaced from 1/8 to 8; same D along residual identity skips). Same minibatch sequence under the gauge. No exclusions based on accuracy.
- **H1 (equivariance):** all 4 pairs remain functionally matched across all recorded checkpoints (max absolute logit error <1e-8, training and test loss diff <1e-9, test accuracy equal, corresponding reparameterized weights max relative error <1e-8). Check the invariant G normalization on the first batch and finite/nonzero preactivation anchors.
- **H2 (zero-bias escape):** each of four original networks has at least one formerly zero bias become nonzero at step 1. The mathematical update permits this when the corresponding gradient is nonzero.
- **H3 (optimization benefit, plain networks):** at step 150, each of the two held-out plain networks exceeds the paired **G4 log-parameter** network's digit test accuracy by at least 0.20 absolute, using the same seed, architecture, batches and 150 steps. Both outcomes and any failures reported.
- Report residual accuracy and loss, but no superiority claim over the G4 residual optimizer is preregistered.
- Capture all 4 model-pair records, all checkpoints, test accuracies, train loss, bias movement, and first-batch gauge consistency. No silent dropped runs. Failure of an assertion is recorded by the run and may not be represented as success.

## Limitations
Activations can have zero preactivation RMS for degenerate neurons, which makes this particular frame undefined. Numerical instability still exists; the clip is gauge-invariant but not a universal stabilizer. These experiments neither prove improved state-of-the-art learning nor invariance for tanh, normalization layers or all function-preserving transformations. Test loss on a small digit dataset is only a screening measure.
