# Recover / Tame EQ: Stage 4

Code: `research/adaptive-filterbank/stage4.py` and the ground-truth test `hidden_melody.py` / `hm_eval.py`.

## Design
Inferred from the Gullfoss manual and patent; not Soundtheory's code.
- Each frame, every hidden-but-close spectral peak (margin between −12 and 0 dB) has a deficit D = 1 − margin.
- Bias splits D. Recover lifts the peak by (1 + bias)/2 · D. Tame cuts that peak's main masker by (1 − bias)/2 · D. Each is capped at 6 dB.
- Each lift or cut is spread as a 0.25-ERB bump that keeps its full depth at the centre.
- A broadband offset holds K-weighted (BS.1770) loudness constant. A 30 ms causal smoother follows.
- Filtering: a minimum-phase filter every 10 ms, by the cepstral method. Checked against scipy: magnitude within 5e-5 dB, phase within 1.3e-4 rad.
- Frames are 20 ms Hann windows at 50% overlap. Processing is causal, with about 20–30 ms latency and no long buffer.

## Results, synthetic signals (limits fixed before running)
| Check | Cambridge | Munich |
|---|---|---|
| P1: hidden share among spectral peaks falls ≥ 5 pp | 85.1 → 84.2 ✗ | 81.9 → 81.3 ✗ |
| P2: loudness change ≤ 1 dB | −0.04 ✓ | −0.04 ✓ |
| P3: pre-echo ≤ −40 dB, and the linear-phase control fails | −126.5 dB (control −20) ✓ | −136.8 dB (control −20) ✓ |
| P4: bypass output bit-identical to input | ✓ | ✓ |
| P5: same output on every run | ✓ | ✓ |
| P6: p95 gain step per 10 ms ≤ 1 dB | 0.23 ✓ | 0.20 ✓ |

## Ground truth: hidden melody (`hm_eval.py`)
A pad and a melody whose notes are each set 5 dB below their exact masked threshold.

| Measure | Result |
|---|---|
| Live pipeline vs exact margin | −6.81 vs −5.00 dB (within the 3 dB limit) |
| Melody margin after EQ | −6.8 → +1.4 dB (median gain +8.3 dB; limit ≥ 3) |
| Melody frames audible | 0% → 65.6% (limit ≥ 50%) |
| Loudness change | 0.0 dB |

**Pass.**

## Why P1 fails while the melody passes
P1 counts every local spectral peak. In the synthetic chord-plus-noise signal, most of those peaks are random noise ripple that changes every frame. Lifting them is neither possible nor wanted, so P1 measures the noise, not the detail. The hidden-melody test has a known target and shows the effect directly. Replacing P1 with that test is Alex's decision at the gate.

## Fixes made while working on the main goal (limits unchanged)
1. **Engine (Stage 3, the main cause).** Own-sound exclusion used a fixed 40 dB radius (about 78 Hz). That discarded a pad partial 20 Hz from a melody note and reported the hidden note as audible, 11 dB off the exact model, so the EQ was never asked to help. Own sound is now any neighbour whose level is explained by the band's own filter leakage (within 3 dB). Stage 3 still passes after this change.
2. **Test.** The first melody design put notes about 20 Hz from pad partials, finer than either the ear or the analysis can resolve. Notes now sit at least 1 ERB from every partial.
3. **Engine.** Spreading gains by averaging diluted a 6 dB lift to about 0.4 dB. Gains are now spread as full-depth bumps.
4. **Engine.** Spectral peaks were found over the whole own-sound radius, which merged partials 28 Hz apart. Peaks are now local maxima over ±1 band.
5. **Test.** The P3 sensitivity control now uses a fixed, clearly audible linear-phase EQ. The program EQ was too gentle for the control to fail.
6. **New permanent check.** Pipeline vs exact margin on the hidden melody, added because none of the earlier checks caught fix 1.

The real-music run (Audius V66vyPP) runs on GitHub Actions (`stage3-music.yml`); its reports go to `research/adaptive-filterbank/music/`.
