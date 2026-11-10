# Strange Effects listening review

2026-11-10 12:04 UTC · commit 61ce428 · **FAIL**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 128 runs | quietest -50.8 dB | ✅ | Strange · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| Never silent on a phone | same, counting only sound above 300 Hz (what phone speakers play) | quietest -56.5 dB | ✅ | Gentle · Lorenz-84 |
| Events you can hear, not a roar | every run has ≥ 0.75 attacks a second a listener can pick out (spectral-flux onsets, Böck & Widmer 2013; a drone scores 0), scaled with Movement | fewest 1.31/s at movement 0.35 · undertow up 3.8% on average, 66.7% at most | ✅ | 1 particle · Rabinovich–Fabrikant |
| Every attractor plays | each playing attractor ≥ 0.25 notes a second at Medium movement (one every 4 s), scaled with Movement | slowest 0/s at movement 0.06 (0% of its bar) | ❌ | Slow · all 10 · Tangle |
| Subwoofer engaged | Receiver output: sound below 80 Hz is −16 to −3 dB of the whole, as in a full mix (a system whose own notes are very low may sit near the top), and 20–40 Hz rumble stays under the 40–80 Hz punch, all 122 runs | below 80 Hz from -13.9 to -3.9 dB | ✅ | Space synth · Willamowski–Rössler |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.084% | ✅ | Strange · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 28% | ❌ | Rabinovich–Fabrikant + Willamowski–Rössler · tangle |
| Interaction you can hear and see | at Tangle, every pair changes audibly (pitch moves ≥ 50¢ or note rate ≥ 25%) and visibly (its particles shift ≥ 0.15 of the box), against Apart | 44/45 pairs · weakest: pitch 328¢, notes 38%, picture 0.10 | ❌ | Rikitake dynamo + Moore–Spiegel |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
