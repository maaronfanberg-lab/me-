# Experiments 8 onward: why does deep residual ReLU lose its tilt? (written before any experiment-8 run)

Written 2026-10-27. Experiment 7 found that residual tanh networks keep nearly the same total tilt T* from 12 to
96 layers at matched training loss, while residual ReLU networks at 96 layers behave differently: on the clean
circle T* is strongly negative, and on digits it is erratic. This series asks why, with up to 20 experiments.

**Rules.** Same as before. Every confirmatory experiment's prediction, design and analysis code are committed to
GitHub before its first run. Exploratory experiments say so up front and make no pass/fail claims. Results are
reported whether they hold or fail. Errors go in CORRECTIONS.md.

**Tool.** `lapse/probe.py` splits T* exactly into three parts:

- `ln_out`: the output layer turning the loss signal into a gradient on the residual stream.
- `ln_transport`: the stream carrying that gradient back from the last block to the first.
- `ln_gate`: the first block's activation derivative letting it through.

The three add to T* to rounding (tests/test_probe.py). `experiments/probe_run.py` trains with these
diagnostics. With default settings it is bit-identical to experiment 7 (tests/test_probe_run.py).

**Experiment 8 (exploratory, no prediction).** This repeats experiment 7's tanh and ReLU runs at depths 12, 24,
48 and 96 on both tasks, with 3 seeds, logging the three parts through training. It also logs, per layer, the
stream gradient, gate, stream size, branch-to-stream ratio, ReLU gate density and dead-unit fraction. Its only
purpose is to say which part moves, so the next experiments can test a specific mechanism.
