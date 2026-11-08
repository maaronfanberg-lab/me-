# Strange Effects listening review

2026-11-08 19:51 UTC · commit 9bfc07d · **FAIL**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 146 runs | quietest -67.5 dB | ❌ | Everything · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| Never silent on a phone | same, counting only sound above 300 Hz (what phone speakers play) | quietest -73.6 dB | ❌ | Gentle · Lorenz-84 |
| Finite events, not a roar | undertow up ≤ 50% of the time in every run | average 3.6%, most 63.4% | ❌ | Slow · Rabinovich–Fabrikant |
| Every attractor plays | each playing attractor ≥ 0.5 notes a second | slowest 0.49/s | ❌ | Slow · all 10 · Tangle |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.413% | ✅ | Rank · Rabinovich–Fabrikant |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 70% | ✅ | Willamowski–Rössler + Nosé–Hoover · pull |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
