# Clarity: Stages 5–7 (real-time engine, JS port, phone test page)

## Stage 5: fast engine (`research/adaptive-filterbank/fast.py`) — PASS
Each 10 ms hop takes two short-time spectra (4096 and 1024 points), weighted by the gammatone power responses (Parseval). This replaces the per-sample filterbanks. The masking model and the Recover/Tame logic are unchanged.

| Check (limits fixed in advance) | Result | Limit |
|---|---|---|
| Steady band levels vs the reference engine | median 0.25 dB, p95 0.40 | median ≤ 1 dB |
| Hidden-melody ground truth (pipeline margin / median gain / audible after) | −6.85 / +8.4 dB / 70% | within 3 dB of exact / ≥ 3 dB / ≥ 50% |
| Stage-3 flicker and jitter checks, both modes | pass | as in Stage 3 |

## Stage 6: JS engine (`apps/clarity-engine.js`) — PASS
- Parity with Python (`js_parity.py`), both modes: levels, margins and gains agree to within 0.0001 dB at p99; audio SNR 197 dB. Limits: 0.1, 0.5, 0.1 dB and 60 dB.
- Speed: 0.55 s of compute per 1 s of audio on the dev machine, after exact-preserving optimisations:
  - prefix sums for own-sound subtraction;
  - one log per band instead of one per detector;
  - masking supports cut where a contribution falls below −70 dB absolute.
- Phone speed is unknown until measured on the phone.

## Stage 7: worklet, worker and page (`apps/clarity.html`) — PASS offline
- **Layout.** The analysis runs in a Web Worker so the audio thread never blocks. The worklet applies the latest minimum-phase EQ spectrum to both channels: 20 ms Hann frames, 10 ms hop. Latency is exactly 960 samples (20 ms).
- **Offline check (`worklet_test.js`).** Streaming output vs the offline path: 145 dB SNR. Bypass output is bit-exact with the input delayed by 960 samples.
- **Fixes.**
  1. Output was 959 samples late, one sample off. It is now read before the input is written.
  2. The dry bypass path drifted one frame. Each output frame now carries its own dry copy.
- **Headless Chromium smoke test.** Audio flows, worker load 54% on the dev machine, 0 dropped frames, no console errors.
- **Controls.** Tap buttons only, no sliders: Recover 0–200%, Tame 0–200%, Bias −100 to +100, Cambridge or Munich, and an A/B bypass. A live meter shows engine load, slowest frame, dropped frames and the share of the spectrum currently hidden.

## Still open
- Stage 8: Brighten and Boost (Boost needs the ISO 226 equal-loudness data checked first).
- Stage 9: on-phone performance and listening test by Alex.
