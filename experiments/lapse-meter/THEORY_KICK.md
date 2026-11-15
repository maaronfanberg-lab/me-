# Why does the kick have a threshold near a few hundred? A back-of-envelope account (written before experiment 30's results)

Written 2026-10-28, after experiments 22–26 and 28's first ten runs, before any result of experiments 27, 29, 30 or
31. This is an estimate, not a derivation. Its value is the falsifiable scaling at the end, which experiment 32 will
test.

## Setup

Take the piled-up stream: every example's last stream is h_j ≈ m + ε_j, with |m| ≫ |ε_j|. The readout learning
rate is η_o, the blocks' is η_b, the block scale is α = 1/√depth. At step 0:

```
mean error            d̄₀ = mean_j (p_j − y_j)             (|d̄₀| is of order 1 when the initial logits are large)
readout update        ΔW_out ≈ −η_o d̄₀ mᵀ                  (the shared part, using h_j ≈ m)
logit change (kick)   K₀ ≈ η_o |d̄₀| |m|²                    (the same for every example: a bias shift)
```

## Step 1

The stream gradient of example j is g_j = d_j W_out. After the update it has a new part,
−η_o (d_j · d̄₀) m. That part has size about η_o |m| and points along m for every example.

Block l then takes the update ΔW_l = −η_b Σ_j δ_j h_jᵀ / n, where δ_j = α g_j ⊙ gate_j. This changes example k's
pre-activation by about

```
η_b α |ḡ| (h_j · h_k)  ≈  η_b α · η_o|m| · |m_l|²
```

That shift is the same for every example, because in a piled-up stream h_j · h_k ≈ |m_l|² for all pairs. Compare
it with the pre-activations' own scale, about |m_l|:

```
ratio  ≈  η_b α η_o |m| |m_l|  ≈  η_b α K₀ / |d̄₀|    (taking |m_l| ≈ |m| near the top)
```

When the ratio passes about 1, a shared shift as large as the pre-activations moves every example's gates
together. The gates flip en masse (mechanism M3, seen in experiment 25) and the backward path through those
blocks is rewired at once.

## The estimate

With η_b = 0.05, α = 1/√96 ≈ 0.10 and |d̄₀| ≈ 1, the ratio reaches 1 at **K₀ ≈ 200**.

The cutoffs measured in experiment 22 were 124 (circle) and 328 (digits), with a transition band of roughly
100–500. I did not tune anything to get 200.

## What this predicts

1. **The threshold scales as 1/(η_b α).** It is set by the blocks' learning rate, not the readout's. Scaling the
   blocks' learning rate by c during the critical window should move the critical kick to about 200/c, with the
   readout untouched. Experiment 32 tests this.
2. **Signed + offset** (experiment 30) **should be healthy.** The stream does not pile up, so h_j · h_k is far
   smaller than |m_relu|², and the shared shift is not amplified. This disagrees with my registered prediction for
   P30a (account K). If the estimate is right, P30a fails.
3. **Center + matched multiplier** (experiment 30): this estimate cannot say. The stream gradients
   −η_o Σ_i (d_j · d_i) ε_i / n vary across examples, and how much they cancel when summed against the piled-up
   h_j is not something the estimate gives. I give no prediction.

## Where it is weakest

- It ignores the gates' own correlation.
- It treats |m_l| as constant across layers, although the pile-up grows with depth.
- It assumes the step-0 readout update is dominated by its shared part. That holds for the measured shares of
  73–87%, but not exactly.

## Amendment, 2026-10-28, 14:31, still before any experiment-27, 29 or 30 result: prediction 1 was already refuted

Before pre-registering experiment 32, I checked prediction 1 against data I already had, which I should have done
before writing it.

**What experiment 14 tested.** Its blocks-only warm-up scaled the blocks' learning rate by c = (t+1)/500 at step t.
That puts c at 0.002 at step 0, so the critical kick this estimate predicts is around 100,000. The readout was left
at full rate.

**What happened.** Neither task was rescued. Five of the six runs lost transport (to about 0.0–0.3) within 100–500
steps, one of those digits runs never trained, and one circle run stayed healthy (`results/e14/*_warmblocks_*`). So slowing the blocks during the first steps does not move
the threshold, and prediction 1 is wrong (CORRECTIONS 49). Experiment 32, as planned, would only repeat experiment 14;
it will not be run.

**What the failure points to.** The damage does not have to be done at step 1. The readout's step-0 update gives
W_out a large component along m, and nothing later removes it. Experiment 25 saw this: the readout's weights end
with 82–88% of their energy along the shared direction. While that component persists, every example's stream
gradient keeps a large part along m, whenever the blocks start moving. The kick matters because it *installs* that
component. Its size relative to the blocks' learning rate is not the point.

**What survives.** The order-of-magnitude coincidence (a predicted crossing near 200, against observed cutoffs of
124–328) survives only as a coincidence. Prediction 2 (signed + offset healthy) came from the same step-1 picture, so
it now has no support. Experiment 30 tests it regardless.

## Amendment 2, 2026-10-28, 14:50, before any experiment-27, 29, 30 or 33 result: the bias channel

I tried a repair, done once, on a 3-step smoke run: before step 1, remove the readout's accumulated change along the
mean input direction m̂. The step-0 kick simply happened again. At step 2 the loss was 108 with the repair, against
22.5 without it. The readout's component along m is not a stray side effect. It is how this readout implements its
**bias**: with every input ≈ m, W_out·m works as a per-class offset far larger than b_out. Remove it and the next
step's error relearns it with another giant kick.

**The account (B, "bias channel").** In a normal network the class-bias gradient stops at b_out. Here the effective
bias is W_out·m, and m is built by every block, so the bias gradient flows backward into all of them. The readout's
gradient into the stream, d_j W_out, contains (d_j · W_out m̂) m̂. That term asks every example's stream to move
along m, by an amount set by how wrong the class priors currently are. After a large shared kick the priors are
very wrong for many steps, so the blocks are flooded with a shared, bias-fitting request that has nothing to do
with the examples.

**Predictions of B:**

- **Experiment 33** (pre-registered alongside this amendment): cut that channel alone, by projecting m̂ out of the
  readout-to-stream gradient during training, with the forward pass and the kick left intact. That rescues plain
  96-layer ReLU on both tasks. The same cut along a random direction does not.
- **Experiment 30** (registered earlier with my bet on account K): B predicts account C's pattern.
  - Signed + offset is broken. The bias rides on m_relu, so the bias gradient asks the twin's blocks to build
    m_relu.
  - Center + multiplier is healthy. The bias lives in b_out, and the readout's input carries no shared direction.

If experiment 33's cut does not rescue, B is wrong. The total kick, through the example-specific errors it leaves
behind, would then be enough (account K).

## Amendment 3, 2026-10-28, 15:12: the collapse as an escape

Written after seeing experiment 30's digits runs (signed + offset diverges in all three, and capping its kick
rescues it) and experiment 29's follow-up traces. It was written **before looking at the experiment-21 or new data
used to check it below.**

**The account (E, "escape").** With a piled-up stream, the readout's effective step, η·|h_L|²·(softmax curvature),
is far above the stability limit of 2: about 2,700 at initialization on digits. The readout cannot converge.

- **Plain ReLU escapes** by shrinking its own stream. Within two steps it closes half its gates and the last stream
  falls from 234 to about 11 (CORRECTIONS 53). That pushes the readout toward the edge of stability, at the price of
  the backward signal.
- **Signed + offset cannot escape.** Its huge readout input is a fixed vector the blocks cannot shrink, so it
  diverges. Capping the kick keeps the readout's steps small and rescues it.
- **Read this way, the collapse is not damage the kick does in passing. It is how the network makes its readout
  stable.**

**Predictions, written before checking:**

- **E-i.** In plain 96-layer ReLU after the shock, the last stream's size scales as η^(−1/2) across learning rates.
  Experiment 21 has SGD at lr 0.02, 0.05 and 0.1 on both tasks. Read at step 500, the ratio of the stream's RMS
  between lr 0.02 and lr 0.1 should be √5 ≈ 2.2, accepted within 1.7–2.9 on each task.
- **E-ii.** After the shock, the readout's preconditioned sharpness, η·λ_max of the loss Hessian over the readout
  alone, sits near the edge of stability: between 1 and 4 at steps 100–500. At initialization it is far above 2.
  This is measured on new traces, digits and circle, seed 0, at lr 0.05.

*Correction, 15:20, before any run that tests E-i or E-ii.* Prediction E-i named experiment 21's learning-rate runs,
but those are tanh networks at 24 layers. No plain-ReLU 96-layer runs exist at other learning rates. E-i and E-ii
are tested unchanged, on new runs (`experiments/escape_check.py`, committed before it ran): plain ReLU, 96 layers,
seed 0, lr 0.02, 0.05 and 0.1, both tasks, 500 steps.

## Result of the escape checks (`results/escape_check.md`): account E refuted as stated

- **E-i fails on both tasks.** Going from lr 0.02 to lr 0.1 shrinks the last stream 1.56× on digits and 21× on the
  circle, not the predicted 1.7–2.9×.
- **E-ii fails on both tasks.** After the shock, the readout's preconditioned sharpness is 0.31 (digits) and about 0
  (circle) at lr 0.05: well below the edge of stability, not near 2.
- **The premise was also wrong.** At initialization on digits the readout's curvature is essentially zero (η·λ ≈ 1e-9,
  from the exact Hessian). The initial logits are so large that every example's softmax is saturated, and a
  saturated softmax is flat. The readout is not "too sharp to converge"; it takes fixed-size linear steps across a
  flat, saturated region. A stability-threshold story of the Gilmer 2022 kind does not apply at initialization here.
  That fits sharpness being the weaker predictor in experiment 22 (AUC 0.91 and 0.85, against the kick's 0.99 and
  0.94).

What remains, as observation only: the stream shrinks right after the shock, and how much depends on the task and
the learning rate in ways no account here has predicted. Signed + offset's divergence is not explained by E.

## Amendment 4, 2026-10-29: deriving the cutoff of experiment 53 (failed)

**Derivation.**

- After the kick, the stream gradient is about K·|d|/|h|.
- The input layer's step then moves the stream by about η|x|²·K|d|/|h|.
- The relative growth per step is r = η|x|²·K·|d| / |h|², and it should run away above r = 1, with nothing fitted.

**Test, on all 262 runs with the teardown blocked** (`results/theory_r.json`; post hoc for experiment 53's runs, but
nothing was fitted):

- r > 1 is right in only 149 of 262 runs (39 of the 72 new ones).
- The best cutoff on r is 0.019, about 50× from the derivation, and even that cutoff is right in only 235, against
  239 for the fitted product rule.
- So dividing by |h|² makes the predictor worse. The derivation is wrong, probably in treating the input layer's
  update as passing unchanged to the top of the stream.

The fitted product rule stands as an empirical boundary with no derivation.
