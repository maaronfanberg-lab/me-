# Spatial SoundCloud iOS 27 PoC — research gate

Date: 2026-09-05
Status: implementation scaffold complete; Xcode 27 / physical-device validation pending
Branch: `feature/spatial-soundcloud-ios27-poc`

## Observed problem

Alex wants ordinary stereo tracks from his SoundCloud library to become a genuinely spatial headphone experience. Existing third-party players demonstrate that SoundCloud account/library playback and real-time DSP are both possible, but there is no evidence yet that an existing app provides the particular binaural depth, externalization, and controllable acoustic-space behavior wanted here.

The immediate technical uncertainty is not SwiftUI. It is whether a SoundCloud AAC HLS stream can be processed as decoded PCM in the playback path without building and synchronizing a second audio renderer.

## Research question

What is the smallest native iPhone architecture that can:

1. play SoundCloud AAC HLS;
2. access decoded PCM during playback;
3. transform that PCM with real binaural cues rather than simple left/right panning;
4. remain real-time safe; and
5. leave a clean path to SoundCloud OAuth/library integration and later head tracking?

## Evidence and sources

### First-party Apple evidence

- Apple, **What's new in HLS 2026**, June 2026: `MTAudioProcessingTap` can now process the mixed audio output of any `AVPlayerItem`, independent of track count and encoding, except FairPlay-protected audio. Apple specifies `AVAudioMixInputParametersTrackMixID` plus `audioTapProcessor` as the setup path.
- Apple Developer Documentation, **AVAudioMixInputParametersTrackID.mixID**: the special mix identifier is explicitly intended for streaming playback taps. The Xcode 27 SDK headers mark it available on iOS 27 and related 27.0 platforms.
- Apple Developer Documentation, **MTAudioProcessingTapCreateWithPreferredFormat**: a tap can request an LPCM processing format, but the actual flags/interleaving/sample size must still be inspected in the prepare callback. The API is beta as of this record.
- Apple Developer Documentation, **AVAudioEnvironmentNode**: Apple's built-in 3D positioning path spatializes mono inputs. It is therefore not a transparent arbitrary-stereo spatializer.

### First-party SoundCloud evidence

- SoundCloud developer documentation currently describes OAuth 2.1 / PKCE and AAC HLS stream transcodings for custom players.
- SoundCloud's current authentication documentation also states that clients are treated as confidential and a `client_secret` is required for token acquisition/refresh. A secret therefore must not be shipped inside an iOS binary; a small server-side token broker is required for production-safe account login.
- `/tracks/{track_urn}/streams` remains authenticated. The preferred modern streams are `hls_aac_160_url` and `hls_aac_96_url`.
- Stream URLs should be treated as ephemeral and resolved for playback rather than persisted as durable media URLs.
- Custom players must credit the uploader, credit SoundCloud, and link to the original SoundCloud work.

### Independent second-model review

The repository's verified Claude oracle bridge was used for a bounded architecture review:

- request: `bridge/inbox/2026-09-05-spatial-soundcloud-002.json`
- response: `bridge/outbox/2026-09-05-spatial-soundcloud-002.json`
- verified model family: Claude
- resolved primary response model: `claude-sonnet-5`

Claude independently recommended separating network/auth, decode/ingest, and DSP; treating the decoded-PCM boundary as the main risk; using real binaural tests rather than subjective widening; and keeping the audio callback free of allocation/locking/network work. Claude's initial assumption that HLS-to-tap processing required an unsupported workaround is superseded by Apple's new iOS 27 whole-mix HLS tap support above.

A later branch-level Claude code review could not inspect this feature branch because the oracle runner checked out only the triggering `main` commit. The oracle explicitly declined to speculate without source visibility. A source-inline follow-up review was submitted separately rather than treating the failed branch review as evidence.

## Competing explanations / limitations

1. A perceived "3D" effect can come from stereo widening, phase tricks, or automated pan motion without true binaural cues. Therefore listening impressions alone are not enough to validate the mechanism.
2. Apple's new whole-mix HLS tap path is iOS 27-era beta API as of 2026-09-05. It should not be assumed to work on iOS 26, and behavior may change before final SDK release.
3. `AVAudioEnvironmentNode` is useful for a mono-source reference experiment, but forcing an existing stereo master through mono point sources can alter the artist's mix. A custom stereo-aware binaural stage is preferable for the long-term design.
4. A custom HRTF/BRIR engine increases DSP complexity and CPU cost. The first PoC proves a smaller measurable binaural mechanism before convolution-heavy rooms are added.
5. SoundCloud OAuth code is scaffolded, but end-to-end authentication still requires a registered SoundCloud API application, a deployed Worker, and real credentials. No credential is committed to the repository.
6. The SoundCloud stream resolver assumes that an authenticated API stream URL redirects to an HTTPS CDN URL that no longer requires the OAuth header. The app deliberately fails closed if the final URL is still `api.soundcloud.com`; this behavior must be tested against a real account/track.
7. Apple's unsupported `AVURLAssetHTTPHeaderFieldsKey` is deliberately not used.

## 10-level gate

1. **Observed problem:** PASS. The desired behavior and current gap are explicit.
2. **Foundational evidence:** PASS for the audio mechanism. Binaural localization relies on interaural time difference (ITD), interaural level difference (ILD), and frequency-dependent filtering; the PoC implements measurable ITD/ILD plus head-shadow filtering rather than a volume pan.
3. **Current evidence:** PASS. Apple 2026 HLS documentation materially changes the ingest architecture and is the primary reason for targeting iOS 27.
4. **Natural-behavior evidence:** N/A. This change is an audio-processing prototype, not human-behavior modeling.
5. **Mechanism evidence:** PASS. The proposed output is generated by delayed/frequency-shaped cross-ear paths and virtual-source geometry, not an effect-name preset.
6. **Competing explanations:** PASS. Stereo widening/panning is treated as a confound and gets separate proof tests.
7. **Replication/correction/limitations:** PARTIAL. The new Apple API is beta and cannot yet have mature field evidence. This uncertainty is explicit.
8. **Context transfer:** PASS WITH LIMIT. Apple's HLS tap applies to AVPlayer streaming generally, but SoundCloud-specific CDN/auth behavior still needs device testing.
9. **Implementation mapping:** PASS. `SoundCloudAccount` handles PKCE/token state; the Cloudflare Worker holds the client secret; `SoundCloudLibrary` resolves library resources and AAC HLS; `AVPlayerItem` owns transport; `MTAudioProcessingTap` exposes decoded PCM; `BinauralDSP` transforms buffers in place.
10. **Post-change validation:** DEFINED below. No success claim is permitted until physical-device tests pass.

## Implemented mapping

### SoundCloud identity and library

`ASWebAuthenticationSession + PKCE`
→ Cloudflare token broker
→ SoundCloud token endpoint
→ iPhone Keychain
→ `/me/likes/tracks` + `/me/playlists`
→ `/tracks/{track_urn}/streams`
→ prefer AAC HLS 160k, fallback 96k
→ authenticated stream preflight
→ final HTTPS CDN URL if the redirect is self-sufficient

All OAuth-bearing API requests are pinned to `https://api.soundcloud.com` before the token is attached. The Worker does not proxy media.

### PoC A — iOS 27 HLS tap

`AVPlayerItem(HLS URL)`
→ `AVAudioMixInputParametersTrackID.mixID`
→ `MTAudioProcessingTapCreateWithPreferredFormat`
→ decoded stereo Float32 target / actual format inspection in prepare
→ in-place DSP
→ AVPlayer's normal headphone output

This deliberately avoids a second `AVAudioEngine` renderer for the first live-stream prototype, eliminating duplicate clocks, mute/synchronization logic, and an unnecessary PCM ring buffer.

### PoC B — minimal binaural mechanism

Treat the incoming left and right program channels as two virtual sources. For each source:

- preserve the ipsilateral direct path;
- add a delayed contralateral path to create ITD;
- apply frequency-dependent attenuation/head-shadow filtering to the contralateral path to create non-flat ILD;
- expose a conservative spatial-amount control;
- maintain headroom and provide an exact bypass.

This is intentionally a small binaural renderer, not a claim of individualized HRTF accuracy. Deterministic unit tests cover bypass transparency, delayed cross-ear energy, and frequency-dependent far-ear attenuation.

### Later stages

1. Xcode 27 and physical iPhone validation of the beta streaming tap.
2. Real SoundCloud OAuth/playlist/HLS redirect validation with registered credentials.
3. Measured/synthetic HRTF FIR convolution via Accelerate/vDSP.
4. Early-reflection field and room/BRIR convolution.
5. Distance/depth controls.
6. Optional `CMHeadphoneMotionManager` head tracking.
7. Final SoundCloud logo/branding implementation and App Store compliance pass.

## Pre-change baseline

No native iOS project in this repository previously implemented SoundCloud HLS whole-mix tapping or in-place binaural DSP.

## Validation criteria

The PoC is successful only if all of these are observed on a physical iPhone running an iOS 27 build that contains the new API:

1. A non-FairPlay HLS stream plays through `AVPlayer`.
2. Tap prepare/process callbacks execute continuously for the stream.
3. Bypass is sample-path transparent within floating-point tolerance for supported formats.
4. Spatial mode produces measurable non-zero cross-ear delay and frequency-dependent cross-ear attenuation, proving it is not merely a balance/pan operation.
5. No allocation, locks, network calls, logging, or Swift async work occur in the process callback.
6. A real SoundCloud track resolves from authenticated `/streams` to a playable final AAC-HLS URL without relying on unsupported AVFoundation header injection.
7. A 60-minute playback test produces no crash and no persistent audio dropout under ordinary network conditions.
8. Background/foreground and headphone route changes either recover cleanly or fail in a documented, observable way.

## Post-change result

Implemented on `feature/spatial-soundcloud-ios27-poc`:

- iOS 27 whole-mix `MTAudioProcessingTap` scaffold with preferred stereo Float32 PCM request;
- realtime-safe first-pass ITD/head-shadow DSP with atomic UI parameters;
- deterministic DSP proof tests;
- SwiftUI player, diagnostics, direct-HLS laboratory mode;
- SoundCloud OAuth/PKCE controller and Keychain storage;
- Cloudflare secret-bearing token broker;
- Likes/playlists loading and AAC-HLS resolver;
- fail-closed token-host validation and authenticated stream preflight;
- creator/SoundCloud track links in the prototype UI.

Still pending: Xcode 27 compilation, real SoundCloud credentials, Worker deployment, physical-device HLS/tap validation, and long-run playback testing. Repository code alone is not evidence that the beta streaming path works on Alex's iPhone.
