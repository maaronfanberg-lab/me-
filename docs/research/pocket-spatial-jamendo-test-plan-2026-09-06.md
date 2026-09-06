# Pocket Spatial Jamendo live-stream test plan

Purpose: prove a free, rights-filtered live stream can reach the existing Pocket Spatial Web Audio graph on iPhone 6 / iOS 12 before any production Jamendo account setup.

## Source contract
- Jamendo read API test client only (`709fa152`) during development.
- Stream via the returned `audio` URL using `audioformat=mp32`.
- Request `include=licenses` and `ccnd=false`.
- Independently reject missing/non-Creative-Commons licenses and any URL containing a NoDerivatives marker (`-nd/` or `/nd/`).
- Do not expose download behavior. Do not record or persist streamed media.

## Automated gates
1. Existing DSP math tests.
2. Existing UI-to-Web-Audio target integration tests.
3. Pure Jamendo URL/license helper tests executed from the production source.
4. ES5 syntax check for the iPhone 6 browser script.
5. Static source/rights contract checks.
6. Live Jamendo API smoke test using the published test client.
7. Live stream byte-range fetch.
8. CORS header verification for the GitHub Pages origin.
9. Existing SoundCloud worker/security checks remain unchanged.
10. Existing HTML and lightweight-DSP compatibility checks remain unchanged.

## Physical-device probe
For a selected eligible track, Pocket Spatial creates two temporary audio elements. One tests native playback. The second uses `crossOrigin=anonymous` and is connected to a temporary `MediaElementAudioSourceNode` and `AnalyserNode`. For roughly two seconds the app measures:
- native `currentTime` advancement,
- CORS media `currentTime` advancement,
- maximum analyser deviation from the 8-bit silence midpoint (128).

Spatial transport is considered verified only when all three pass and analyser deviation is greater than 2. Otherwise the app reports the exact failure reason and can fall back to dry playback without claiming spatial processing.

## Success criterion
A physical iPhone 6 test must display `SPATIAL PCM VERIFIED` for at least one Jamendo stream, after which the normal Pocket Spatial Play + Spatial controls are used to test the real DSP graph and home-theater output.

## Failure interpretation
- `native_stream_did_not_advance`: Safari could not play the stream at all.
- `cors_media_did_not_advance`: native playback may work, but the CORS-enabled media path failed.
- `web_audio_pcm_flatline`: media advanced, but Web Audio did not receive usable PCM.
- `probe_graph_failed`: Web Audio graph creation failed on-device.

A failure is useful data and must not be relabeled as spatial playback.
