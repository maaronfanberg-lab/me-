# Strange Effects listening review

2026-11-08 20:04 UTC · commit c0a295e · **FAIL**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 146 runs | quietest -51.7 dB | ✅ | Electric · Willamowski–Rössler + Nosé–Hoover |
| Never silent on a phone | same, counting only sound above 300 Hz (what phone speakers play) | quietest -56.8 dB | ✅ | Gentle · Lorenz-84 |
| Finite events, not a roar | in every run the loud moments stand ≥ 15 dB above the quiet floor (90th vs 10th percentile of 20 ms windows) | least contrast 3.1 dB · undertow up 3.6% on average, 63.4% at most | ❌ | Cathedral · Willamowski–Rössler + Nosé–Hoover |
| Every attractor plays | each playing attractor ≥ 0.5 notes a second at Medium movement, scaled with Movement (Slow ≥ 0.09, Fast ≥ 2.3) | slowest 0.78/s at movement 0.35 (156% of its bar) | ✅ | 1 particle · Rabinovich–Fabrikant |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.413% | ✅ | Rank · Rabinovich–Fabrikant |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 70% | ✅ | Willamowski–Rössler + Nosé–Hoover · pull |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
