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
