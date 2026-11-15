# Experiment 31 (exploratory): where does final-LayerNorm ReLU's extra transport come from? (written before any run)

Written 2026-10-28, before any experiment-31 run. This is exploratory: one question and one signature, both fixed now.
It is not a pre-registered test.

## The puzzle

In experiment 26, 96-layer residual ReLU with a final LayerNorm ends with more transport than its signed twin:

- digits: +0.75 against +0.54 at loss 0.03;
- circle: +1.11 against +0.60.

The gap is there at every matched step too, not only at matched loss. It also trains more slowly: digits loss 2.09
against 0.40 at step 50.

Measured at initialization before writing this:

- The ReLU stream gradient at the top is 2–18× smaller than the twin's, because LayerNorm divides it by the ReLU
  stream's spread.
- The blocks' weight gradients are mostly larger (2–3×, one seed smaller), because they are δ·hᵀ with h the
  piled-up stream.

So most of the ReLU blocks' updates are rank-one along the shared stream direction m. These are bias-like moves,
which change every example's pre-activations alike.

## Question

Is ReLU's extra transport carried by the **shared** part of the stream gradient (the batch-mean gradient, the same
request to every example) or by the **example-specific** part?

## Method

`experiments/e31_trace.py` reruns the twelve final-LayerNorm runs of experiment 26 exactly (it checks the logs are
identical). A logging hook splits the stream gradient at the top and at block 1 into the batch mean and the rest.

## Signature, fixed now

Read the quantities at the first logged step where training loss is below 0.03.

- **"Shared" answer:** the ReLU − twin gap in example-specific transport (`tr_specific`) is less than half the gap
  in total transport, on both tasks.
- **"Specific" answer:** the gap in `tr_specific` is at least as large as the total gap.
- Anything between is **"mixed"**.

If the answer is "shared", the extra transport is not better learning signal: it is the pile-up's shared direction,
carried backward. Higher transport then does not mean a healthier backward pass, which would be a limit on reading
transport as health.
