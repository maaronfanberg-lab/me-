# RESONATOR — determinism, output ceiling, shape levels, tap path (2026-10-09)

Approved by Alex at gate 1 (Stage 1 audit). Harness and scripts: `qa-resonator/`.

## Observed problem (measured, Stage 1 audit, original build)
- **Determinism:** same input, two runs → different output whenever attractor, regimes,
  inference, FX stack or the random LFO is on. With `Math.random` seeded, all-on runs were
  bit-identical, so unseeded randomness in the worklet was the only source.
- **Output ceiling:** output stage hard-clipped at ±1.2 (+1.58 dBFS). Feedback alone at max
  reached +2.2 dBTP; all extremes together +4.6 to +5.0 dBTP.
- **Shape levels:** default loudness spread 21.6 dB (Web −18.4 LUFS … Tank −40.0 LUFS).
- **Tap path:** `move` (drag a mass) and `orbit` (rotate view) had no non-drag control.
  Drag controls have repeatedly failed on Alex's devices.

## Sources
- ITU-R BS.1770-4 (2015): K-weighted gated loudness; Annex 2 true-peak via ≥4× oversampling.
- EBU R 128 (2020) and EBU Tech 3341/3342: −1 dBTP maximum true peak for distribution.
- W3C Pointer Events Level 2; WCAG 2.2 SC 2.5.7 (dragging movements must have a single-pointer
  alternative) and SC 2.5.8 (target size).
- mulberry32 PRNG (public-domain 32-bit generator, T. Ettinger) — fast, seedable, adequate for
  audio jitter (not cryptographic).

## Competing explanations / limits
- The first "Splash is inaudible" result was a test error (Splash acts only in splash mode);
  confirmed at 15.7 dB in mode 1. Ratchet: mode-dependent controls are now tested in their mode.
- A sample-domain limiter capped sample peaks at −1.5 dBFS but true peak still hit +3.06 dBTP
  (stress signal ≈50 % energy above 12 kHz). Meter verified against a known fs/4 sine (0.09 dB error),
  so the fault was the limiter, not the meter → replaced with oversampled detection.
- The engine's 16-tap interpolator under-reads the 48-tap meter by up to 1.1 dB; the internal
  ceiling is set to −2.3 dBFS to cover that measured gap.
- Loudness (not peak) under extreme feedback is still about +0.5 LUFS. Not addressed: out of approved scope.
- Phone CPU cost is unmeasured; dev-machine benchmark showed no slowdown but does not transfer.

## Implementation mapping
- **F1** worklet: `Math.random()` → per-instance `this.rnd()` (mulberry32), reset to a fixed seed on
  every `struct`; `{t:'seed'}` message allows a different seed. Main-thread UI randomness
  (pad velocity, Scramble) is user input and left as is.
- **F2** worklet output: ±1.2 clamp → true-peak lookahead limiter (4× windowed-sinc detection,
  16-sample / 0.33 ms lookahead, 80 ms release, gain exactly 1 below ceiling).
- **F3** `SHAPE_LVL` per-shape calibration to −21 LUFS at defaults, sent as `{t:'lvl'}` on every
  structure send; applied linearly after the pickup.
- **F4** nudge pad (▲◀▶▼) shown for `orbit` (turns view) and `move` (moves the selected mass in the
  screen plane, same math as drag). Hold to repeat; one undo step per press, like one drag.

## Validation (post-change, measured)
| check | result |
|---|---|
| additive: 140 configs; those below the ceiling must equal the original delayed 16 samples, bit for bit | 133/133 identical, 7 limited by design, 0 broken |
| determinism, unseeded, 5 random-using modes | 5/5 bit-identical |
| shape loudness at defaults | all −21.0 LUFS (Tank −21.28, limiter touching) |
| true peak, 112 extreme cases (8 shapes × 7 settings × 2 modes) | worst −1.19 dBTP, 0 NaN |
| browser (390×844 touch): orbit/move nudges, hint, select, move, undo, hold-repeat, hide, overlap | all pass |
| app Self-test, original vs patched | identical, no script errors, 0 underruns |
