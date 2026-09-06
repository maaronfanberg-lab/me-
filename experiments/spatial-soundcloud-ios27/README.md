# Spatial SoundCloud — iOS 27 audio-path PoC

This is the first native proof-of-concept for an eventual SoundCloud-first binaural player.

It deliberately proves the risky part before account UI: an HLS stream is played by `AVPlayer`, Apple's iOS 27 whole-mix `MTAudioProcessingTap` receives the decoded PCM, and a small real-time-safe binaural processor changes that PCM in place.

## Requirements

- Xcode 27 beta or later with the iOS 27 SDK
- iPhone running a compatible iOS 27 build
- XcodeGen (`brew install xcodegen`) to generate the project from `project.yml`
- Headphones strongly recommended
- A non-FairPlay HLS URL for the first test

The new `AVAudioMixInputParametersTrackID.mixID` streaming-tap path is iOS 27 API. This PoC is intentionally not presented as an iOS 26 solution.

## Generate and run

```bash
cd experiments/spatial-soundcloud-ios27
xcodegen generate
open SpatialSoundCloud.xcodeproj
```

Select your development team, choose a physical iPhone, then run.

Paste a direct HLS URL into the field and tap **Load**. The app starts in **Bypass**. Toggle **Spatial** to enable the first binaural mechanism.

## What the first spatializer is

It is not an "8D" pan animation and it is not yet a measured individualized HRTF.

The incoming left and right program channels are treated as two virtual sources. Each source keeps a direct near-ear path and gains a delayed, low-pass-filtered far-ear path. That creates two actual binaural localization cues:

- interaural time difference (ITD)
- frequency-dependent interaural level difference (ILD / head shadow)

The amount control changes virtual source angle and cross-ear contribution. Bypass leaves the source samples untouched.

## What this PoC does not yet do

- SoundCloud login or playlists
- SoundCloud token exchange
- automatic track-to-HLS resolution
- measured HRTF or BRIR convolution
- room reflections
- head tracking
- App Store packaging

Those are intentionally staged after the HLS tap works on real hardware.

## SoundCloud integration direction

SoundCloud currently treats API clients as confidential, so a production iOS app must not contain the client secret. The intended next step is:

```text
iPhone / ASWebAuthenticationSession + PKCE
        |
        v
small Cloudflare Worker token broker
        |
        v
SoundCloud OAuth/token endpoints
        |
        v
iPhone Keychain + SoundCloud library/stream resolver
```

The Worker holds `SOUNDCLOUD_CLIENT_SECRET`; the app never does.

## Pass/fail milestone

Before adding the SoundCloud account layer, verify on a physical device that:

1. HLS playback starts.
2. The UI reports the tap as prepared.
3. Spatial mode is audibly different from bypass.
4. A test signal shows a real cross-ear delay and frequency-dependent attenuation, not only amplitude panning.
5. Backgrounding and headphone route changes do not crash the player.

Research/limitations are recorded in `docs/research/spatial-soundcloud-ios27-poc-2026-09-05.md`.
