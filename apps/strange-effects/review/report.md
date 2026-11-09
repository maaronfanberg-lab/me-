# Strange Effects listening review

2026-11-09 20:43 UTC · commit ca6faaf · **FAIL**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 146 runs | quietest -51.7 dB | ✅ | Gilmour · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| Never silent on a phone | same, counting only sound above 300 Hz (what phone speakers play) | quietest -56.5 dB | ✅ | Gentle · Lorenz-84 |
| Events you can hear, not a roar | every run has ≥ 0.75 attacks a second a listener can pick out (spectral-flux onsets, Böck & Widmer 2013; a drone scores 0), scaled with Movement | fewest 1.18/s at movement 0.35 · undertow up 4.1% on average, 63.4% at most | ✅ | Strange · Willamowski–Rössler + Nosé–Hoover · Tangle |
| Every attractor plays | each playing attractor ≥ 0.25 notes a second at Medium movement (one every 4 s), scaled with Movement | slowest 0.38/s at movement 0.35 (152% of its bar) | ✅ | 1 particle · Rabinovich–Fabrikant |
| Subwoofer engaged | Receiver output: sound below 80 Hz is −16 to −4 dB of the whole, as in a full mix, and 20–40 Hz rumble stays under the 40–80 Hz punch, all 140 runs | below 80 Hz from -16.5 to -3.3 dB | ❌ | Space synth · Willamowski–Rössler |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.521% | ❌ | Electric · Rabinovich–Fabrikant |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 70% | ✅ | Willamowski–Rössler + Nosé–Hoover · pull |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
