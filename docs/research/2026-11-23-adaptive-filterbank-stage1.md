# Adaptive Fourier↔wavelet filterbank — Stage 1 (offline)

**Aim.** Analysis stage for a Gullfoss-style perceptual EQ in Pocket Spatial. Per band, the filterbank moves between Fourier-like (narrow, constant bandwidth) and wavelet-like (wide, constant-Q) filters, with the ear's ERB filters as the midpoint.

**Basis.**
- Lewicki 2002 (Nat. Neurosci. 5:356): efficient codes look Fourier-like for animal vocalizations and wavelet-like for environmental sounds. The ear sits in between.
- Smith & Lewicki 2006 (Nature 439:978).
- Glasberg & Moore 1990: ERB formula.
- Patterson et al. 1987: gammatone filters.
- Bello et al. 2005: spectral-flux onset detection.

**Design (`research/adaptive-filterbank/stage1.py`).**
- Three 4th-order complex gammatone banks:
  - narrow = min(ERB, 25 Hz)
  - ear = ERB
  - wide = max(ERB, f/4)
- Envelope blend: (1−w)|narrow| + w|wide|.
- w per band is the larger of two triggers:
  - a broadband gate, equal to the octaves covered by bands rising more than 6 dB above their own peak over the previous 5–60 ms (1 octave → 0, 2 octaves → 1);
  - a local rise score.
- w is held at 1 until the narrow filter's ringing has fallen 60 dB, then released with a 20 ms time constant.
- Onset smoothing is causal (no look-ahead). Output is deterministic (seed 1234).

**Pass conditions, fixed before the first run.**
| Check | Condition |
|---|---|
| ERB match | Every filter within 2% of design, by the closed form and by numeric integration |
| Click smear | Adaptive at least 20% below the ear bank, both alone and inside the mix |
| Chord partial separation | Adaptive at least 3 dB above the ear bank, both alone and inside the mix |
| Real drums | All 4 hits detected |
| Steady chord | Mean w below 0.02 |

**Result (`stage1-report.json`): PASS.**
| Check | Result |
|---|---|
| ERB error | worst 0.05% |
| Smear alone | 0.74 → 0.48 ms (−35.1%) |
| Smear in mix | 0.74 → 0.48 ms (−35.1%) |
| Separation alone | +13.15 dB |
| Separation in mix | +12.65 dB |
| Real drum hits | 4/4 |
| Steady-chord w | 0.0012 |

**Fix log (none of the thresholds were changed).**
1. Test error: the smear metric measured the drums' own decay. Fixed by using zero-duration clicks and fixed band weights.
2. Engine error: amplitude beats between chord partials triggered the detector. Fixed with a peak-relative rise and a −70 dB floor.
3. Engine error: below about 300 Hz the "wide" bank was narrower than the ear. Fixed by bounding both families at the ERB.
4. Engine error: a transient under the chord was missed because the gate counted a share of bands. Fixed by measuring the gate in octaves.
5. Engine error: narrow-filter ringing leaked back into the blend after the release. The hold now lasts until that ringing is 60 dB down. The first version used the 99% energy point, and its constant was wrong (13.2 instead of 14.57).
6. Engine error: the onset smoothing looked 1 ms ahead. Made causal; the result is unchanged.

**Limits.**
- Signals are synthetic.
- Smear was not measured on real drum recordings; only detection was.
- 8 partial pairs closer than 15 Hz were excluded, since no bank can resolve them.
- This stage covers analysis only. The EQ comes in later stages.
- On-device performance is untested.
