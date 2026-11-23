# Ear masking model — Stage 2 (offline): did not pass the gate

**Model A (built).** Glasberg & Moore (1990) roex excitation pattern.
- p51 = 4fc/ERB.
- The lower side broadens with level: k = 0.38, as in Glasberg & Moore 1990. AMT moore1997 and ANSI S3.4-2007 use 0.35.
- The upper side is fixed.
- Masked threshold is the target level at which masker + target excitation exceeds the masker's alone by 1 dB at any detector (van der Heijden & Kohlrausch 1994). Internal noise is set at the threshold in quiet.

**Model B (reference).** The Terhardt (1979) / Maiwald (1967) tone masking pattern in Bark, a published fit to Zwicker's data:
- lower slope 27 dB/Bark;
- upper slope 24 + 230/f − 0.2L dB/Bark.

**Two-way checks on the building blocks.** All passed:
- the roex ERB integral matches its design to 3 decimals;
- the ERB-number and Bark inverses round-trip to under 1e-12.

**Pass conditions, fixed before the first run.**
| Check | Condition |
|---|---|
| Shape fit, every level | mean \|A − B\| ≤ 3 dB and max ≤ 6 dB |
| Upward spread | Upper slope flattens as level rises |
| Constant k | 0.38 and 0.35 differ by ≤ 1 dB mean |

**Result.**
| Masker level | Mean \|d\| | Max \|d\| | Upper slope A / B (dB/Bark) |
|---|---|---|---|
| 40 dB | 2.15 | 4.5 | n/a (too few points above the floor) / 16.2 |
| 60 dB | 3.50 ✗ | 5.94 | 11.9 / 12.2 |
| 80 dB | 5.11 ✗ | 7.52 ✗ | 8.1 / 8.2 |
- Flattening: ✓.
- Constant k: differs by 1.06 dB ✗.

**Where it disagrees.** On the upper side, the two models agree to within 0.3 dB/Bark. The misses are all below the masker frequency, where Model A's slope is about 21–25 dB/Bark against Model B's 27. Model B's lower slope is level-independent by construction.

**Test fix (thresholds unchanged).** The upper-slope fit now uses only points at least 10 dB above the threshold in quiet. Before this, the internal-noise floor made the slope look flatter than it is.

**Open question.** The two references come from different data sets: notched noise (Glasberg & Moore) and tone masking patterns (Zwicker). Raw masking-pattern data, such as Moore, Alcántara & Dau 1998 (JASA 104:1023), are needed to judge which is right. Those data were not reachable from here.
