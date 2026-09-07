# Pocket Spatial Native iOS experiment

This is a native iPhone probe for the part of Pocket Spatial that Safari cannot test reliably: direct multichannel hardware output through `AVAudioSession` and `AVAudioEngine`.

## What it tests

1. Activates a native playback audio session.
2. Sets `supportsMultichannelContent` to true.
3. Reads `maximumOutputNumberOfChannels` and `outputNumberOfChannels` from the current route.
4. Requests 6 or 8 hardware output channels when the route reports that they are available.
5. Opens an `AVAudioEngine` graph using a standard Core Audio 5.1 or 7.1 channel layout.
6. Generates a short PCM tone in only one channel at a time so the receiver can prove whether the channels are genuinely discrete.

For 7.1 the app uses `kAudioChannelLayoutTag_MPEG_7_1_C`, whose channel order is:

`L, R, C, LFE, Ls, Rs, Lrs, Rrs`

For 5.1 it uses `kAudioChannelLayoutTag_MPEG_5_1_A`:

`L, R, C, LFE, Ls, Rs`

## Expected results

Bluetooth is expected to report two hardware channels.

The important experiment is a Lightning-to-HDMI connection from the iPhone into an AV receiver. If iOS reports 6 or 8 available channels and the individual speaker buttons play from the intended speakers, Pocket Spatial has a native route for true discrete multichannel PCM.

## Building

The repository includes an XcodeGen project spec. On macOS with Xcode and XcodeGen installed:

```sh
cd ios/PocketSpatialNative
xcodegen generate
open PocketSpatialNative.xcodeproj
```

Select an Apple development team, connect the iPhone, and run the app on the physical device. A physical iPhone and the real receiver connection are required for the meaningful channel-route test.

The GitHub Actions workflow builds the app for the iOS Simulator with code signing disabled. That verifies source compilation, but a simulator cannot prove the HDMI hardware route.
