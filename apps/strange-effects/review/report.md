# Strange Effects listening review

2026-11-08 19:20 UTC · commit f5da6d3 · **FAIL**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 95 runs | quietest -63.1 dB | ❌ | Everything · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| Finite events, not a roar | undertow up ≤ 50% of the time in every run | average 7.9%, most 47.8% | ✅ | Space synth · Rabinovich–Fabrikant |
| Every attractor plays | each playing attractor ≥ 0.5 notes a second | slowest 2.07/s | ✅ | Everything · Willamowski–Rössler + Nosé–Hoover · Tangle |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.058% | ✅ | Space synth · Rabinovich–Fabrikant |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 70% | ✅ | Willamowski–Rössler + Nosé–Hoover · pull |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
