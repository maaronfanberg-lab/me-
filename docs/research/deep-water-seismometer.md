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

## Update (2026-11-16): higher pitches, more variety, no static
Observed: Alex wanted higher pitches and more variety, without the steady static. Cause found: every measured half-wave
became a voice (≈26 voices/s on a microseism-like trace) with pitch squeezed into 22–118 Hz (saturating map), and the
master low-pass sat at 1.8 kHz. Change: (1) pitch proportional to the measured wave frequency, f = 4 × played wave Hz
(80× the ground frequency at 20× playback), 30 Hz–2.5 kHz, so intervals between waves are preserved (an octave in the
ground is an octave in the sound); (2) a half-wave sings only if its peak is ≥ 1.25× the running average, or if none has
sung for 0.5 s; (3) up/down-going half-waves pan slightly left/right; (4) master low-pass 6 kHz, voice low-pass
1.5–5 kHz by curvature. Results on a synthetic microseism + quake trace: voices/s 25.8 → 9.8; pitch 10–90% range
31–111 Hz → 30–1600 Hz; tests updated (prominence, steady background ≤ 4 voices/s, 2× frequency = octave ±0.15).

## Update (2026-11-16, later): "not impressive"
Observed in a render: voices were very short (≤0.9 s) and, on microseism-dominated traces, mostly pinned to the 30 Hz floor,
so the result was a dense low clicking. Changes: one transposition factor per trace (slow log-mean of wave frequency → 200 Hz)
(superseded below); voices ring for their physical decay time (6/β, 0.3–2.5 s); a half-wave must also reach
1.2× the trace's 2 s RMS (tiny noise wiggles never sing); voices get the open-water reverb and a wider stereo image;
bubble-cloud collective resonance (Lu, Prosperetti & Yoon 1990; Commander & Prosperetti 1989) gives a deep boom when 6+
voices form within a second. Render (synthetic microseism + quake): voice pitch 10/50/90% = 40/220/2464 Hz (was all ≈30–111 Hz),
6.7 voices/s, 6 cloud booms at 20–28 Hz around the quake.

Correction (same day): the per-trace transposition was replaced by a fixed map of the real ground frequency fg (played Hz / 20)
over the seismic band: f = 60·(2000/60)^(log(fg/0.05)/log 200), 40–2500 Hz (microseisms ≈ 150 Hz, body waves 1–8 Hz ≈
500–1700 Hz); voice displacement scaled by 3 cm/a so small (high) bubbles radiate the same pressure as large ones (they were
~26 dB quieter); calm waves at ≥ 1.2× RMS may sing every 0.25 s; cloud boom level reduced. Checks: 0.2/2/8 Hz ground waves
→ 150/689/2000 Hz at −23.5/−17.6/−17.3 dB; render voice pitch 10/50/90% = 117/967/2500 Hz, 7.7 voices/s; all tests pass.

## Update (2026-11-16): great-earthquake archive
Alex asked to use historical seismograph recordings from public archives. A GitHub Actions job
(.github/workflows/deep-water-archive.yml, apps/deep-water/archive/build.py, ObsPy) finds each event in the USGS
catalogue, downloads the vertical BHZ seismogram at IU.ANMO (fallbacks IU.HRV/COLA/TUC) from EarthScope/IRIS FDSN
dataselect, 2 min before the iasp91 P arrival to 100 min after, detrends, low-passes at 8 Hz and resamples to 20 sps, and
commits int16 + index.json. First run: 9 of 10 archived (Tōhoku 2011, Sumatra 2004, Maule 2010, Kamchatka 2025,
Chignik 2021, Türkiye 2023, Kaikōura 2016, Gorkha 2015, Ridgecrest 2019); Bolivia 1994 had no IU …00.BHZ data.
The app plays them from the same site (no cross-origin request), through the same bubble or direct modes as live data.
