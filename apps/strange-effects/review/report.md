# Strange Effects listening review

2026-11-12 01:54 UTC · commit c02277d · **FAIL**

| Check | Pass condition | Result | | Worst case |
|---|---|---|---|---|
| Never silent | every 20 ms window louder than −60 dB, all 128 runs | quietest -46.6 dB | ✅ | Gentle · Hindmarsh–Rose + Willamowski–Rössler · Tangle |
| Never silent on a phone | same, counting only sound above 300 Hz (what phone speakers play) | quietest -52.5 dB | ✅ | Gilmour · Hastings–Powell + Lorenz-84 · Tangle |
| Events you can hear, not a roar | every run has ≥ 0.75 attacks a second a listener can pick out (spectral-flux onsets, Böck & Widmer 2013; a drone scores 0), scaled with Movement | fewest 0.62/s at movement 0.06 · undertow up 5.5% on average, 65.4% at most | ✅ | Slow · Rabinovich–Fabrikant |
| Every attractor plays | each playing attractor ≥ 0.25 notes a second at Medium movement (one every 4 s), scaled with Movement | slowest 0.38/s at movement 0.35 (152% of its bar) | ✅ | 1 particle · Rabinovich–Fabrikant |
| Subwoofer engaged | Receiver output: sound below 80 Hz is −16 to −3 dB of the whole, as in a full mix (a system whose own notes are very low may sit near the top), and 20–40 Hz rumble stays under the 40–80 Hz punch, all 122 runs | below 80 Hz from -13.9 to -3.9 dB | ✅ | Space synth · Willamowski–Rössler |
| No harsh clipping | ≤ 0.5% of samples at full scale | most 0.078% | ✅ | Slow · Rabinovich–Fabrikant |
| No broken samples | 0 NaN in every run | 0 runs with NaN | ✅ |  |
| Pulls keep the notes | no pair below half its Apart notes, 45 pairs × 3 pulls | lowest 56% | ✅ | Hastings–Powell + Tumor–immune · pull |
| Interaction you can hear and see | at Tangle, every pair changes audibly against Apart (pitch moves ≥ 50¢, note rate ≥ 25%, or replies — notes landing 80–300 ms after a partner note — rise ≥ 15 points) and visibly (partner particles flash as calls land, ≥ 1 a second) | 45/45 pairs · weakest: pitch 34¢, notes 24%, replies +37 points, 3.3 flashes/s | ✅ | Willamowski–Rössler + Nosé–Hoover |
| Replies echo the call | at Tangle, the pitch gap between a reply and the partner note it answers (median) is at most 60% of what it is at Apart, in every pair | 42/45 pairs · least echo: 156¢ at Apart → 158¢ at Tangle | ❌ | Hastings–Powell + Rikitake dynamo |
| Deterministic | same settings twice → bit-identical sound | identical | ✅ |  |
