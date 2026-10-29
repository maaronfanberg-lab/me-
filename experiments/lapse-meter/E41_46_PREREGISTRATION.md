# Experiments 41–46: how general is "the teardown is an escape only for large kicks on large-scale inputs"? (written before any run)

Written 2026-10-29, after experiment 40. Committed with `ci/e41_46.txt` and `experiments/e41_46_analyze.py`
before any run.

## Rule under test

From experiments 36–40: with the teardown blocked (`block_nomean = "all"`), a network diverges if its step-one kick
is large (digits threshold about 600) **and** its inputs are large-scale. Otherwise it trains.

## Shared rules

- **Diverged:** the run stops on non-finite values.
- A condition takes the state at least 3 of 5 runs show (at least 8 of 10 for E46).
- Kicks were measured before writing this, on seed 0.

## Predictions

| exp | condition (teardown blocked unless noted) | kick, seed 0 | prediction |
|---|---|---|---|
| E41a | language model, inputs ×1 (one-hot, norm 4) | 18 | trains |
| E41b | language model, inputs ×10 | 3,196 | diverges |
| E42a | digits, width 128 | 4,265 | diverges |
| E42b | circle, width 128 | 824 | trains (small input scale) |
| E43a | digits, 48 layers | 206 | trains (kick below about 600) |
| E43b | digits, 192 layers | 63,137 | diverges |
| E46a | digits, seeds 5–14 (replicating E36) | – | diverges, at least 8 of 10 |
| E46b | circle, seeds 5–14 | – | trains, at least 8 of 10 |

**E45 (exploratory).** An every-step trace of digits with the teardown blocked, the input layer frozen and readout
×10 (the blocks route of E40), 5 seeds, against the same with the blocks at 0.1×. It reports stream size,
own/inherited parts and gate flips.

## Decision

The rule is **supported** if at least 7 of the 8 tested predictions hold, and **refuted** if 4 or more fail.

*Dropped before any run:* E44 (Adam). Adam rescales each coordinate, so a projected gradient no longer gives a
mean-free update, and the manipulation is not defined there.
