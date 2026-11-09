# Strange Effects listening review

2026-11-09 20:12 UTC · commit 9a3d10c · **ALL PASS**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 146 runs | quietest -52.8 dB | ✅ | Everything · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| Never silent on a phone | same, counting only sound above 300 Hz (what phone speakers play) | quietest -57.9 dB | ✅ | Strange · Lorenz-84 |
| Events you can hear, not a roar | every run has ≥ 0.75 attacks a second a listener can pick out (spectral-flux onsets, Böck & Widmer 2013; a drone scores 0), scaled with Movement | fewest 1.02/s at movement 0.35 · undertow up 4.2% on average, 63.4% at most | ✅ | Electric · Rabinovich–Fabrikant |
| Every attractor plays | each playing attractor ≥ 0.25 notes a second at Medium movement (one every 4 s), scaled with Movement | slowest 0.38/s at movement 0.35 (152% of its bar) | ✅ | 1 particle · Rabinovich–Fabrikant |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.413% | ✅ | Rank · Rabinovich–Fabrikant |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 70% | ✅ | Willamowski–Rössler + Nosé–Hoover · pull |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
