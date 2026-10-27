# Spatial SoundCloud — iOS 27 proof of concept

This branch contains the first native proof-of-concept for a SoundCloud-first binaural player.

The intended path is now wired end to end in code:

```text
SoundCloud OAuth + PKCE
        |
        v
Cloudflare token broker (client secret stays server-side)
        |
        v
iPhone Keychain
        |
        v
Likes / Playlists / AAC-HLS resolver
        |
        v
AVPlayer
        |
        v
iOS 27 whole-mix MTAudioProcessingTap
        |
        v
binaural DSP
        |
        v
headphones
```

It is still a proof-of-concept until the new iOS 27 media APIs and SoundCloud redirect behavior pass on a physical device.

## Requirements

- Xcode 27 beta or later with the iOS 27 SDK
- iPhone running a compatible iOS 27 build
- XcodeGen (`brew install xcodegen`) to generate the project from `project.yml`
- Headphones strongly recommended
- For SoundCloud account mode: a registered SoundCloud API application and a deployed `cloudflare/spatial-soundcloud-auth` Worker

The new `AVAudioMixInputParametersTrackID.mixID` whole-streaming-mix tap is iOS 27 API. This PoC is intentionally not presented as an iOS 26 solution.

## Generate and run

```bash
cd experiments/spatial-soundcloud-ios27
xcodegen generate
open SpatialSoundCloud.xcodeproj
```

Select your development team and a physical iPhone.

The app has two tabs:

- **SoundCloud** — signs in, loads Likes and Playlists, resolves the preferred AAC HLS stream, and routes it into the spatial player.
- **Lab** — accepts a direct non-FairPlay HLS URL so the Apple streaming-tap/DSP path can be tested independently of SoundCloud auth.

## Configure SoundCloud

SoundCloud currently requires OAuth 2.1 + PKCE, but it also currently treats clients as confidential and requires the app's `client_secret` for token exchange and refresh. The secret must not be embedded in the iPhone app.

Configure and deploy:

```text
cloudflare/spatial-soundcloud-auth/
```

See that directory's README. After deployment, replace the placeholder value for `SoundCloudBrokerBaseURL` in:

```text
SpatialSoundCloud/Info.plist
```

The registered SoundCloud callback must match:

```text
spatialsoundcloud://soundcloud/callback
```

The app stores access/refresh tokens in Keychain. It sends authenticated API/library requests directly to SoundCloud; the Worker never proxies audio.

## Stream resolution

The app requests `/tracks/{track_urn}/streams`, prefers `hls_aac_160_url`, and falls back to `hls_aac_96_url`.

SoundCloud's returned stream endpoint remains authenticated. The app therefore preflights that small HLS request with `URLSession` and an OAuth header. If the request redirects to a signed CDN URL, that final URL is passed to `AVPlayer`. If it remains an OAuth-header-dependent `api.soundcloud.com` URL, playback is deliberately rejected rather than relying on Apple's unsupported `AVURLAssetHTTPHeaderFieldsKey` behavior.

This exact redirect behavior is one of the physical-device/API tests still required.

## What the first spatializer is

It is not an "8D" pan animation and it is not yet a measured individualized HRTF.

The incoming left and right program channels are treated as two virtual sources. Each source keeps a direct near-ear path and gains a delayed, low-pass-filtered far-ear path. That creates two measurable binaural localization cues:

- interaural time difference (ITD)
- frequency-dependent interaural level difference (ILD / head shadow)

The amount control changes virtual source angle and cross-ear contribution. Bypass leaves the source samples untouched. Unit tests verify transparent bypass, delayed cross-ear energy, and stronger high-frequency far-ear attenuation.

## Not yet implemented

- measured HRTF or BRIR convolution
- early-reflection/room model
- distance/depth control
- head tracking
- production SoundCloud logo assets / final branding layout
- App Store packaging and compliance review

## Pass/fail milestones

The PoC is not considered validated until:

1. Xcode 27 compiles the new whole-mix tap implementation without API/signature changes.
2. A physical iOS 27 iPhone plays a non-FairPlay HLS stream while the tap's prepare/process callbacks run continuously.
3. A real SoundCloud track resolves from authenticated `/streams` to a playable signed CDN AAC-HLS URL.
4. Spatial mode produces measurable delayed and frequency-shaped cross-ear energy, not only amplitude panning.
5. Bypass is transparent for the supported PCM format.
6. Background/foreground transitions and headphone route changes do not crash playback.
7. A long playback session has no persistent dropouts or realtime-thread violations.

Research and limitations are recorded in `docs/research/spatial-soundcloud-ios27-poc-2026-09-05.md`.
