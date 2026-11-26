# Pocket Spatial Studio — research record

**Observed problem:** the Lt/Rt matrix in pocket-spatial.html disturbed the receiver's (Sony STR-DH520) subwoofer output; the user had to reset the receiver. The user also wanted an EQ reaching 50 Hz, mixing tools, and Audius playback.

**Mechanism:** bass management on the receiver sums L+R for the sub. Any L/R phase difference in the bass (anti-phase matrix content, decorrelated reverb, independent per-channel processing) partially cancels in that sum.

**Implementation mapping:** no matrix encoding. All dynamics run before a mid/side stage. Mid passes unchanged (delayed for alignment); side passes through a linear-phase Blackman-windowed FIR high-pass (stopband ≤124 Hz, passband ≥156 Hz), then width gain. Below 120 Hz L and R are identical by construction. EQ: 9 bands 50 Hz–12 kHz, identical filters on both channels.

**Pre-change baseline:** an 8th-order IIR side high-pass at 120 Hz left the 80 Hz side component only −4 dB relative to mid in an anti-phase test. With the compressor placed after M/S, heavy settings leaked side bass to −30 dB.

**Validation (offline render, Chromium, worst-case one-sided and anti-phase bass):** side residual relative to input side: 50 Hz ≤ −81 dB, 80 Hz ≤ −84 dB, 110 Hz ≤ −68 dB across all tested combinations (width 0–150 %, reverb 60 %, warmth 10, compressor −40 dB/12:1/+12 dB, EQ ±12 dB). 50 Hz band set to +6 dB measures +6.0 dB. Audius flow tested with mocked API responses and a local stream (no network in the build sandbox); live Audius streaming still to confirm on device.

**Post-change result:** pending user listening test on the receiver.
