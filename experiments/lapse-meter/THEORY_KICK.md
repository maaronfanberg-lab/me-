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
