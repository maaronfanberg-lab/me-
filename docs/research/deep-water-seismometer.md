# Deep Water — hearing real ground motion (2026-11-14)

**Observed request.** Alex asked whether the app's vibrations can be correlated with the earthquakes' vibrations.
v2 only used earthquake catalogue entries (time, magnitude, place), not the ground motion itself.

**Mechanism.** Audification of a real seismogram: play the recorded vertical ground velocity directly, sped up so its
frequencies land in hearing range (Speeth 1961, JASA 33, 909; Dombois 2001, ICAD; Sonification Handbook, audification
chapter). Data: EarthScope/IRIS FDSN dataselect (fdsnws-dataselect 1, miniSEED), stations IU.ANMO, US.EYMN, IU.HRV,
IU.POHA, IU.MAJO, channel BHZ (40 samples/s). The irisws-timeseries audio service was retired (EarthScope notice,
26 Aug 2026), so miniSEED is decoded in the browser.

**Mapping.** Last ~20 minutes, mean removed, 0.05 Hz high-pass, scaled by 3x the 90th-percentile amplitude and soft
limited, played 20x faster (800 samples/s) as a one-minute loop refreshed each minute: 1 Hz ground motion -> 20 Hz,
5 Hz -> 100 Hz. Its envelope also scales the vent bubble rate (0.5x-3x): the shaking releases bubbles.

**Validation.** Decoder checked against libmseed's reference files: Steim-1 and Steim-2 (big- and little-endian) decode
to exactly the int32 reference samples (0 mismatches). Page tested in a headless browser with a real miniSEED response:
request URL formed correctly, trace drawn with playhead, envelope reported, Off removes the layer, no errors.

**Limits.** CORS on the EarthScope service could not be tested from the build machine (network-restricted); the page
says "not reachable" plainly if the browser blocks it. Data latency is typically minutes. With 20x compression a
quake's waves enter the loop within ~1-2 minutes of reaching the station, then repeat each minute for ~20 minutes.

## 2026-11-14 follow-up: steady hiss
**Observed:** Alex hears a prolonged hiss/static even after refresh. **Measured (engine alone):** the noise-based deep
hum sat at -22 to -29 dB with energy into the hundreds of Hz, and rising bubbles were driven by white-noise "wake"
forcing whose broadband leakage summed into a hiss (-39.7 dB in 300-1800 Hz after bubbles stopped starting).
**Change:** wake forcing band-limited to just above each bubble's own note (2-pole low-pass at 1.5·ω) and fading over
the first ~4 s of the rise (physically, wake shedding is low-frequency, St·U/d ~ 1 Hz, so white forcing was too broad);
hum now 4-pole low-pass at 45 Hz, ~10 dB quieter, off by default. **Result:** 300-1800 Hz tail energy -61.7 dB
(22 dB lower); single-bubble murmur at 10 s -53 dB (was -36); Minnaert pitch check still exact.

## Update (2026-11-14): the seismogram plays the bubbles
Alex chose to have the ground motion drive the bubbles, with pitch matching the graph. The ungated trace now (a) is the
external force on each bubble oscillator (ẍ + 2βẋ + ω²x = k·ω²·y(t)), (b) creates a bubble wherever its 10 ms
envelope exceeds 1.8× its 2 s envelope (or every 3 s of steady motion), and (c) sets pitch from the trace height:
f = 40·10^((u+1)/2) Hz, u = clamp(y/0.5, −1, 1), which the bubble keeps following while it rings. Quake-catalogue
bubbles are used only when no seismogram is available. Check: correlation between bubble pitch (log) and trace height at
release = 1.000 on a synthetic trace; engine 1.4% of real time; browser test with real miniSEED, no errors.
