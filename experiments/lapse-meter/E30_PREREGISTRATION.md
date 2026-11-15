# Experiment 30: is a large readout kick enough by itself, and does it matter whether it is shared? (written before any run)

Written 2026-10-28, before any experiment-30 run, while experiment 28 was running and before experiments 27 and 29
had run. Committed with `experiments/e30_jobs.txt`, `experiments/e30_predictions.json`,
`experiments/e30_measure.py` (the initial measurements below, `results/e30_init.json`) and
`experiments/e30_analyze.py`.

## Why

Experiments 22–24 tie the collapse to the readout kick, but in every collapsing run so far two things came together:

1. a large kick, and
2. a piled-up stream.

Even experiment 23's 24-layer runs were made to collapse by scaling the inputs, which enlarges the stream too.
Experiment 29 then confounds a second pair. Centering the readout's input removes the kick's shared, bias-like
part, but it also shrinks the kick's total size about 14-fold on digits.

Experiment 30 pulls both pairs apart.

**Signed + offset (`ln = "offset"`, `lapse/nets_ln.py`).** This is the signed-ReLU twin, whose stream does not pile up
(growth 1.2–1.3×). Its readout sees h_L + m_relu, where m_relu is the mean last stream of the plain ReLU network with
the same seed, held fixed. The readout's input, the initial logits and so the kick are almost those of plain ReLU,
but the stream is the healthy twin's.

**Center + matched multiplier.** This is plain ReLU, with the full pile-up, whose readout sees h_L − m₀. That removes
the shared part. The readout's learning rate is raised for steps 0 and 1 only (`out_lr_mult_until = 2`), by a per-seed
factor that makes the step-one kick exactly equal to plain ReLU's (digits 13.7–15.1×, circle 2.6–5.5×). The total kick
is the same as in plain ReLU, but almost none of it is shared.

**Signed + offset + kick cap 10.** This control checks that the offset does its harm, if any, through the readout's
update and not through the shifted initial logits.

## Measured at initialization (before writing this)

For each condition: the step-one kick, then the common-mode share, then the stream growth.

| condition | digits | circle |
|---|---|---|
| plain ReLU (experiment 8, all broken) | 1,640–2,396; 0.80–0.87; 35–39× | 108–369; 0.72–0.75; 36–39× |
| signed twin (experiment 9, all healthy: transport +0.70, +1.15) | 0.2–0.3; 0.65–0.76; 1.3× | 0.03–0.14; 0.47–0.75; 1.2–1.3× |
| signed + offset | 1,532–2,081; 1.00; 1.3× | 93–224; 1.00; 1.2–1.3× |
| center + multiplier | 1,640–2,396 (matched); ≤ 0.001; 35–39× | 108–369 (matched); ≤ 0.005; 36–39× |
| signed + offset + cap 10 | 10 effective; 1.00; 1.3× | 10 effective; 1.00; 1.2–1.3× |

## Design and outcome

96-layer residual network, width 64, SGD lr 0.05, batch 64, 6,000 steps, seeds 0–2, both tasks; 18 runs. The
signed and plain references are experiments 9 and 8, whose configurations these runs share. The outcome rule is the
one from experiments 23, 24 and 29: **broken** if transport at loss 0.03 is below +0.3 (falling back to 0.1, then
0.3), or if the run fails to train (final loss above 0.5·ln K).

## The accounts and what each predicts

| account | signed + offset | center + multiplier |
|---|---|---|
| **K:** the kick's total size decides | broken | broken |
| **C:** the kick's shared part decides | broken | healthy |
| **A:** the kick decides only when a piled-up stream turns the resulting errors into coherent block updates | healthy | broken |
| **C+A:** both are needed | healthy | healthy |

Under every account, **signed + offset + cap 10 is healthy (P30c).**

**Primary task: digits.** Its kicks are far from the cutoff (328), so a condition is "broken" or "healthy" there if
at least 2 of 3 runs are. On the circle the kicks straddle the cutoff (124): signed + offset has 93–224 and center +
multiplier 108–369. So the circle result is reported per run against the kick rule, which says broken for 4 of
those 6 runs, and is not used to choose among the accounts.

**My prediction (P30a, P30b): account K.** Signed + offset is broken on digits, and so is center + multiplier. I
hold this weakly, at about 60% and 55%.

The case for A is real. After a large shared kick, every example's stream gradient points along m_relu, but the
blocks' update changes example k's pre-activations by Σ_j δ_j (h_j · h_k). In a piled-up stream h_j · h_k ≈ |m|²
for all pairs, so even unrelated δ_j add into a shared shift. In the signed twin's stream that factor is much
smaller. Digits inputs are all non-negative, though, so even the twin's h_j are correlated through the input layer,
and I cannot tell the size of that effect without running it.

## Decision

On digits, whichever account matches both conditions is **supported**. If P30c fails, the offset harms through the
initial logits, and the readout-update reading of the offset condition is **void**. The kick rule's per-run hit rate
over all 18 runs is reported, not tested.
